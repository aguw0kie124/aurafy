"""Agentic AI playlist builder.

Runs a Claude tool-use loop that grounds itself in the user's real listening
history (top artists/tracks/genres), searches Spotify for real playable tracks,
and converges on a curated tracklist. The loop only *proposes* a playlist; the
irreversible Spotify write happens later in the commit endpoint.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx

MODEL = "claude-opus-4-8"
MAX_ITERATIONS = 8
MAX_SEARCHES = 16
MIN_LENGTH = 5
MAX_LENGTH = 50

_client = None


def ai_is_configured() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _get_client():
    global _client
    if _client is None:
        from anthropic import Anthropic

        _client = Anthropic()
    return _client


TOOLS = [
    {
        "name": "get_taste_profile",
        "description": (
            "Get the user's real Spotify listening profile for a time range: "
            "their top artists (with genres), top tracks, and aggregated genres. "
            "Call this first to ground the playlist in what they actually listen to."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_range": {
                    "type": "string",
                    "enum": ["short_term", "medium_term", "long_term"],
                    "description": "short_term = last 4 weeks, medium_term = 6 months, long_term = all time.",
                }
            },
            "required": ["time_range"],
        },
    },
    {
        "name": "search_tracks",
        "description": (
            "Search Spotify's catalog for real, playable tracks. Returns matching "
            "tracks with their spotify_track_id, title, artist, album and popularity. "
            "Every track you put in the final playlist MUST come from these search "
            "results — never invent a track id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query, e.g. an artist name, song title, or 'genre:indie year:2020-2024'.",
                },
                "limit": {
                    "type": "integer",
                    "description": "How many results to return (1-10).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "finalize_playlist",
        "description": (
            "Submit the finished playlist. Call this exactly once when you are done "
            "curating. Every track must come from a prior search_tracks result."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "A short, catchy playlist name."},
                "description": {
                    "type": "string",
                    "description": "One-sentence playlist description (max ~250 chars).",
                },
                "tracks": {
                    "type": "array",
                    "description": "The ordered tracklist.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "spotify_track_id": {"type": "string"},
                            "title": {"type": "string"},
                            "artist": {"type": "string"},
                            "reason": {
                                "type": "string",
                                "description": "One short phrase on why this track fits.",
                            },
                        },
                        "required": ["spotify_track_id", "title", "artist", "reason"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["name", "description", "tracks"],
            "additionalProperties": False,
        },
    },
]


def _build_system_prompt(opts: dict[str, Any]) -> str:
    length = opts["length"]
    discovery = opts["mix"]  # 0 = only familiar artists, 100 = mostly new artists
    explicit = "allowed" if opts["allow_explicit"] else "NOT allowed — exclude explicit tracks"
    return (
        "You are Aurafy's expert music curator. You build a Spotify playlist for the "
        "user from their request and their real listening history.\n\n"
        "Workflow:\n"
        "1. Call get_taste_profile to learn their top artists, tracks, and genres.\n"
        "2. Use search_tracks across several focused queries to gather real, playable "
        "candidate tracks. Search for specific artists and songs, not just broad genres.\n"
        "3. When the playlist is cohesive and the right length, call finalize_playlist "
        "exactly once.\n\n"
        "Curation rules:\n"
        f"- Target about {length} tracks.\n"
        f"- Discovery balance: {discovery}/100 (0 = stick to artists they already love, "
        "100 = mostly new artists that match the vibe). Blend accordingly.\n"
        f"- Explicit content is {explicit}.\n"
        "- Honor the user's described mood, theme, and any constraints above all else.\n"
        "- Keep the playlist cohesive in energy and vibe; avoid duplicate tracks.\n"
        "- Every track in finalize_playlist MUST be one you found via search_tracks."
    )


async def _run_get_taste_profile(
    client: httpx.AsyncClient, access_token: str, time_range: str
) -> str:
    from .main import artist_names, normalize_range, spotify_get

    normalized = normalize_range(time_range)
    top_tracks, top_artists = await asyncio.gather(
        spotify_get(client, "/me/top/tracks", access_token, {"time_range": normalized, "limit": 30}),
        spotify_get(client, "/me/top/artists", access_token, {"time_range": normalized, "limit": 30}),
    )

    artist_items = top_artists.get("items") or []
    track_items = top_tracks.get("items") or []

    genre_counts: dict[str, int] = {}
    for artist in artist_items:
        for genre in artist.get("genres") or []:
            genre_counts[genre] = genre_counts.get(genre, 0) + 1
    top_genres = [g for g, _ in sorted(genre_counts.items(), key=lambda kv: -kv[1])[:12]]

    return json.dumps(
        {
            "topArtists": [
                {"name": a.get("name"), "genres": (a.get("genres") or [])[:4]}
                for a in artist_items
            ],
            "topTracks": [
                {"title": t.get("name"), "artist": artist_names(t)} for t in track_items
            ],
            "topGenres": top_genres,
        }
    )


async def _run_search_tracks(
    client: httpx.AsyncClient,
    access_token: str,
    query: str,
    limit: int,
    seen: dict[str, dict[str, Any]],
) -> str:
    from .main import artist_names, spotify_get

    limit = max(1, min(int(limit or 8), 10))
    payload = await spotify_get(
        client, "/search", access_token, {"q": query, "type": "track", "limit": limit}
    )
    items = ((payload.get("tracks") or {}).get("items")) or []

    results = []
    for track in items:
        track_id = track.get("id")
        if not track_id:
            continue
        meta = {
            "spotify_track_id": track_id,
            "title": track.get("name") or "Unknown track",
            "artist": artist_names(track),
            "album": (track.get("album") or {}).get("name"),
            "popularity": track.get("popularity"),
            "explicit": bool(track.get("explicit")),
        }
        seen[track_id] = meta
        results.append(meta)

    return json.dumps(results)


async def generate_playlist(
    session: dict[str, Any], prompt: str, opts: dict[str, Any]
) -> dict[str, Any]:
    """Run the agentic loop and return a proposed (uncommitted) playlist."""
    from .main import refresh_access_token, to_track_response

    length = max(MIN_LENGTH, min(int(opts.get("length", 25)), MAX_LENGTH))
    opts = {
        "length": length,
        "mix": max(0, min(int(opts.get("mix", 30)), 100)),
        "allow_explicit": bool(opts.get("allow_explicit", True)),
        "range": opts.get("range", "medium_term"),
    }

    client = _get_client()
    access_token = await refresh_access_token(session)
    seen: dict[str, dict[str, Any]] = {}
    finalized: dict[str, Any] | None = None
    search_count = 0

    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt.strip()}]
    system_prompt = _build_system_prompt(opts)

    async with httpx.AsyncClient(timeout=20) as http:
        for _ in range(MAX_ITERATIONS):
            response = await asyncio.to_thread(
                client.messages.create,
                model=MODEL,
                max_tokens=4096,
                thinking={"type": "adaptive"},
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            )
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                break

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                if block.name == "get_taste_profile":
                    content = await _run_get_taste_profile(
                        http, access_token, block.input.get("time_range", opts["range"])
                    )
                elif block.name == "search_tracks":
                    if search_count >= MAX_SEARCHES:
                        content = json.dumps({"error": "search limit reached, finalize now"})
                    else:
                        search_count += 1
                        content = await _run_search_tracks(
                            http,
                            access_token,
                            block.input.get("query", ""),
                            block.input.get("limit", 8),
                            seen,
                        )
                elif block.name == "finalize_playlist":
                    finalized = block.input
                    content = "Playlist recorded."
                else:
                    content = json.dumps({"error": f"unknown tool {block.name}"})

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

            if finalized is not None:
                break

        if finalized is None:
            raise RuntimeError("The curator did not finish a playlist. Try a more specific prompt.")

        # Keep only real, de-duplicated tracks the agent actually searched for.
        ordered_ids: list[str] = []
        reasons: dict[str, str] = {}
        for entry in finalized.get("tracks") or []:
            track_id = entry.get("spotify_track_id")
            if not track_id or track_id not in seen or track_id in reasons:
                continue
            if not opts["allow_explicit"] and seen[track_id].get("explicit"):
                continue
            ordered_ids.append(track_id)
            reasons[track_id] = entry.get("reason") or ""
        ordered_ids = ordered_ids[:length]

        if not ordered_ids:
            raise RuntimeError("No playable tracks resolved. Try a more specific prompt.")

        # Hydrate fresh track objects (cover art etc.) in one batch.
        hydrated = await spotify_get_tracks(http, access_token, ordered_ids)

    tracks = []
    for rank, track_id in enumerate(ordered_ids, start=1):
        raw = hydrated.get(track_id)
        if raw is None:
            continue
        card = to_track_response(raw, rank)
        card["reason"] = reasons.get(track_id, "")
        tracks.append(card)

    return {
        "name": (finalized.get("name") or "Aurafy Mix").strip()[:100],
        "description": (finalized.get("description") or "").strip()[:300],
        "tracks": tracks,
        "trackUris": [f"spotify:track:{track_id}" for track_id in ordered_ids],
    }


async def spotify_get_tracks(
    client: httpx.AsyncClient, access_token: str, track_ids: list[str]
) -> dict[str, dict[str, Any]]:
    from .main import spotify_get

    if not track_ids:
        return {}
    payload = await spotify_get(
        client, "/tracks", access_token, {"ids": ",".join(track_ids[:50])}
    )
    return {t["id"]: t for t in (payload.get("tracks") or []) if t and t.get("id")}
