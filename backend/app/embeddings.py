"""Track/artist embeddings (Google Gemini) — the recommender's vector space.

Turns each item's text metadata into a 768-dim vector so semantically similar
music sits nearby. This is our stand-in for the audio features dev-mode Spotify
denies: we substitute *textual/cultural* similarity (artist, album, genres) for
audio similarity.

Best-effort and cached by construction: only items whose stored vector is NULL
are embedded, so repeated syncs converge without re-work. A quota hiccup just
leaves some items unembedded until the next sync.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Awaitable, Callable

from . import db

EMBED_MODEL = "text-embedding-004"  # 768-dim
EMBED_DIM = 768

_BATCH = 100                  # texts per Gemini embed call
_MAX_TRACKS_PER_SYNC = 2000   # bound the latency of the in-request backfill
_MAX_ARTISTS_PER_SYNC = 1000

_client = None


def is_configured() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))


def _get_client():
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    return _client


# --- text documents ---------------------------------------------------------


def track_doc(row: dict[str, Any]) -> str:
    """Compact semantic doc for a track: title, artists, album, genres."""
    parts = [f'{row["title"]} by {row["artist"]}']
    if row.get("album"):
        parts.append(f'album: {row["album"]}')
    genres = sorted({g for g in (row.get("genres") or []) if g})
    if genres:
        parts.append("genres: " + ", ".join(genres))
    return " — ".join(parts)


def artist_doc(row: dict[str, Any]) -> str:
    """Compact semantic doc for an artist: name + genres."""
    genres = sorted({g for g in (row.get("genres") or []) if g})
    return f'{row["name"]} — {", ".join(genres)}' if genres else row["name"]


# --- embedding calls --------------------------------------------------------


async def _embed_batch(texts: list[str]) -> list[list[float]] | None:
    """Embed one batch; None on any failure (network/quota) so callers skip it."""
    client = _get_client()
    try:
        resp = await asyncio.to_thread(
            client.models.embed_content, model=EMBED_MODEL, contents=texts
        )
    except Exception:
        return None
    return [list(e.values) for e in resp.embeddings]


async def embed_texts(texts: list[str]) -> list[list[float] | None]:
    """Embed many texts, chunked. Returns a per-text vector or None (order kept)."""
    out: list[list[float] | None] = []
    for start in range(0, len(texts), _BATCH):
        chunk = texts[start : start + _BATCH]
        vecs = await _embed_batch(chunk)
        out.extend(vecs if vecs is not None else [None] * len(chunk))
    return out


# --- sync-time backfill -----------------------------------------------------


async def _embed_and_store(
    rows: list[dict[str, Any]],
    doc_fn: Callable[[dict[str, Any]], str],
    key: str,
    store: Callable[[list[tuple[str, list[float]]]], Awaitable[None]],
) -> int:
    if not rows:
        return 0
    vecs = await embed_texts([doc_fn(r) for r in rows])
    pairs = [(r[key], v) for r, v in zip(rows, vecs) if v is not None]
    if pairs:
        await store(pairs)
    return len(pairs)


async def backfill() -> dict[str, int]:
    """Embed any tracks/artists still missing a vector. Best-effort; bounded per
    call so a large first sync doesn't stall the request (later syncs finish it)."""
    if not is_configured():
        return {"tracks": 0, "artists": 0}
    tracks = await db.get_tracks_missing_embeddings(_MAX_TRACKS_PER_SYNC)
    artists = await db.get_artists_missing_embeddings(_MAX_ARTISTS_PER_SYNC)
    return {
        "tracks": await _embed_and_store(
            tracks, track_doc, "spotify_track_id", db.store_track_embeddings
        ),
        "artists": await _embed_and_store(
            artists, artist_doc, "spotify_artist_id", db.store_artist_embeddings
        ),
    }
