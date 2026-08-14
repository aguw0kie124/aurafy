"""Natural-language layer for the recommender (Google Gemini).

Three calls, all hallucination-safe by construction:

1. ``interpret`` — turn a free-text request into a structured spec and a short
   "vibe" sentence (which the pipeline embeds into the query vector that drives
   pgvector retrieval).
2. ``discovery_ideas`` — name artists/tracks the listener probably doesn't know
   yet. Names only: every one is resolved through a real Spotify search before it
   can become a catalog row, so a hallucinated name simply finds nothing.
3. ``curate`` — **the RAG step.** Given the tracks the pipeline retrieved (real
   rows, with ids + metadata), pick and order the final playlist *from that set
   only*. Returned ids are validated against the supplied set, so nothing the
   model invents can reach the playlist.

Requires GEMINI_API_KEY/GOOGLE_API_KEY. These calls raise on failure rather than
degrading to a second, weaker code path; ``main`` enforces the key at startup so
a running app always has one.
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


class LLMError(RuntimeError):
    """A Gemini call failed or came back unusable. Callers translate this into an
    HTTP error — there is no second, weaker path to fall back to."""


async def _generate(system: str, prompt: str, temperature: float) -> dict[str, Any]:
    """One JSON-mode Gemini call. Raises LLMError if the call fails or the reply
    isn't parseable JSON."""
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
    except Exception as exc:
        raise LLMError(f"Gemini call failed: {exc}") from exc
    parsed = _extract_json((getattr(resp, "text", None) or "").strip())
    if parsed is None:
        raise LLMError("Gemini returned no parseable JSON object")
    return parsed


# --- interpret --------------------------------------------------------------

INTERPRET_INSTRUCTION = """You plan a music playlist for one listener from their short request.

There are NO audio features available, so translate any mood/activity words
(chill, hype, workout, sad, focus, party, rainy day) into fitting genres and a vibe.

Return ONLY a JSON object with exactly these fields:
- name: a short, catchy playlist title
- description: one sentence describing the playlist
- allow_explicit: boolean (default true; false if they ask for clean / no explicit)
- genres: array of genre strings to focus on
- avoid_genres: array of genres to EXCLUDE. Fill it for "no rap", "nothing heavy",
  "skip country"; include close relatives (e.g. "no rap" -> ["rap","hip hop","trap","drill"]).
- vibe: ONE vivid sentence describing the target sound and mood (used to search a
  music library by meaning) — name textures, tempo, era, and feel, not artists.

Output only the JSON object, nothing else."""


async def interpret(instruction: str, top_artists: list[str]) -> dict[str, Any]:
    """Turn a free-text request into a spec dict, including the ``vibe`` sentence
    the pipeline embeds as its retrieval query. Raises LLMError on failure."""
    prompt = (
        f"Request: {instruction.strip()}\n\n"
        f"Listener's top artists (for context): {', '.join(top_artists) or 'unknown'}"
    )
    ideas = await _generate(INTERPRET_INSTRUCTION, prompt, temperature=0.7)
    return {
        "name": (ideas.get("name") or "").strip() or "Aurafy Mix",
        "description": (ideas.get("description") or "").strip(),
        "allow_explicit": ideas.get("allow_explicit", True),
        "genres": [g for g in (ideas.get("genres") or []) if isinstance(g, str) and g.strip()],
        "avoid_genres": [g for g in (ideas.get("avoid_genres") or []) if isinstance(g, str) and g.strip()],
        "vibe": (ideas.get("vibe") or "").strip(),
    }


# --- discovery ideas (find NEW artists from taste) --------------------------

DISCOVERY_INSTRUCTION = """You are a music curator finding NEW music for one listener.

You get their taste (top artists), and sometimes a target vibe for the session.
Recommend music they most likely DON'T already know but would love: adjacent scenes,
influences, collaborators, rising acts, deeper corners of their sound. When a vibe is
given, bias every pick towards it. Use web search when it helps (current releases,
"artists like X", scene lists).

Return ONLY a JSON object with exactly these fields:
- artists: up to 12 artist names that fit their taste. NEVER include artists from the
  listener's top list — the point is expansion, not repetition.
- tracks: up to 15 objects {"title": "...", "artist": "..."} — specific song picks,
  favoring artists outside the listener's top list.

Only the JSON object."""


async def discovery_ideas(top_artists: list[str], vibe: str = "") -> dict[str, Any]:
    """Ask Gemini for artists/tracks the listener likely doesn't know yet — the taste
    -> new-music step (Spotify's /recommendations is dead for dev-mode apps). Returns
    ``{"artists": [...], "tracks": [{"title","artist"}, ...]}``; raises LLMError if
    both attempts come back empty. Grounded call first (Google Search can't combine
    with JSON mode, hence the lenient parse); plain JSON call as the second attempt.

    This is the single entry point for growing the catalog — the feed calls it with
    taste alone, the playlist builder also passes the request's ``vibe`` so the names
    lean towards what was actually asked for. Everything is resolved through live
    Spotify search later, so a hallucinated name simply finds nothing."""
    from google.genai import types

    client = _get_client()
    prompt = (
        f"Listener's top artists (do NOT recommend these): {', '.join(top_artists) or 'unknown'}\n"
        + (f"Target vibe for this session: {vibe}\n" if vibe.strip() else "")
        + "\nRecommend artists and songs they most likely DON'T know yet but would love."
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
    raise LLMError("Gemini returned no usable discovery ideas")


# --- curate (the RAG step) --------------------------------------------------

CURATE_INSTRUCTION = """You are a music curator assembling ONE playlist.

You are given the playlist brief, the listener's taste, and a NUMBERED list of
candidate tracks that were already retrieved for them. Your job is to SELECT and
ORDER the best tracks from that list — you may ONLY use tracks from the list.

Each candidate is tagged "familiar" (already in their library) or "discovery" (new to
them), and carries a taste score — how close it sits to the rest of their library,
0.00-1.00, higher means more like what they already play.

Rules:
- Pick exactly the requested number of tracks (or fewer if the list is too short).
- Choose tracks that fit the vibe and honor the requested/avoided genres.
- Blend familiar and discovery unless the brief clearly leans one way ("stuff I
  haven't heard" -> mostly discovery; "my favourites" -> mostly familiar).
- Prefer a higher taste score when two candidates fit the brief equally well.
- Order them to flow well (don't stack the same artist back to back).
- NEVER invent tracks or ids. Only reference the numbers shown.

Return ONLY a JSON object: {"picks": [<candidate numbers in playlist order>]}."""


async def curate(
    candidates: list[dict[str, Any]], spec: dict[str, Any], top_artists: list[str], length: int
) -> list[str]:
    """RAG selection: from the retrieved ``candidates`` (each has an ``n`` index, id,
    title, artist, genres, kind and taste score), return the chosen
    ``spotify_track_id`` list in order. Every returned id is validated to come from
    ``candidates``, so a hallucinated pick cannot survive. Raises LLMError if the call
    fails; an empty selection is a valid answer (the caller backfills)."""
    if not candidates:
        return []
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
        f"Target length: {length} tracks\n"
        f"Listener's top artists: {', '.join(top_artists) or 'unknown'}\n\n"
        f"Candidates:\n" + "\n".join(lines)
    )
    out = await _generate(CURATE_INSTRUCTION, prompt, temperature=0.4)
    picks = out.get("picks")
    if not isinstance(picks, list):
        raise LLMError("Gemini curate reply had no 'picks' list")
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
    return chosen


# --- genre backfill for fresh finds -----------------------------------------

GENRE_TAGGING_INSTRUCTION = """You tag music artists with genres.

For EVERY artist name given, return 1-3 lowercase genre tags. Use broad, canonical
tags (rap, hip hop, trap, drill, r&b, pop, dance pop, edm, house, electronic, indie
rock, rock, alternative, metal, punk, country, folk, latin, reggaeton, k-pop,
afrobeats, jazz, soul, classical, lo-fi, ambient, soundtrack). Never skip an artist.

Return ONLY a JSON object mapping each artist name EXACTLY as given to its tag array."""


async def infer_artist_genres(names: list[str]) -> dict[str, list[str]]:
    """Tag artists with genres via Gemini. This is the app's ONLY source of genre
    data — Spotify exposes no ``genres`` field to dev-mode apps at all — and it is
    what lets ``avoid_genres`` ("no rap") actually filter anything. Returns whatever
    subset came back tagged; raises LLMError if the call itself fails."""
    if not names:
        return {}
    parsed = await _generate(
        GENRE_TAGGING_INSTRUCTION, "Artists:\n" + "\n".join(names), temperature=0.2
    )
    tagged: dict[str, list[str]] = {}
    for name in names:
        genres = parsed.get(name)
        if isinstance(genres, list):
            cleaned = [g.strip().lower() for g in genres if isinstance(g, str) and g.strip()]
            if cleaned:
                tagged[name] = cleaned[:3]
    return tagged
