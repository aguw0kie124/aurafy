"""The recommender. Two features, deliberately two different shapes.

THE FEED (``recommend``) — "For You" shelves. There is no stated intent to satisfy,
just "more of what this person likes", which is a pure retrieval problem: k-means
over the user's library embeddings finds their taste modes, and each cluster's
centroid drives an ANN search over the catalog. No LLM curation — with no request to
reason about, it would have nothing to add.

THE PLAYLIST BUILDER (``build``) — "describe a playlist". Here there IS stated intent,
with nuance a single vector flattens ("upbeat but not too aggressive, for a workout"),
which is what earns the generation step:

    interpret -> retrieve -> curate (RAG) -> safety

1. INTERPRET: ``llm.interpret`` turns the request into a spec + one "vibe" sentence.
2. RETRIEVE: grow the catalog first (``llm.discovery_ideas`` -> live Spotify search ->
   persist + embed), so fresh finds are already in the index; then ONE ANN query for
   the tracks nearest the embedded vibe. Owned and unowned tracks share the table and
   the embedding space, so a single search covers both and each row is tagged
   familiar/discovery afterwards. kNN taste-fit rides along as a column.
3. CURATE (the RAG step): ``llm.curate`` picks and orders the playlist from those
   retrieved rows; returned ids are validated against the supplied set, so nothing
   invented survives.
4. SAFETY: avoid-genre filter, title+artist dedupe, per-artist cap, variety order.

Gemini is required, not optional: interpret/discovery/curate failures raise rather
than falling back to a second, weaker implementation of the same feature.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import numpy as np
from fastapi import HTTPException

from . import db, embeddings, llm

MIN_LENGTH, MAX_LENGTH, DEFAULT_LENGTH = 5, 50, 25


def _mean(vectors: list[list[float]]) -> list[float]:
    """Centroid of a set of embedding vectors."""
    return np.asarray(vectors, dtype=float).mean(axis=0).tolist()


CATALOG_K = 60          # ANN candidates pulled near the vibe vector
CURATE_POOL = 40        # retrieved tracks handed to the LLM curator
# Dev-mode Spotify apps reject search limits above 10, so page with offset.
SEARCH_PAGE_LIMIT = 10
SEARCH_PAGES = 2        # up to 20 tracks per query
SEARCH_CONCURRENCY = 6


# --- spec ------------------------------------------------------------------


def _normalize_spec(spec: dict[str, Any], length: int) -> dict[str, Any]:
    """Clamp the LLM's raw spec into safe pipeline inputs. ``length`` comes from the
    UI's own dropdown, never the model — the user already picked a number, so asking
    the model to guess one only creates a way to ignore them."""
    length = max(MIN_LENGTH, min(int(length or DEFAULT_LENGTH), MAX_LENGTH))
    genres = [g.strip().lower() for g in (spec.get("genres") or []) if isinstance(g, str) and g.strip()]
    avoid = [g.strip().lower() for g in (spec.get("avoid_genres") or []) if isinstance(g, str) and g.strip()]
    return {
        "name": (spec.get("name") or "").strip() or "Aurafy Mix",
        "description": (spec.get("description") or "").strip(),
        "length": length,
        "allow_explicit": bool(spec.get("allow_explicit", True)),
        "genres": genres[:8],
        "avoid_genres": avoid[:8],
        "vibe": (spec.get("vibe") or "").strip(),
    }


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


async def _resolve_names(
    session: dict[str, Any],
    artists: list[str],
    tracks: list[dict[str, str]],
    owned: set[str],
    allow_explicit: bool,
) -> list[dict[str, Any]]:
    """Resolve LLM-suggested artist/track NAMES through live Spotify search into real,
    non-owned candidate tracks. A name that doesn't exist simply finds nothing, which
    is what keeps invented suggestions out of the catalog."""
    from .main import refresh_access_token

    if not artists and not tracks:
        return []
    queries = [f'artist:"{n}"' for n in artists[:10]]
    queries += [f'track:"{t["title"]}" artist:"{t["artist"]}"' for t in tracks[:10]]

    token = await refresh_access_token(session)
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
    if not allow_explicit:
        cands = [c for c in cands if not c["explicit"]]
    return cands


async def grow_catalog(
    session: dict[str, Any],
    top_artists: list[str],
    owned: set[str],
    allow_explicit: bool,
    vibe: str = "",
) -> list[dict[str, Any]]:
    """The one way new music enters the catalog, shared by the feed and the playlist
    builder. Spotify's /recommendations endpoint is dead for dev-mode apps, so instead:
    ask Gemini to NAME artists/tracks this listener probably doesn't know, confirm each
    name is real via Spotify search, then persist + embed the survivors. Because the
    embedding happens here, the finds are ANN-retrievable immediately after this returns."""
    ideas = await llm.discovery_ideas(top_artists, vibe)
    found = await _resolve_names(session, ideas["artists"], ideas["tracks"], owned, allow_explicit)
    await _persist_and_embed(found)
    return found


async def _persist_and_embed(cands: list[dict[str, Any]]) -> None:
    """Persist live finds into the shared catalog and embed them inline, so the very
    next ANN query can retrieve them (the discovery flywheel)."""
    if not cands:
        return
    artists: dict[str, dict[str, Any]] = {}
    track_artists: list[tuple[str, str, int]] = []
    for c in cands:
        for pos, (aid, name) in enumerate(zip(c["artist_ids"], c["artist_name_list"])):
            artists.setdefault(aid, {"spotify_artist_id": aid, "name": name})
            track_artists.append((c["spotify_track_id"], aid, pos))
    await db.upsert_catalog_tracks(list(artists.values()), cands, track_artists)
    docs = [embeddings.track_doc(c) for c in cands]
    vecs = await embeddings.embed_texts(docs)
    pairs = [(c["spotify_track_id"], v) for c, v in zip(cands, vecs) if v is not None]
    if pairs:
        await db.store_track_embeddings(pairs)


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
    """Build a proposed (uncommitted) playlist from a free-text request."""
    user_id = session["user_id"]
    instruction = (body.instruction or "").strip()
    if not instruction:
        raise HTTPException(status_code=422, detail="Describe the playlist you want.")

    artist_rows = await db.get_artist_weights(user_id)
    top_artists = [r["name"] for r in artist_rows[:15]]

    # 1) INTERPRET — the request becomes a spec plus one "vibe" sentence, which is
    #    the only thing retrieval actually queries on.
    spec = _normalize_spec(await llm.interpret(instruction, top_artists), body.length)
    if not spec["vibe"]:
        spec["vibe"] = instruction
    allow_explicit = spec["allow_explicit"]
    avoid = set(spec["avoid_genres"])
    length = spec["length"]

    # 2) RETRIEVE. Grow the catalog FIRST — `grow_catalog` embeds what it finds, so
    #    those tracks are already in the HNSW index when the ANN query runs a moment
    #    later and need no separate merge/score path of their own.
    owned = await db.get_library_track_ids(user_id)
    await grow_catalog(session, top_artists, owned, allow_explicit, vibe=spec["vibe"])

    vibe_vec = await embeddings.embed_query(spec["vibe"])

    # One search over everything. The user's own tracks and the wider catalog share a
    # table and an embedding space, so whatever genuinely sits nearest the vibe wins;
    # ownership only decides how a row is labelled, not whether it can be picked.
    pool = await db.vector_search_catalog(
        user_id, vibe_vec, CURATE_POOL, allow_explicit, exclude_owned=False
    )
    for c in pool:
        c["kind"] = "familiar" if c["spotify_track_id"] in owned else "discovery"

    await _enrich_genres(pool)
    if avoid:
        await _infer_missing_genres(pool)
        pool = _drop_avoided(pool, avoid)
    if not pool:
        raise HTTPException(status_code=422, detail="No candidates matched — try a broader request or sync your library.")

    # kNN taste-fit rides along as a column for the curator to weigh — it is not a
    # separate ranking stage; ANN order is the ranking.
    taste = await db.knn_taste_scores(user_id, [c["spotify_track_id"] for c in pool], 5)
    for i, c in enumerate(pool, start=1):
        c["taste"] = taste.get(c["spotify_track_id"], 0.0)
        c["n"] = i
    by_id = {c["spotify_track_id"]: c for c in pool}

    # 3) CURATE — the RAG step. The model only ever returns numbers from the list it
    #    was shown, and unknown numbers are dropped, so an invented track cannot survive.
    chosen_ids = await llm.curate(pool, spec, top_artists, length)

    # 4) SAFETY — dedupe, per-artist cap, backfill to length, variety order.
    chosen = _safety_pass([by_id[i] for i in chosen_ids if i in by_id], pool, length)
    return _finalize(chosen, spec)


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
    """Tag candidates that still have no genres so the avoid-genre filter can catch
    them. This is the app's only genre source — Spotify exposes no ``genres`` field to
    dev-mode apps, so without this "no rap" would match nothing and filter nothing.
    Best-effort by design: a tagging failure costs precision on one request, and is
    not worth failing the whole build over."""
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


# --- For You feed (one saveable playlist per taste mode) ---------------------

PLAYLIST_LEN = 25       # tracks per curated playlist
MAX_CLUSTERS = 6        # taste-mode playlists
# Each playlist takes PLAYLIST_LEN off a shared pool (tracks are deduped across the
# whole feed, not just within a playlist), so pull deep enough that the last cluster
# still clears the keep threshold.
NEAR_K = 80             # candidates pulled per ANN query before dedupe/cap

# The feed is ~20s to build (live discovery + Spotify search), so cache it per user
# and serve instantly on revisits; the Refresh button (force=True) rebuilds on demand.
FEED_TTL = 1800         # seconds a cached feed stays fresh (30 min)
_feed_cache: dict[str, dict[str, Any]] = {}


def invalidate_feed(user_id: str) -> None:
    """Drop a user's cached feed (e.g. after a library sync) so the next visit rebuilds."""
    _feed_cache.pop(user_id, None)


def _dedupe_cap(
    cands: list[dict[str, Any]],
    n: int,
    seen_ids: set[str] | None = None,
    seen_songs: set[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Dedupe (id + title/artist), cap per primary artist, order for variety, take n.

    Pass ``seen_ids``/``seen_songs`` to share dedupe state across calls — the feed
    threads one pair through every playlist so the same track can't surface in two
    rows. The per-artist cap stays per-call: capping an artist within a row is the
    point, capping them across the whole feed is not."""
    per_artist_cap = max(2, round(n / 5))
    out: list[dict[str, Any]] = []
    ids = seen_ids if seen_ids is not None else set()
    songs = seen_songs if seen_songs is not None else set()
    counts: dict[str, int] = {}
    for c in cands:
        if len(out) >= n:
            break
        tid = c["spotify_track_id"]
        song = (c["title"].strip().lower(), c["artist"].strip().lower())
        if tid in ids or song in songs:
            continue
        primary = _primary_artist(c)
        if counts.get(primary, 0) >= per_artist_cap:
            continue
        ids.add(tid)
        songs.add(song)
        counts[primary] = counts.get(primary, 0) + 1
        out.append(c)
    return _order_for_variety(out)


def _nearest_by_cosine(
    X: "np.ndarray", idx: list[int], centroid: "np.ndarray", k: int
) -> list[int]:
    """The k members of ``idx`` closest to ``centroid`` by *cosine* distance — the same
    geometry pgvector uses for the ANN query these centroids seed."""
    members = X[idx]
    norms = np.linalg.norm(members, axis=1)
    sims = (members @ centroid) / np.where(norms == 0, 1.0, norms)
    return [idx[i] for i in np.argsort(-sims)[:k]]


def _cluster_name(reps: list[dict[str, str]], fallback: str) -> str:
    """Name a taste mode after its two most representative distinct artists.

    ``artist`` is every credited name comma-joined ("Chief Keef, Tray Savage, Tadoe"),
    so take each rep's *lead* artist — joining the raw strings reads as a credits list,
    not a name."""
    artists: list[str] = []
    seen: set[str] = set()
    for rep in reps:
        lead = (rep.get("artist") or "").split(",")[0].strip()
        if lead and lead.lower() not in seen:
            seen.add(lead.lower())
            artists.append(lead)
        if len(artists) == 2:
            break
    return f"{', '.join(artists)} & similar" if artists else fallback


def _library_clusters(lib: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """k-means over the user's library vectors → distinct taste modes. Each cluster:
    ``{centroid, size, representative_tracks}`` (the members nearest the centroid, used
    to name + seed a playlist). A small library collapses to a single centroid."""
    if not lib:
        return []
    vecs = [t["embedding"] for t in lib]
    n = len(lib)
    if n < 15:
        return [{
            "centroid": _mean(vecs),
            "size": n,
            "representative_tracks": [{"title": t["title"], "artist": t["artist"]} for t in lib[:5]],
        }]
    from sklearn.cluster import KMeans

    X = np.asarray(vecs, dtype=float)
    k = min(7, max(2, n // 25))
    labels = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(X)
    clusters: list[dict[str, Any]] = []
    for ci in range(k):
        idx = [i for i, lbl in enumerate(labels) if lbl == ci]
        if not idx:
            continue
        centroid = X[idx].mean(axis=0)
        nearest = _nearest_by_cosine(X, idx, centroid, 5)
        clusters.append({
            "centroid": centroid.tolist(),
            "size": len(idx),
            "representative_tracks": [
                {"title": lib[i]["title"], "artist": lib[i]["artist"]} for i in nearest
            ],
        })
    # Biggest taste modes first.
    clusters.sort(key=lambda c: c["size"], reverse=True)
    return clusters


async def recommend(session: dict[str, Any], force: bool = False) -> dict[str, Any]:
    """The For You feed: one saveable playlist per k-means taste mode, plus Fresh Finds.
    No LLM curation here — with no request to reason about, retrieval IS the answer:
    each shelf is an ANN slice around one cluster centroid. Cached per user for
    FEED_TTL; ``force=True`` (the Refresh button) rebuilds."""
    user_id = session["user_id"]
    if not force:
        cached = _feed_cache.get(user_id)
        if cached and (time.monotonic() - cached["at"]) < FEED_TTL:
            return cached["feed"]
    allow_explicit = True

    owned = await db.get_library_track_ids(user_id)
    artist_rows = await db.get_artist_weights(user_id)
    top_artists = [r["name"] for r in artist_rows[:15]]

    # 1) Grow the catalog from this user's taste, so the ANN slices below have new
    #    music to find. Same single path the playlist builder uses, minus a vibe.
    pool = await grow_catalog(session, top_artists, owned, allow_explicit)
    await _enrich_genres(pool)
    for c in pool:
        c["kind"] = "discovery"

    # 2) Curated playlists — one per taste mode (deterministic) + Fresh Finds. Named
    #    statically from each mode's most representative artists (no LLM naming call).
    #    Nearby centroids pull overlapping candidates, so dedupe state is shared across
    #    every playlist: no track appears twice anywhere in the feed.
    playlists: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_songs: set[tuple[str, str]] = set()
    clusters = _library_clusters(await db.get_user_library_vectors(user_id))
    for i, cl in enumerate(clusters[:MAX_CLUSTERS]):
        near = await db.vector_search_catalog(user_id, cl["centroid"], NEAR_K, allow_explicit)
        tracks = _dedupe_cap(
            [{**c, "kind": "discovery"} for c in near], PLAYLIST_LEN, seen_ids, seen_songs
        )
        if len(tracks) >= 8:
            name = _cluster_name(cl["representative_tracks"], f"Taste Mix {i + 1}")
            playlists.append(_playlist_shape(f"cluster_{i}", "A slice of your taste", tracks, name=name))

    # Fresh Finds — the freshest picks (popular new tracks you don't own).
    fresh = _dedupe_cap(
        sorted(pool, key=lambda c: (c.get("popularity") or 0), reverse=True),
        PLAYLIST_LEN,
        seen_ids,
        seen_songs,
    )
    if len(fresh) >= 8:
        playlists.append(_playlist_shape("fresh_finds", "New music picked for you", fresh, name="Fresh Finds"))

    result = {"playlists": playlists}
    _feed_cache[user_id] = {"feed": result, "at": time.monotonic()}
    return result


def _playlist_shape(
    key: str, description: str, tracks: list[dict[str, Any]], name: str | None = None
) -> dict[str, Any]:
    out = [_output_track(c) for c in tracks]
    return {
        "key": key,
        "name": name,
        "description": description,
        "coverUrl": out[0]["coverUrl"] if out else None,
        "tracks": out,
        "trackUris": [f"spotify:track:{t['spotifyTrackId']}" for t in out],
    }
