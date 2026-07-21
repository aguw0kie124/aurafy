"""The recommender: a single-pass RAG pipeline.

    interpret -> retrieve -> rerank -> curate (RAG) -> safety

1. ``llm.interpret`` turns the request into a spec + a "vibe" sentence + discovery
   name ideas (skipped for parameter builds / when Gemini is unconfigured).
2. RETRIEVE: the user's own library (familiar) + discovery = pgvector nearest-to-
   the-embedded-vibe over the catalog + live Spotify search of the discovery names
   (new finds are persisted and embedded — the catalog flywheel).
3. RERANK: ``db.knn_taste_scores`` (taste-fit) blended with vibe similarity and
   popularity; keep the strongest ~40 with metadata.
4. CURATE (the RAG step): ``llm.curate`` selects + orders the final playlist from
   those ~40 retrieved tracks; returned ids are validated against the supplied set,
   so nothing invented survives.
5. SAFETY: avoid-genre filter, title+artist dedupe, per-artist cap, variety order.

Every step degrades gracefully: no Gemini key / no embeddings / a rate limit falls
back to a deterministic taste-ranked build, so a build never hard-fails.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import HTTPException

from . import db, embeddings, llm

MIN_LENGTH, MAX_LENGTH, DEFAULT_LENGTH = 5, 50, 25

CATALOG_K = 60          # ANN candidates pulled near the vibe vector
CURATE_POOL = 40        # retrieved tracks handed to the LLM curator
# Dev-mode Spotify apps reject search limits above 10, so page with offset.
SEARCH_PAGE_LIMIT = 10
SEARCH_PAGES = 2        # up to 20 tracks per query
SEARCH_CONCURRENCY = 6


# --- spec ------------------------------------------------------------------


def _normalize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Clamp a raw spec (from the LLM or UI params) into safe pipeline inputs."""
    length = int(spec.get("length") or DEFAULT_LENGTH)
    length = max(MIN_LENGTH, min(length, MAX_LENGTH))
    mix = spec.get("mix")
    mix = 30 if mix is None else int(mix)
    mix = max(0, min(mix, 100))
    genres = [g.strip().lower() for g in (spec.get("genres") or []) if isinstance(g, str) and g.strip()]
    avoid = [g.strip().lower() for g in (spec.get("avoid_genres") or []) if isinstance(g, str) and g.strip()]
    return {
        "name": (spec.get("name") or "").strip() or "Aurafy Mix",
        "description": (spec.get("description") or "").strip(),
        "length": length,
        "mix": mix,
        "allow_explicit": bool(spec.get("allow_explicit", True)),
        "genres": genres[:8],
        "avoid_genres": avoid[:8],
        "vibe": (spec.get("vibe") or "").strip(),
        "discovery_artists": list(spec.get("discovery_artists") or []),
        "discovery_tracks": list(spec.get("discovery_tracks") or []),
    }


def _spec_from_params(body: Any) -> dict[str, Any]:
    """A spec straight from the UI knobs (params mode / LLM unavailable)."""
    genres = list(body.genres or [])
    return _normalize_spec(
        {
            "name": body.name or "Aurafy Mix",
            "description": body.description or "",
            "length": body.length,
            "mix": body.mix,
            "allow_explicit": body.allowExplicit,
            "genres": genres,
            "avoid_genres": list(body.avoidGenres or []),
            # No LLM: seed the vibe from the requested genres so ANN still has a
            # meaningful query, and use the seed artists as discovery names.
            "vibe": (body.description or "") + " " + " ".join(genres),
            "discovery_artists": list(body.seedArtistNames or []),
        }
    )


# --- genre helpers (lifted from the retired engine) -------------------------


def _matches_any(genre: str, terms: set[str]) -> bool:
    """Word-boundary match so avoiding "rap" hits "pop rap" but not "trap"."""
    padded = f" {genre} "
    return any(f" {term} " in padded for term in terms)


def _drop_avoided(cands: list[dict[str, Any]], avoid: set[str]) -> list[dict[str, Any]]:
    if not avoid:
        return cands
    return [c for c in cands if not any(_matches_any(g.lower(), avoid) for g in c.get("genres") or [])]


def _primary_artist(cand: dict[str, Any]) -> str:
    ids = cand.get("artist_ids") or []
    return ids[0] if ids else cand["artist"]


def _order_for_variety(cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Greedily avoid two tracks by the same primary artist back to back."""
    remaining = list(cands)
    ordered: list[dict[str, Any]] = []
    while remaining:
        prev = _primary_artist(ordered[-1]) if ordered else None
        pick = next((c for c in remaining if _primary_artist(c) != prev), remaining[0])
        ordered.append(pick)
        remaining.remove(pick)
    return ordered


# --- live Spotify discovery (offset-paged within the dev-mode cap) ----------


def _cand_from_spotify(track: dict[str, Any]) -> dict[str, Any]:
    from .main import artist_names, select_image_url, spotify_external_url

    album = track.get("album") or {}
    return {
        "spotify_track_id": track["id"],
        "title": track.get("name") or "Unknown track",
        "artist": artist_names(track),
        "album": album.get("name"),
        "image_url": select_image_url(album.get("images")),
        "external_url": spotify_external_url(track),
        "popularity": track.get("popularity") or 0,
        "explicit": bool(track.get("explicit")),
        "duration_ms": track.get("duration_ms"),
        "artist_ids": [a["id"] for a in (track.get("artists") or []) if a.get("id")],
        "artist_name_list": [a["name"] for a in (track.get("artists") or []) if a.get("name")],
        "genres": [],
    }


async def _search_tracks(client: httpx.AsyncClient, token: str, query: str) -> list[dict[str, Any]]:
    """Offset-paged track search within the dev-mode limit-10 cap."""
    from .main import spotify_get

    tracks: list[dict[str, Any]] = []
    for page in range(SEARCH_PAGES):
        try:
            resp = await spotify_get(
                client, "/search", token,
                {"q": query, "type": "track", "limit": SEARCH_PAGE_LIMIT, "offset": page * SEARCH_PAGE_LIMIT},
            )
        except HTTPException:
            break
        batch = (resp.get("tracks") or {}).get("items") or []
        tracks.extend(t for t in batch if t and t.get("id"))
        if len(batch) < SEARCH_PAGE_LIMIT:
            break
    return tracks


async def _live_discovery(
    session: dict[str, Any], spec: dict[str, Any], owned: set[str]
) -> list[dict[str, Any]]:
    """Resolve the LLM's discovery names through live Spotify search into real,
    non-owned candidate tracks. Best-effort: any failure yields fewer candidates."""
    from .main import refresh_access_token

    artists = spec["discovery_artists"]
    tracks = spec["discovery_tracks"]
    if not artists and not tracks:
        return []
    queries = [f'artist:"{n}"' for n in artists[:10]]
    queries += [f'track:"{t["title"]}" artist:"{t["artist"]}"' for t in tracks[:10]]

    try:
        token = await refresh_access_token(session)
    except Exception:
        return []

    sem = asyncio.Semaphore(SEARCH_CONCURRENCY)

    async def run(q: str) -> list[dict[str, Any]]:
        async with sem:
            return await _search_tracks(client, token, q)

    async with httpx.AsyncClient(timeout=30) as client:
        results = await asyncio.gather(*(run(q) for q in queries))

    found: dict[str, dict[str, Any]] = {}
    for tracks_batch in results:
        for track in tracks_batch:
            if track["id"] not in owned:
                found.setdefault(track["id"], _cand_from_spotify(track))
    cands = list(found.values())
    if not spec["allow_explicit"]:
        cands = [c for c in cands if not c["explicit"]]
    return cands


async def _persist_and_embed(cands: list[dict[str, Any]]) -> None:
    """Persist live finds into the shared catalog and embed them inline so kNN /
    curation / future ANN can use them (the discovery flywheel). Best-effort."""
    if not cands:
        return
    artists: dict[str, dict[str, Any]] = {}
    track_artists: list[tuple[str, str, int]] = []
    for c in cands:
        for pos, (aid, name) in enumerate(zip(c["artist_ids"], c["artist_name_list"])):
            artists.setdefault(aid, {"spotify_artist_id": aid, "name": name})
            track_artists.append((c["spotify_track_id"], aid, pos))
    try:
        await db.upsert_catalog_tracks(list(artists.values()), cands, track_artists)
    except Exception:
        return
    if not embeddings.is_configured():
        return
    try:
        docs = [embeddings.track_doc(c) for c in cands]
        vecs = await embeddings.embed_texts(docs)
        pairs = [(c["spotify_track_id"], v) for c, v in zip(cands, vecs) if v is not None]
        if pairs:
            await db.store_track_embeddings(pairs)
    except Exception:
        pass


# --- enrichment & scoring ---------------------------------------------------


async def _enrich_genres(cands: list[dict[str, Any]]) -> None:
    """Fill artist_ids/names/genres for thin candidates (ANN rows, live finds)."""
    thin = [c["spotify_track_id"] for c in cands if not c.get("genres")]
    if not thin:
        return
    meta = await db.get_track_artist_genres(thin)
    for c in cands:
        m = meta.get(c["spotify_track_id"])
        if m:
            c["artist_ids"] = c.get("artist_ids") or m["artist_ids"]
            c["artist_name_list"] = c.get("artist_name_list") or m["artist_name_list"]
            c["genres"] = m["genres"] or c.get("genres") or []


def _discovery_score(c: dict[str, Any]) -> float:
    """Blend taste-fit, vibe similarity, and a little popularity."""
    return (
        c.get("taste", 0.0)
        + 0.4 * c.get("similarity", 0.0)
        + 0.1 * (c.get("popularity") or 0) / 100.0
    )


# --- output -----------------------------------------------------------------


def _output_track(cand: dict[str, Any]) -> dict[str, Any]:
    return {
        "spotifyTrackId": cand["spotify_track_id"],
        "title": cand["title"],
        "artist": cand["artist"],
        "album": cand.get("album") or "Unknown album",
        "coverUrl": cand.get("image_url"),
        "externalUrl": cand.get("external_url"),
        "source": cand.get("kind", "library"),
    }


def _finalize(chosen: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, Any]:
    chosen = _order_for_variety(chosen)
    return {
        "name": spec["name"],
        "description": spec["description"] or "Built by Aurafy from your listening history.",
        "tracks": [_output_track(c) for c in chosen],
        "trackUris": [f"spotify:track:{c['spotify_track_id']}" for c in chosen],
    }


# --- pipeline ---------------------------------------------------------------


async def build(session: dict[str, Any], body: Any) -> dict[str, Any]:
    """Build a proposed (uncommitted) playlist from a request."""
    user_id = session["user_id"]

    # 1) INTERPRET — LLM for instruction mode, else straight from UI params.
    genre_rows = await db.get_genre_weights(user_id)
    artist_rows = await db.get_artist_weights(user_id)
    top_genres = [r["genre"] for r in genre_rows[:12]]
    top_artists = [r["name"] for r in artist_rows[:15]]

    spec: dict[str, Any] | None = None
    if getattr(body, "mode", "params") == "instruction" and (body.instruction or "").strip() and llm.is_configured():
        interpreted = await llm.interpret(body.instruction, top_genres, top_artists)
        if interpreted:
            spec = _normalize_spec(interpreted)
    if spec is None:
        spec = _spec_from_params(body)

    # With no explicit signal at all (bare params build), still give the pipeline
    # something to work with: default the vibe to the user's top genres, and seed
    # discovery from their top artists (deeper cuts), so the knobs aren't inert for
    # a solo user whose catalog is basically just their own library.
    if not spec["vibe"]:
        spec["vibe"] = ", ".join(top_genres[:8])
    if spec["mix"] > 0 and not spec["discovery_artists"]:
        spec["discovery_artists"] = top_artists[:8]

    allow_explicit = spec["allow_explicit"]
    avoid = set(spec["avoid_genres"])
    length = spec["length"]

    # 2) RETRIEVE
    owned = await db.get_library_track_ids(user_id)
    familiar = await db.get_library_candidates(user_id, allow_explicit)
    for c in familiar:
        c["kind"] = "library"

    # Embed the request's vibe once — it drives ANN retrieval AND ranks the
    # familiar half (whose taste-fit is uniformly ~1.0 and can't discriminate).
    vibe_vec: list[float] | None = None
    if spec["vibe"].strip() and embeddings.is_configured():
        vecs = await embeddings.embed_texts([spec["vibe"]])
        if vecs and vecs[0] is not None:
            vibe_vec = vecs[0]

    discovery: dict[str, dict[str, Any]] = {}

    # 2a) Catalog ANN nearest the embedded vibe.
    if vibe_vec is not None:
        for c in await db.vector_search_catalog(user_id, vibe_vec, CATALOG_K, allow_explicit):
            c["kind"] = "discovery"
            discovery[c["spotify_track_id"]] = c

    # 2b) Live Spotify search of the LLM's discovery names (persist + embed).
    live = await _live_discovery(session, spec, owned)
    await _persist_and_embed(live)
    for c in live:
        c["kind"] = "discovery"
        discovery.setdefault(c["spotify_track_id"], c)

    discovery_list = [c for c in discovery.values() if c["spotify_track_id"] not in owned]

    # 3) RERANK — enrich thin rows, taste-score everything, apply avoid-filter.
    await _enrich_genres(discovery_list)
    if avoid:
        await _infer_missing_genres(discovery_list)
    familiar = _drop_avoided(familiar, avoid)
    discovery_list = _drop_avoided(discovery_list, avoid)

    all_ids = [c["spotify_track_id"] for c in familiar + discovery_list]
    taste = await db.knn_taste_scores(user_id, all_ids, 5)
    for c in familiar + discovery_list:
        c["taste"] = taste.get(c["spotify_track_id"], 0.0)

    if vibe_vec is not None:
        # Rank both halves by how well they fit the request's vibe. Familiar
        # taste-fit is uniformly ~1.0, so vibe similarity is what makes the
        # request actually shape the familiar half; live finds have no ANN
        # similarity yet, so fill it in here too.
        vibe = await db.vibe_scores(all_ids, vibe_vec)
        for c in familiar + discovery_list:
            c["similarity"] = vibe.get(c["spotify_track_id"], c.get("similarity", 0.0))
        familiar.sort(key=lambda c: (c.get("similarity", 0.0), c.get("popularity") or 0), reverse=True)
    else:
        # No vibe (params build, no genres/description): fall back to taste-fit.
        familiar.sort(key=lambda c: (c["taste"], c.get("popularity") or 0), reverse=True)
    discovery_list.sort(key=_discovery_score, reverse=True)

    # Build the ~40-track curate pool, proportioned by mix.
    n_disc = round(CURATE_POOL * spec["mix"] / 100)
    n_fam = CURATE_POOL - n_disc
    pool = familiar[:n_fam] + discovery_list[:n_disc]
    # Backfill the pool from whichever side has extra, so it reaches CURATE_POOL.
    if len(pool) < CURATE_POOL:
        extra = familiar[n_fam:] + discovery_list[n_disc:]
        pool += extra[: CURATE_POOL - len(pool)]
    if not pool:
        raise HTTPException(status_code=422, detail="No candidates matched — try a broader request or sync your library.")
    by_id = {c["spotify_track_id"]: c for c in pool}
    for i, c in enumerate(pool, start=1):
        c["n"] = i

    # 4) CURATE — the RAG step (grounded, validated). Fallback = ranked order.
    chosen_ids: list[str] | None = None
    if llm.is_configured():
        chosen_ids = await llm.curate(pool, spec, top_artists, length)
    if not chosen_ids:
        chosen_ids = [c["spotify_track_id"] for c in _mix_order(familiar, discovery_list, spec["mix"])]

    # 5) SAFETY — validate ids, dedupe, per-artist cap, then backfill + order.
    chosen = _safety_pass([by_id[i] for i in chosen_ids if i in by_id], pool, length)
    return _finalize(chosen, spec)


def _mix_order(
    familiar: list[dict[str, Any]], discovery: list[dict[str, Any]], mix: int
) -> list[dict[str, Any]]:
    """Deterministic fallback order: interleave the two ranked pools by mix."""
    fam, disc = list(familiar), list(discovery)
    out: list[dict[str, Any]] = []
    take_disc = mix / 100.0
    acc = 0.0
    while fam or disc:
        acc += take_disc
        if disc and (acc >= 1.0 or not fam):
            out.append(disc.pop(0))
            acc -= 1.0
        elif fam:
            out.append(fam.pop(0))
        elif disc:
            out.append(disc.pop(0))
    return out


def _safety_pass(
    chosen: list[dict[str, Any]], pool: list[dict[str, Any]], length: int
) -> list[dict[str, Any]]:
    """Dedupe (id + title/artist), cap per primary artist, backfill to length."""
    per_artist_cap = max(2, round(length / 5))
    out: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    used_songs: set[tuple[str, str]] = set()
    artist_counts: dict[str, int] = {}

    def take(cands: list[dict[str, Any]], capped: bool) -> None:
        for c in cands:
            if len(out) >= length:
                return
            tid = c["spotify_track_id"]
            song = (c["title"].strip().lower(), c["artist"].strip().lower())
            if tid in used_ids or song in used_songs:
                continue
            primary = _primary_artist(c)
            if capped and artist_counts.get(primary, 0) >= per_artist_cap:
                continue
            used_ids.add(tid)
            used_songs.add(song)
            artist_counts[primary] = artist_counts.get(primary, 0) + 1
            out.append(c)

    take(chosen, capped=True)          # honor the curator's selection + order first
    take(pool, capped=True)            # backfill to length from the ranked pool
    take(pool, capped=False)           # last resort: ignore the per-artist cap
    return out


async def _infer_missing_genres(cands: list[dict[str, Any]]) -> None:
    """For candidates still lacking genres (fresh finds Spotify never tagged), ask
    Gemini for tags so the avoid-genre filter can catch them. Best-effort."""
    if not llm.is_configured():
        return
    names: set[str] = set()
    for c in cands:
        if not c.get("genres"):
            names.update(c.get("artist_name_list") or [])
    if not names:
        return
    try:
        tagged = await llm.infer_artist_genres(sorted(names))
    except Exception:
        return
    for c in cands:
        if not c.get("genres"):
            extra = {g for n in c.get("artist_name_list") or [] for g in tagged.get(n, [])}
            if extra:
                c["genres"] = sorted(extra)
