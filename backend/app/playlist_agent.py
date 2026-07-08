"""Natural-language layer for the playlist builder (Google Gemini).

Two jobs, both hallucination-safe by construction:

1. ``spec_from_instruction`` — translate a short free-text request into a
   structured ``PlaylistSpec`` the deterministic engine executes.
2. ``discovery_ideas`` — act as a music curator: given the spec and the
   listener's taste, propose artists/songs they likely DON'T know yet
   (grounded with Google Search when available). Spotify apps lost the
   /recommendations and related-artists endpoints, so this fills that hole.

Gemini only ever emits names and search hints — never track ids. Everything it
suggests is resolved through live Spotify search, so nothing fake can appear.

Capability-flagged: if no Gemini key is configured, the parameter-based builder
still works; only these AI modes are unavailable.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from fastapi import HTTPException

MODEL = "gemini-2.5-flash"  # 2.0-flash no longer has free-tier quota

_client = None

SYSTEM_INSTRUCTION = """You translate a listener's short request into a JSON playlist spec.

Return ONLY a JSON object with exactly these fields:
- name: a short, catchy playlist title
- description: one sentence describing the playlist
- length: integer between 5 and 50 (default 25)
- mix: integer 0..100. 0 = only songs the listener already knows; 100 = only new
  discoveries. Use a high value when they ask for new / fresh / "stuff I haven't heard".
- allow_explicit: boolean (default true; set false if they ask for clean / no explicit)
- genres: array of genre strings to focus on. Prefer choosing from the USER'S TOP GENRES
  listed below. There are NO audio features available, so translate any mood words
  (chill, hype, workout, sad, focus, party) into fitting genres.
- seed_artist_names: array of artist names ONLY if they explicitly want music like a
  specific artist; otherwise an empty array.

Never include track names or ids. Output only the JSON object, nothing else."""


def ai_is_configured() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))


def _get_client():
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    return _client


async def spec_from_instruction(
    instruction: str, top_genres: list[str], top_artists: list[str]
) -> dict[str, Any]:
    """Ask Gemini to turn a short instruction into a raw PlaylistSpec dict."""
    from google.genai import types

    client = _get_client()
    prompt = (
        f"Request: {instruction.strip()}\n\n"
        f"User's top genres: {', '.join(top_genres) or 'unknown'}\n"
        f"User's top artists: {', '.join(top_artists) or 'unknown'}"
    )
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        temperature=0.7,
    )
    try:
        response = await asyncio.to_thread(
            client.models.generate_content, model=MODEL, contents=prompt, config=config
        )
    except Exception as exc:  # network / quota / SDK errors
        message = str(exc)
        if "RESOURCE_EXHAUSTED" in message or "429" in message:
            raise HTTPException(
                status_code=503,
                detail="The playlist assistant is rate-limited right now. "
                "Wait a minute and retry, or use the manual controls.",
            )
        raise HTTPException(status_code=502, detail=f"Playlist assistant failed: {message[:200]}")

    text = (getattr(response, "text", None) or "").strip()
    try:
        spec = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(
            status_code=502, detail="Could not understand that request. Try rephrasing it."
        )
    if not isinstance(spec, dict):
        raise HTTPException(status_code=502, detail="The playlist assistant returned an invalid spec.")
    return spec


DISCOVERY_INSTRUCTION = """You are a music curator finding NEW music for one listener.

You get the playlist being built and the listener's taste (top artists and genres).
Recommend music they most likely DON'T already know but would love, fitting the
playlist's vibe: adjacent scenes, influences, collaborators, rising acts, deeper cuts.
Use web search when it helps (current releases, "artists like X", scene lists).

Return ONLY a JSON object with exactly these fields:
- artists: up to 12 artist names that fit the brief. NEVER include artists from the
  listener's top list — the point is expansion, not repetition.
- tracks: up to 15 objects {"title": "...", "artist": "..."} — specific song picks
  that fit the brief, favoring artists outside the listener's top list.

No commentary, no markdown fences if you can avoid them. Only the JSON object."""


def _extract_json(text: str) -> dict[str, Any] | None:
    """Parse a JSON object out of a model reply that may carry fences/prose."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def discovery_ideas(
    brief: dict[str, Any], top_genres: list[str], top_artists: list[str]
) -> dict[str, Any] | None:
    """Curate discovery candidates for a spec. Returns {"artists": [...],
    "tracks": [{"title", "artist"}, ...]} or None — callers must treat this as
    a best-effort enhancement and fall back to plain search discovery."""
    from google.genai import types

    client = _get_client()
    prompt = (
        f"Playlist: {brief.get('name') or 'Untitled'} — {brief.get('description') or ''}\n"
        f"Requested genres/moods: {', '.join(brief.get('genres') or []) or 'open'}\n"
        f"Novelty: {brief.get('mix', 30)}/100 (higher = push further from their comfort zone)\n\n"
        f"Listener's top genres: {', '.join(top_genres) or 'unknown'}\n"
        f"Listener's top artists (do NOT recommend these): {', '.join(top_artists) or 'unknown'}"
    )
    # Grounded call first (search tool can't be combined with JSON response
    # mode, hence the lenient parse); plain JSON call as fallback.
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
    for config in attempts:
        try:
            response = await asyncio.to_thread(
                client.models.generate_content, model=MODEL, contents=prompt, config=config
            )
        except Exception:
            continue
        ideas = _extract_json((getattr(response, "text", None) or "").strip())
        if not ideas:
            continue
        artists = [a for a in (ideas.get("artists") or []) if isinstance(a, str) and a.strip()]
        tracks = [
            {"title": t["title"].strip(), "artist": t["artist"].strip()}
            for t in (ideas.get("tracks") or [])
            if isinstance(t, dict)
            and isinstance(t.get("title"), str) and t["title"].strip()
            and isinstance(t.get("artist"), str) and t["artist"].strip()
        ]
        # Belt and braces: drop anything the model echoed from the top list.
        known = {a.lower() for a in top_artists}
        artists = [a for a in artists if a.lower() not in known]
        tracks = [t for t in tracks if t["artist"].lower() not in known]
        if artists or tracks:
            return {"artists": artists[:12], "tracks": tracks[:15]}
    return None
