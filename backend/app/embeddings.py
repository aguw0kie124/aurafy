"""Track embeddings (Google Gemini) — the recommender's vector space.

Turns each track's text metadata into a 768-dim vector so semantically similar
music sits nearby. This is our stand-in for the audio features dev-mode Spotify
denies: we substitute *textual/cultural* similarity (artist, album, genres) for
audio similarity.

Free-tier reality: `embed_content` is capped at ~100 items/min (each text counts
as a request), so `backfill` is throttled and runs in the background, resuming
across runs via embed-once (only NULL-vector rows are embedded). Artists aren't
embedded yet — nothing consumes artist vectors.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from . import db

EMBED_MODEL = "gemini-embedding-001"  # text-embedding-004 was retired
EMBED_DIM = 768                       # matches the tracks.embedding vector(768) column

_BATCH = 50                # texts per embed call
_RATE_PER_MIN = 90         # stay under the ~100 items/min free-tier cap

_client = None
_backfill_running = False
_tasks: set[asyncio.Task] = set()


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


# --- embedding calls --------------------------------------------------------


class EmbeddingError(RuntimeError):
    """An embedding call failed. Raised on the request path (where the caller needs
    to report *why*); the throttled backfill keeps its None-means-skip contract."""


async def _embed(texts: list[str]) -> list[list[float]]:
    """Embed one batch. Raises EmbeddingError carrying the real cause — a 429 quota
    error and a network drop want very different responses from the caller."""
    from google.genai import types

    client = _get_client()
    try:
        resp = await asyncio.to_thread(
            client.models.embed_content,
            model=EMBED_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(output_dimensionality=EMBED_DIM),
        )
    except Exception as exc:
        raise EmbeddingError(str(exc)) from exc
    return [list(e.values) for e in resp.embeddings]


async def embed_query(text: str) -> list[float]:
    """Embed one text as a retrieval query vector. Raises EmbeddingError — without a
    query vector there is no retrieval, so this cannot be degraded past."""
    return (await _embed([text]))[0]


async def _embed_batch(texts: list[str]) -> list[list[float]] | None:
    """Embed one batch; None on any failure (network/quota) so the backfill can skip
    the batch and resume on its next run."""
    try:
        return await _embed(texts)
    except EmbeddingError:
        return None


async def embed_texts(texts: list[str]) -> list[list[float] | None]:
    """Embed a small set of texts (e.g. a query at request time). Not throttled —
    keep call sizes small. Returns a per-text vector or None (order kept)."""
    out: list[list[float] | None] = []
    for start in range(0, len(texts), _BATCH):
        chunk = texts[start : start + _BATCH]
        vecs = await _embed_batch(chunk)
        out.extend(vecs if vecs is not None else [None] * len(chunk))
    return out


# --- background backfill ----------------------------------------------------


async def backfill() -> dict[str, int]:
    """Embed tracks missing a vector, throttled under the free-tier rate cap and
    resumable (embed-once). Stops early on a rate/quota hit — the next run picks
    up where it left off. Guarded so overlapping syncs don't double-embed."""
    global _backfill_running
    if not is_configured() or _backfill_running:
        return {"tracks": 0}
    _backfill_running = True
    done = 0
    try:
        while True:
            rows = await db.get_tracks_missing_embeddings(_BATCH)
            if not rows:
                break
            vecs = await _embed_batch([track_doc(r) for r in rows])
            if vecs is None:
                break  # rate/quota or error — resume on the next run
            pairs = [(r["spotify_track_id"], v) for r, v in zip(rows, vecs) if v is not None]
            if pairs:
                await db.store_track_embeddings(pairs)
                done += len(pairs)
            # Pace to stay under ~100 items/min.
            await asyncio.sleep(len(rows) / _RATE_PER_MIN * 60)
    finally:
        _backfill_running = False
    return {"tracks": done}


def start_backfill() -> bool:
    """Kick backfill in the background (non-blocking). Returns True if started,
    False if unconfigured or already running. Keeps a task ref so it isn't GC'd."""
    if not is_configured() or _backfill_running:
        return False
    task = asyncio.create_task(backfill())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return True
