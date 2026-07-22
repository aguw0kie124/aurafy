"""Natural-language layer for the recommender (Google Gemini).

Two calls, both hallucination-safe by construction:

1. ``interpret`` — turn a free-text request into a structured spec, a short
   "vibe" sentence (which the pipeline embeds into the query vector that drives
   pgvector retrieval), and a few discovery name ideas (resolved through live
   Spotify search, never trusted as track ids).
2. ``curate`` — **the RAG step.** Given the tracks the pipeline retrieved (real
   rows, with ids + metadata), pick and order the final playlist *from that set
   only*. Returned ids are validated against the supplied set, so nothing the
   model invents can reach the playlist.

Capability-flagged: with no Gemini key the recommender falls back to a
deterministic taste-ranked build, so these calls are always optional.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")  # 2.5-flash got gated for new keys

_client = None


def is_configured() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))


def _get_client():
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    return _client


def _extract_json(text: str) -> dict[str, Any] | None:
    """Parse a JSON object out of a reply that may carry fences/prose."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def _generate(system: str, prompt: str, temperature: float) -> dict[str, Any] | None:
    """One JSON-mode Gemini call; None on any failure (caller degrades)."""
    from google.genai import types

    client = _get_client()
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        temperature=temperature,
    )
    try:
        resp = await asyncio.to_thread(
            client.models.generate_content, model=MODEL, contents=prompt, config=config
        )
    except Exception:
        return None
    return _extract_json((getattr(resp, "text", None) or "").strip())


# --- interpret --------------------------------------------------------------

INTERPRET_INSTRUCTION = """You plan a music playlist for one listener from their short request.

There are NO audio features available, so translate any mood/activity words
(chill, hype, workout, sad, focus, party, rainy day) into fitting genres and a vibe.

Return ONLY a JSON object with exactly these fields:
- name: a short, catchy playlist title
- description: one sentence describing the playlist
- length: integer 5..50 (default 25)
- mix: integer 0..100. 0 = only music the listener already knows; 100 = only new
  discoveries. Use a high value for "new", "fresh", "stuff I haven't heard".
- allow_explicit: boolean (default true; false if they ask for clean / no explicit)
- genres: array of genre strings to focus on
- avoid_genres: array of genres to EXCLUDE. Fill it for "no rap", "nothing heavy",
  "skip country"; include close relatives (e.g. "no rap" -> ["rap","hip hop","trap","drill"]).
- vibe: ONE vivid sentence describing the target sound and mood (used to search a
  music library by meaning) — name textures, tempo, era, and feel, not artists.
- discovery_artists: up to 10 artist names the listener likely does NOT know yet but
  would love for this brief. Expansion, not repetition — avoid their listed top artists.
- discovery_tracks: up to 10 objects {"title": "...", "artist": "..."} of specific
  song picks fitting the brief, favoring artists outside their top list.

Output only the JSON object, nothing else."""


async def interpret(instruction: str, top_genres: list[str], top_artists: list[str]) -> dict[str, Any] | None:
    """Turn a free-text request into {spec fields, vibe, discovery_artists,
    discovery_tracks}. None on failure (caller falls back to param spec)."""
    prompt = (
        f"Request: {instruction.strip()}\n\n"
        f"Listener's top genres: {', '.join(top_genres) or 'unknown'}\n"
        f"Listener's top artists (do NOT recommend these): {', '.join(top_artists) or 'unknown'}"
    )
    ideas = await _generate(INTERPRET_INSTRUCTION, prompt, temperature=0.7)
    if not ideas:
        return None
    known = {a.lower() for a in top_artists}
    artists = [
        a.strip() for a in (ideas.get("discovery_artists") or [])
        if isinstance(a, str) and a.strip() and a.strip().lower() not in known
    ]
    tracks = [
        {"title": t["title"].strip(), "artist": t["artist"].strip()}
        for t in (ideas.get("discovery_tracks") or [])
        if isinstance(t, dict)
        and isinstance(t.get("title"), str) and t["title"].strip()
        and isinstance(t.get("artist"), str) and t["artist"].strip()
        and t["artist"].strip().lower() not in known
    ]
    return {
        "name": (ideas.get("name") or "").strip() or "Aurafy Mix",
        "description": (ideas.get("description") or "").strip(),
        "length": ideas.get("length"),
        "mix": ideas.get("mix"),
        "allow_explicit": ideas.get("allow_explicit", True),
        "genres": [g for g in (ideas.get("genres") or []) if isinstance(g, str) and g.strip()],
        "avoid_genres": [g for g in (ideas.get("avoid_genres") or []) if isinstance(g, str) and g.strip()],
        "vibe": (ideas.get("vibe") or "").strip(),
        "discovery_artists": artists[:10],
        "discovery_tracks": tracks[:10],
    }


# --- discovery ideas (find NEW artists from taste) --------------------------

DISCOVERY_INSTRUCTION = """You are a music curator finding NEW music for one listener.

You get their taste (top genres and top artists). Recommend music they most likely
DON'T already know but would love: adjacent scenes, influences, collaborators, rising
acts, deeper corners of their genres. Use web search when it helps (current releases,
"artists like X", scene lists).

Return ONLY a JSON object with exactly these fields:
- artists: up to 12 artist names that fit their taste. NEVER include artists from the
  listener's top list — the point is expansion, not repetition.
- tracks: up to 15 objects {"title": "...", "artist": "..."} — specific song picks,
  favoring artists outside the listener's top list.

Only the JSON object."""


async def discovery_ideas(top_genres: list[str], top_artists: list[str]) -> dict[str, Any] | None:
    """Ask Gemini for artists/tracks the listener likely doesn't know yet — the taste
    -> new-music step (Spotify's /recommendations is dead for dev-mode apps). Returns
    ``{"artists": [...], "tracks": [{"title","artist"}, ...]}`` or None. Grounded call
    first (Google Search can't combine with JSON mode, hence the lenient parse); plain
    JSON call as fallback. Everything is resolved through live Spotify search later, so
    a hallucinated name simply finds nothing — never a fake track."""
    from google.genai import types

    client = _get_client()
    prompt = (
        f"Listener's top genres: {', '.join(top_genres) or 'unknown'}\n"
        f"Listener's top artists (do NOT recommend these): {', '.join(top_artists) or 'unknown'}\n\n"
        "Recommend artists and songs they most likely DON'T know yet but would love."
    )
    attempts = [
        types.GenerateContentConfig(
            system_instruction=DISCOVERY_INSTRUCTION,
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.9,
        ),
        types.GenerateContentConfig(
            system_instruction=DISCOVERY_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.9,
        ),
    ]
    known = {a.lower() for a in top_artists}
    for config in attempts:
        try:
            resp = await asyncio.to_thread(
                client.models.generate_content, model=MODEL, contents=prompt, config=config
            )
        except Exception:
            continue
        ideas = _extract_json((getattr(resp, "text", None) or "").strip())
        if not ideas:
            continue
        artists = [
            a.strip() for a in (ideas.get("artists") or [])
            if isinstance(a, str) and a.strip() and a.strip().lower() not in known
        ]
        tracks = [
            {"title": t["title"].strip(), "artist": t["artist"].strip()}
            for t in (ideas.get("tracks") or [])
            if isinstance(t, dict)
            and isinstance(t.get("title"), str) and t["title"].strip()
            and isinstance(t.get("artist"), str) and t["artist"].strip()
            and t["artist"].strip().lower() not in known
        ]
        if artists or tracks:
            return {"artists": artists[:12], "tracks": tracks[:15]}
    return None


# --- curate (the RAG step) --------------------------------------------------

CURATE_INSTRUCTION = """You are a music curator assembling ONE playlist.

You are given the playlist brief, the listener's taste, and a NUMBERED list of
candidate tracks that were already retrieved for them. Your job is to SELECT and
ORDER the best tracks from that list — you may ONLY use tracks from the list.

Rules:
- Pick exactly the requested number of tracks (or fewer if the list is too short).
- Choose tracks that fit the vibe and honor the requested/avoided genres.
- Respect the familiar-vs-discovery balance implied by the mix value.
- Order them to flow well (don't stack the same artist back to back).
- NEVER invent tracks or ids. Only reference the numbers shown.

Return ONLY a JSON object: {"picks": [<candidate numbers in playlist order>]}."""


async def curate(
    candidates: list[dict[str, Any]], spec: dict[str, Any], top_artists: list[str], length: int
) -> list[str] | None:
    """RAG selection: from the retrieved ``candidates`` (each has an ``n`` index,
    id, title, artist, genres, and scores), return the chosen ``spotify_track_id``
    list in order. Every returned id is validated to come from ``candidates``, so
    a hallucinated pick cannot survive. None on failure (caller ranks locally)."""
    if not candidates:
        return None
    by_n = {c["n"]: c["spotify_track_id"] for c in candidates}
    lines = []
    for c in candidates:
        genres = ", ".join(c.get("genres") or []) or "unknown"
        lines.append(
            f'{c["n"]}. "{c["title"]}" by {c["artist"]} '
            f'[{c.get("kind", "?")}; genres: {genres}; taste {c.get("taste", 0):.2f}]'
        )
    prompt = (
        f"Brief: {spec.get('name') or 'Untitled'} — {spec.get('description') or ''}\n"
        f"Vibe: {spec.get('vibe') or 'open'}\n"
        f"Focus genres: {', '.join(spec.get('genres') or []) or 'open'}\n"
        f"AVOID genres: {', '.join(spec.get('avoid_genres') or []) or 'none'}\n"
        f"Mix (0=familiar, 100=new): {spec.get('mix', 30)}\n"
        f"Target length: {length} tracks\n"
        f"Listener's top artists: {', '.join(top_artists) or 'unknown'}\n\n"
        f"Candidates:\n" + "\n".join(lines)
    )
    out = await _generate(CURATE_INSTRUCTION, prompt, temperature=0.4)
    if not out:
        return None
    picks = out.get("picks")
    if not isinstance(picks, list):
        return None
    chosen: list[str] = []
    seen: set[str] = set()
    for n in picks:
        try:
            tid = by_n.get(int(n))
        except (TypeError, ValueError):
            continue
        if tid and tid not in seen:
            seen.add(tid)
            chosen.append(tid)
    return chosen or None


# --- genre backfill for fresh finds -----------------------------------------

GENRE_TAGGING_INSTRUCTION = """You tag music artists with genres.

For EVERY artist name given, return 1-3 lowercase genre tags. Use broad, canonical
tags (rap, hip hop, trap, drill, r&b, pop, dance pop, edm, house, electronic, indie
rock, rock, alternative, metal, punk, country, folk, latin, reggaeton, k-pop,
afrobeats, jazz, soul, classical, lo-fi, ambient, soundtrack). Never skip an artist.

Return ONLY a JSON object mapping each artist name EXACTLY as given to its tag array."""


async def infer_artist_genres(names: list[str]) -> dict[str, list[str]]:
    """Tag artists with genres via Gemini (Spotify no longer exposes them to
    dev-mode apps). Best-effort: returns whatever subset succeeded."""
    if not names:
        return {}
    parsed = await _generate(
        GENRE_TAGGING_INSTRUCTION, "Artists:\n" + "\n".join(names), temperature=0.2
    )
    if not parsed:
        return {}
    tagged: dict[str, list[str]] = {}
    for name in names:
        genres = parsed.get(name)
        if isinstance(genres, list):
            cleaned = [g.strip().lower() for g in genres if isinstance(g, str) and g.strip()]
            if cleaned:
                tagged[name] = cleaned[:3]
    return tagged
