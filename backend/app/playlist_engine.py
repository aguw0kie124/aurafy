"""Deterministic playlist engine.

Turns a ``PlaylistSpec`` (produced either directly from UI parameters or by the
Gemini natural-language layer) into an ordered list of real, playable tracks.

It never invents tracks: candidates come only from the user's stored library
(``db`` queries) and live Spotify calls (genre search + artist top-tracks). The
LLM layer produces the spec but never touches tracks, so hallucination is
impossible by construction.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx
from fastapi import HTTPException

from . import db, playlist_agent

MIN_LENGTH = 5
MAX_LENGTH = 50
DEFAULT_LENGTH = 25

DISCOVERY_GENRE_SEARCHES = 4   # how many focus genres to search Spotify for
DISCOVERY_ARTISTS = 6          # how many artists to search tracks for
CROSS_USER_LIMIT = 100
# Development-mode Spotify apps (post-Nov-2024 restrictions) reject search
# limits above 10 and 403 on /artists/{id}/top-tracks, so discovery uses
# offset-paged /search exclusively.
SEARCH_PAGE_LIMIT = 10
SEARCH_PAGES = 2               # pages per query -> up to 20 tracks each

# Scoring weights.
W_GENRE = 1.0
W_ARTIST = 1.5
W_POPULARITY = 0.3
W_SEED = 2.0         # explicit "sounds like X" artists outrank everything
W_RECOMMENDED = 1.8  # AI-curated picks beat the listener's own artists' deep cuts

# When the AI curator supplies discovery ideas, only lightly top up with the
# listener's own top artists — the point of discovery is new names.
TOP_ARTISTS_WITH_IDEAS = 2
SEARCH_CONCURRENCY = 6


def normalize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Clamp/normalize a raw spec dict into safe engine inputs."""
    length = int(spec.get("length") or DEFAULT_LENGTH)
    length = max(MIN_LENGTH, min(length, MAX_LENGTH))
    mix = int(spec.get("mix") if spec.get("mix") is not None else 30)
    mix = max(0, min(mix, 100))
    genres = [g.strip().lower() for g in (spec.get("genres") or []) if isinstance(g, str) and g.strip()]
    avoid = [g.strip().lower() for g in (spec.get("avoid_genres") or []) if isinstance(g, str) and g.strip()]
    seeds = [s for s in (spec.get("seed_artist_names") or []) if isinstance(s, str) and s.strip()]
    return {
        "name": (spec.get("name") or "").strip() or "Aurafy Mix",
        "description": (spec.get("description") or "").strip(),
        "length": length,
        "mix": mix,
        "allow_explicit": bool(spec.get("allow_explicit", True)),
        "genres": genres[:8],
        "avoid_genres": avoid[:8],
        "seed_artist_names": seeds[:5],
    }


def _normalized_weights(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    if not rows:
        return {}
    top = max(r["weight"] for r in rows) or 1.0
    return {r[key]: r["weight"] / top for r in rows}


def _cand_from_spotify(track: dict[str, Any], genres_hint: list[str]) -> dict[str, Any]:
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
        "artist_ids": [a["id"] for a in (track.get("artists") or []) if a.get("id")],
        "artist_name_list": [a["name"] for a in (track.get("artists") or []) if a.get("name")],
        "genres": list(genres_hint),
    }


def _score(cand: dict[str, Any], genre_w: dict[str, float], artist_w: dict[str, float]) -> float:
    genre_overlap = sum(genre_w.get(g, 0.0) for g in cand["genres"])
    artist_affinity = max((artist_w.get(a, 0.0) for a in cand["artist_ids"]), default=0.0)
    popularity = (cand.get("popularity") or 0) / 100.0
    seed = W_SEED if cand.get("from_seed") else 0.0
    recommended = W_RECOMMENDED if cand.get("recommended") else 0.0
    jitter = random.uniform(0.0, 0.02)  # break ties, add variety across builds
    return (
        W_GENRE * genre_overlap + W_ARTIST * artist_affinity + W_POPULARITY * popularity
        + seed + recommended + jitter
    )


def _primary_artist(cand: dict[str, Any]) -> str:
    return cand["artist_ids"][0] if cand["artist_ids"] else cand["artist"]


def _matches_any(genre: str, terms: set[str]) -> bool:
    """Word-boundary match so avoiding "rap" hits "pop rap" but not "trap"."""
    padded = f" {genre} "
    return any(f" {term} " in padded for term in terms)


def _drop_avoided(cands: list[dict[str, Any]], avoid: set[str]) -> list[dict[str, Any]]:
    return [c for c in cands if not any(_matches_any(g.lower(), avoid) for g in c["genres"])]


def _order_for_variety(cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Greedily avoid placing two tracks by the same primary artist back to back."""
    remaining = list(cands)
    ordered: list[dict[str, Any]] = []
    while remaining:
        prev = _primary_artist(ordered[-1]) if ordered else None
        pick = next((c for c in remaining if _primary_artist(c) != prev), remaining[0])
        ordered.append(pick)
        remaining.remove(pick)
    return ordered


async def _search_tracks(
    client: httpx.AsyncClient, token: str, query: str, pages: int = SEARCH_PAGES
) -> list[dict[str, Any]]:
    """Offset-paged track search within the dev-mode limit cap."""
    from .main import spotify_get

    tracks: list[dict[str, Any]] = []
    for page in range(pages):
        try:
            resp = await spotify_get(
                client,
                "/search",
                token,
                {
                    "q": query,
                    "type": "track",
                    "limit": SEARCH_PAGE_LIMIT,
                    "offset": page * SEARCH_PAGE_LIMIT,
                },
            )
        except HTTPException:
            break
        batch = (resp.get("tracks") or {}).get("items") or []
        tracks.extend(t for t in batch if t and t.get("id"))
        if len(batch) < SEARCH_PAGE_LIMIT:
            break
    return tracks


async def _gather_discovery(
    client: httpx.AsyncClient,
    token: str,
    focus_genres: list[str],
    artist_names: list[str],
    seed_names: list[str],
    idea_artists: list[str],
    idea_tracks: list[dict[str, str]],
    allow_explicit: bool,
) -> list[dict[str, Any]]:
    # (query, pages, first-result-only, genres hint, flags to set on candidates)
    searches: list[tuple[str, int, bool, list[str], dict[str, bool]]] = []
    for name in artist_names:
        flags = {"from_seed": True} if name in seed_names else {}
        searches.append((f'artist:"{name}"', SEARCH_PAGES, False, [], flags))
    for name in idea_artists:
        searches.append((f'artist:"{name}"', SEARCH_PAGES, False, [], {"recommended": True}))
    for idea in idea_tracks:
        query = f'track:"{idea["title"]}" artist:"{idea["artist"]}"'
        searches.append((query, 1, True, [], {"recommended": True}))
    for genre in focus_genres[:DISCOVERY_GENRE_SEARCHES]:
        searches.append((f'genre:"{genre}"', SEARCH_PAGES, False, [genre], {}))

    sem = asyncio.Semaphore(SEARCH_CONCURRENCY)

    async def run(query: str, pages: int) -> list[dict[str, Any]]:
        async with sem:
            return await _search_tracks(client, token, query, pages)

    results = await asyncio.gather(*(run(q, pages) for q, pages, *_ in searches))

    found: dict[str, dict[str, Any]] = {}
    for (query, pages, first_only, genres_hint, flags), tracks in zip(searches, results):
        for track in tracks[:1] if first_only else tracks:
            cand = found.setdefault(track["id"], _cand_from_spotify(track, genres_hint))
            if genres_hint and not cand["genres"]:
                cand["genres"] = list(genres_hint)
            for flag in flags:
                cand[flag] = True

    candidates = list(found.values())
    if not allow_explicit:
        candidates = [c for c in candidates if not c["explicit"]]
    return candidates


def _output_track(cand: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "spotifyTrackId": cand["spotify_track_id"],
        "title": cand["title"],
        "artist": cand["artist"],
        "album": cand["album"] or "Unknown album",
        "coverUrl": cand["image_url"],
        "externalUrl": cand["external_url"],
        "source": source,
    }


async def build(session: dict[str, Any], raw_spec: dict[str, Any]) -> dict[str, Any]:
    """Build a proposed (uncommitted) playlist from a spec."""
    from .main import refresh_access_token

    spec = normalize_spec(raw_spec)
    user_id = session["user_id"]
    allow_explicit = spec["allow_explicit"]

    genre_rows = await db.get_genre_weights(user_id)
    artist_rows = await db.get_artist_weights(user_id)
    genre_w = _normalized_weights(genre_rows, "genre")
    artist_w = _normalized_weights(artist_rows, "spotify_artist_id")

    avoid = set(spec["avoid_genres"])
    focus_genres = spec["genres"] or [
        r["genre"] for r in genre_rows if not _matches_any(r["genre"], avoid)
    ][:5]
    library_ids = await db.get_library_track_ids(user_id)

    # Familiar pool (from the stored library). Genre filtering is soft: many
    # Spotify apps get no artist-genre data, so if the filter empties the pool
    # we keep the unfiltered library rather than dropping the familiar half.
    familiar = await db.get_library_candidates(user_id, allow_explicit)
    if spec["genres"]:
        wanted = set(spec["genres"])
        filtered = [c for c in familiar if wanted & {g.lower() for g in c["genres"]}]
        if filtered:
            familiar = filtered

    # Discovery pool (live Spotify + cross-user), excluding anything already owned.
    # Skipped entirely for a pure-library build (mix == 0) so it stays offline.
    discovery: list[dict[str, Any]] = []
    known: dict[str, list[str]] = {}  # artist id -> DB genre tags
    if spec["mix"] > 0:
        seed_names = spec["seed_artist_names"]
        top_names = [r["name"] for r in artist_rows if r["name"] not in seed_names]

        # Ask the AI curator for artists/songs OUTSIDE the listener's orbit
        # (replaces Spotify's dead /recommendations endpoint). Best-effort:
        # any failure just falls back to plain search discovery.
        ideas: dict[str, Any] | None = None
        if playlist_agent.ai_is_configured():
            try:
                ideas = await playlist_agent.discovery_ideas(
                    spec,
                    [r["genre"] for r in genre_rows[:12]],
                    top_names[:15],
                )
            except Exception:
                ideas = None
        idea_artists = (ideas or {}).get("artists") or []
        idea_tracks = (ideas or {}).get("tracks") or []

        # With curated ideas in hand, the listener's own top artists are only a
        # light top-up; without them they carry discovery like before.
        top_take = TOP_ARTISTS_WITH_IDEAS if idea_artists else DISCOVERY_ARTISTS
        discovery_artists = seed_names + top_names[:top_take]

        access_token = await refresh_access_token(session)
        async with httpx.AsyncClient(timeout=30) as client:
            discovery = await _gather_discovery(
                client,
                access_token,
                focus_genres,
                discovery_artists,
                seed_names,
                idea_artists,
                idea_tracks,
                allow_explicit,
            )
        discovery += await db.get_cross_user_candidates(user_id, allow_explicit, CROSS_USER_LIMIT)
        seen_disc: dict[str, dict[str, Any]] = {}
        for c in discovery:
            if c["spotify_track_id"] not in library_ids:
                seen_disc.setdefault(c["spotify_track_id"], c)
        discovery = list(seen_disc.values())

        # Live-search candidates arrive with at most a search-hint genre, which
        # can mask what the artist actually is (Drake surfacing in an "r&b"
        # search). Merge in everything the DB knows about their artists so
        # avoid-filtering and scoring see the full picture.
        all_ids = sorted({a for c in discovery for a in c["artist_ids"]})
        known = await db.get_genres_for_artist_ids(all_ids) if all_ids else {}
        for c in discovery:
            merged = set(c["genres"]) | {g for a in c["artist_ids"] for g in known.get(a, [])}
            c["genres"] = sorted(merged)

    # Exclusions are hard: "no rap" must hold even if it empties a pool
    # (discovery/backfill then covers the shortfall).
    if avoid:
        # Artists the DB has never seen (fresh curator/search finds) have no
        # tags for the filter to catch — tag them in-memory with one Gemini
        # call before filtering.
        unknown_names: set[str] = set()
        for c in discovery:
            if any(a not in known for a in c["artist_ids"]):
                unknown_names.update(c.get("artist_name_list") or [])
        if unknown_names and playlist_agent.ai_is_configured():
            try:
                tagged = await playlist_agent.infer_artist_genres(sorted(unknown_names))
            except Exception:
                tagged = {}
            for c in discovery:
                extra = {g for n in c.get("artist_name_list") or [] for g in tagged.get(n, [])}
                if extra:
                    c["genres"] = sorted(set(c["genres"]) | extra)
        familiar = _drop_avoided(familiar, avoid)
        discovery = _drop_avoided(discovery, avoid)

    for pool in (familiar, discovery):
        pool.sort(key=lambda c: _score(c, genre_w, artist_w), reverse=True)

    # Split by mix, then backfill from whichever pool has extra.
    length = spec["length"]
    n_disc = round(length * spec["mix"] / 100)
    n_fam = length - n_disc
    chosen: list[dict[str, Any]] = []
    used: set[str] = set()
    # Also dedupe by title+artist: the same song often exists under several
    # track ids (single vs. album release).
    used_songs: set[tuple[str, str]] = set()
    # Cap tracks per primary artist so one heavy favorite can't fill the list;
    # the uncapped backfill pass still lets short pools reach the target length.
    per_artist_cap = max(2, round(length / 5))
    artist_counts: dict[str, int] = {}

    def take(pool: list[dict[str, Any]], count: int, source: str, capped: bool = True) -> None:
        for cand in pool:
            if len(chosen) >= length or count <= 0:
                break
            song_key = (cand["title"].strip().lower(), cand["artist"].strip().lower())
            if cand["spotify_track_id"] in used or song_key in used_songs:
                continue
            primary = _primary_artist(cand)
            if capped and artist_counts.get(primary, 0) >= per_artist_cap:
                continue
            artist_counts[primary] = artist_counts.get(primary, 0) + 1
            used.add(cand["spotify_track_id"])
            used_songs.add(song_key)
            if source == "discovery" and cand.get("recommended"):
                cand["_source"] = "curated"
            else:
                cand["_source"] = source
            chosen.append(cand)
            count -= 1

    take(familiar, n_fam, "library")
    take(discovery, n_disc, "discovery")
    # Backfill to reach the target length from either pool, capped first.
    take(familiar, length - len(chosen), "library")
    take(discovery, length - len(chosen), "discovery")
    take(familiar, length - len(chosen), "library", capped=False)
    take(discovery, length - len(chosen), "discovery", capped=False)

    chosen = _order_for_variety(chosen)

    tracks = [_output_track(c, c["_source"]) for c in chosen]
    track_uris = [f"spotify:track:{c['spotify_track_id']}" for c in chosen]
    description = spec["description"] or "Built by Aurafy from your listening history."
    return {
        "name": spec["name"],
        "description": description,
        "tracks": tracks,
        "trackUris": track_uris,
    }
