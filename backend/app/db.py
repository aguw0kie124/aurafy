"""Postgres (Supabase) persistence: users, tokens, and sessions.
Plain asyncpg + SQL — no ORM.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
from cryptography.fernet import Fernet

SESSION_TTL = timedelta(days=14)

pool: asyncpg.Pool | None = None
_fernet: Fernet | None = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Register the pgvector codec so `vector` columns accept/return Python lists.
    Best-effort: if the extension isn't installed yet (migration not run), vector
    writes simply no-op via the best-effort embedding backfill until it is."""
    try:
        from pgvector.asyncpg import register_vector

        await register_vector(conn)
    except Exception:
        pass


async def connect() -> None:
    global pool, _fernet
    dsn = os.getenv("SUPABASE_DB_URL")
    key = os.getenv("TOKEN_ENCRYPTION_KEY")
    if not dsn or not key:
        raise RuntimeError("Set SUPABASE_DB_URL and TOKEN_ENCRYPTION_KEY in .env (see README).")
    _fernet = Fernet(key)
    # statement_cache_size=0 keeps asyncpg compatible with both Supabase pooler modes.
    pool = await asyncpg.create_pool(
        dsn, min_size=1, max_size=5, statement_cache_size=0, init=_init_connection
    )


async def disconnect() -> None:
    if pool is not None:
        await pool.close()


def _encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def _decrypt(value: str) -> str:
    return _fernet.decrypt(value.encode()).decode()


def _to_dt(epoch: float) -> datetime:
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


# --- users, tokens, sessions ---


async def upsert_user(spotify_user_id: str, display_name: str, image_url: str | None) -> str:
    row = await pool.fetchrow(
        """
        insert into app_users (spotify_user_id, display_name, image_url)
        values ($1, $2, $3)
        on conflict (spotify_user_id) do update
            set display_name = excluded.display_name, image_url = excluded.image_url
        returning id
        """,
        spotify_user_id, display_name, image_url,
    )
    return str(row["id"])


async def upsert_tokens(
    user_id: str, access_token: str, refresh_token: str, expires_at: float
) -> None:
    await pool.execute(
        """
        insert into spotify_tokens
            (user_id, access_token_encrypted, refresh_token_encrypted, expires_at, updated_at)
        values ($1, $2, $3, $4, now())
        on conflict (user_id) do update set
            access_token_encrypted = excluded.access_token_encrypted,
            refresh_token_encrypted = excluded.refresh_token_encrypted,
            expires_at = excluded.expires_at,
            updated_at = now()
        """,
        user_id, _encrypt(access_token), _encrypt(refresh_token), _to_dt(expires_at),
    )


async def create_session(session_id: str, user_id: str) -> None:
    await pool.execute(
        "insert into sessions (id, user_id, expires_at) values ($1, $2, now() + $3)",
        session_id, user_id, SESSION_TTL,
    )


async def get_session_ctx(session_id: str) -> dict[str, Any] | None:
    row = await pool.fetchrow(
        """
        select u.id as user_id, u.spotify_user_id, u.display_name, u.image_url,
               t.access_token_encrypted, t.refresh_token_encrypted, t.expires_at
        from sessions s
        join app_users u on u.id = s.user_id
        join spotify_tokens t on t.user_id = u.id
        where s.id = $1 and s.expires_at > now()
        """,
        session_id,
    )
    if row is None:
        return None
    return {
        "session_id": session_id,
        "user_id": str(row["user_id"]),
        "user": {
            "spotifyUserId": row["spotify_user_id"],
            "displayName": row["display_name"],
            "imageUrl": row["image_url"],
        },
        "tokens": {
            "access_token": _decrypt(row["access_token_encrypted"]),
            "refresh_token": _decrypt(row["refresh_token_encrypted"]),
            "expires_at": row["expires_at"].timestamp(),
        },
    }


async def delete_session(session_id: str) -> None:
    await pool.execute("delete from sessions where id = $1", session_id)


async def delete_expired_sessions() -> int:
    """Purge sessions past their TTL (expired rows are ignored by lookups but
    otherwise accumulate forever). Run on startup."""
    result = await pool.execute("delete from sessions where expires_at <= now()")
    # asyncpg returns a tag like "DELETE 12"; best-effort parse for logging.
    try:
        return int(result.split()[-1])
    except (ValueError, IndexError):
        return 0


# --- library sync ---


async def sync_library(user_id: str, payload: dict[str, Any]) -> None:
    """Persist a full snapshot of the user's Spotify library in one transaction.

    ``payload`` is built by the caller from Spotify responses. Catalog rows
    (artists, tracks) are upserted; per-user snapshots (saved/top/playlists) are
    replaced so removals disappear; play history is append-only.
    Writes run in FK-safe order: artists -> tracks -> links -> user rows.
    """
    artists = payload["artists"]
    genres = payload["artist_genres"]
    tracks = payload["tracks"]
    track_artists = payload["track_artists"]
    saved = payload["saved_tracks"]
    playlists = payload["playlists"]
    playlist_tracks = payload["playlist_tracks"]
    top_tracks = payload["top_tracks"]
    top_artists = payload["top_artists"]
    play_history = payload["play_history"]

    async with pool.acquire() as conn:
        async with conn.transaction():
            if artists:
                await conn.executemany(
                    """
                    insert into artists
                        (spotify_artist_id, name, image_url, external_url, popularity, updated_at)
                    values ($1, $2, $3, $4, $5, now())
                    on conflict (spotify_artist_id) do update set
                        name = excluded.name, image_url = excluded.image_url,
                        external_url = excluded.external_url, popularity = excluded.popularity,
                        updated_at = now()
                    """,
                    [
                        (a["spotify_artist_id"], a["name"], a.get("image_url"),
                         a.get("external_url"), a.get("popularity"))
                        for a in artists
                    ],
                )

            if genres:
                await conn.executemany(
                    "delete from artist_genres where spotify_artist_id = $1",
                    [(artist_id,) for artist_id in genres],
                )
                genre_rows = [(artist_id, g) for artist_id, gs in genres.items() for g in gs]
                if genre_rows:
                    await conn.executemany(
                        "insert into artist_genres (spotify_artist_id, genre) values ($1, $2) "
                        "on conflict do nothing",
                        genre_rows,
                    )

            if tracks:
                await conn.executemany(
                    """
                    insert into tracks
                        (spotify_track_id, title, artist, album, image_url, external_url,
                         popularity, explicit, duration_ms, updated_at)
                    values ($1, $2, $3, $4, $5, $6, $7, $8, $9, now())
                    on conflict (spotify_track_id) do update set
                        title = excluded.title, artist = excluded.artist, album = excluded.album,
                        image_url = excluded.image_url, external_url = excluded.external_url,
                        popularity = excluded.popularity, explicit = excluded.explicit,
                        duration_ms = excluded.duration_ms, updated_at = now()
                    """,
                    [
                        (t["spotify_track_id"], t["title"], t["artist"], t.get("album"),
                         t.get("image_url"), t.get("external_url"), t.get("popularity"),
                         bool(t.get("explicit")), t.get("duration_ms"))
                        for t in tracks
                    ],
                )

            if track_artists:
                await conn.executemany(
                    "insert into track_artists (spotify_track_id, spotify_artist_id, position) "
                    "values ($1, $2, $3) "
                    "on conflict (spotify_track_id, spotify_artist_id) do update set "
                    "position = excluded.position",
                    track_artists,
                )

            await conn.execute("delete from user_saved_tracks where user_id = $1", user_id)
            if saved:
                await conn.executemany(
                    "insert into user_saved_tracks (user_id, spotify_track_id, saved_at) "
                    "values ($1, $2, $3) on conflict do nothing",
                    [(user_id, track_id, saved_at) for track_id, saved_at in saved],
                )

            playlist_ids = [p["spotify_playlist_id"] for p in playlists]
            await conn.execute("delete from user_playlists where user_id = $1", user_id)
            if playlist_ids:
                await conn.execute(
                    "delete from playlist_tracks where spotify_playlist_id = any($1::text[])",
                    playlist_ids,
                )
            if playlists:
                await conn.executemany(
                    "insert into user_playlists (user_id, spotify_playlist_id, name, track_total, updated_at) "
                    "values ($1, $2, $3, $4, now()) "
                    "on conflict (user_id, spotify_playlist_id) do update set "
                    "name = excluded.name, track_total = excluded.track_total, updated_at = now()",
                    [
                        (user_id, p["spotify_playlist_id"], p.get("name"), p.get("track_total"))
                        for p in playlists
                    ],
                )
            if playlist_tracks:
                await conn.executemany(
                    "insert into playlist_tracks (spotify_playlist_id, spotify_track_id, position) "
                    "values ($1, $2, $3) "
                    "on conflict (spotify_playlist_id, spotify_track_id) do update set "
                    "position = excluded.position",
                    playlist_tracks,
                )

            await conn.execute("delete from user_top_tracks where user_id = $1", user_id)
            if top_tracks:
                await conn.executemany(
                    "insert into user_top_tracks (user_id, spotify_track_id, time_range, rank, captured_at) "
                    "values ($1, $2, $3, $4, now()) "
                    "on conflict (user_id, spotify_track_id, time_range) do update set "
                    "rank = excluded.rank, captured_at = now()",
                    [(user_id, track_id, tr, rank) for track_id, tr, rank in top_tracks],
                )

            await conn.execute("delete from user_top_artists where user_id = $1", user_id)
            if top_artists:
                await conn.executemany(
                    "insert into user_top_artists (user_id, spotify_artist_id, time_range, rank, captured_at) "
                    "values ($1, $2, $3, $4, now()) "
                    "on conflict (user_id, spotify_artist_id, time_range) do update set "
                    "rank = excluded.rank, captured_at = now()",
                    [(user_id, artist_id, tr, rank) for artist_id, tr, rank in top_artists],
                )

            if play_history:
                await conn.executemany(
                    "insert into play_history (user_id, spotify_track_id, played_at) "
                    "values ($1, $2, $3) on conflict do nothing",
                    [(user_id, track_id, played_at) for track_id, played_at in play_history],
                )


async def get_track_artist_genres(track_ids: list[str]) -> dict[str, dict[str, Any]]:
    """For each track id, its artist ids (billing order), artist names, and the
    union of those artists' genres. Enriches candidates that arrive thin — ANN
    retrieval rows and live-search finds — so avoid-genre filtering and per-artist
    caps see the full picture. Missing ids are simply absent from the result."""
    if not track_ids:
        return {}
    rows = await pool.fetch(
        f"""
        select t.spotify_track_id,
               {_ARTIST_IDS_AND_GENRES_SQL},
               coalesce((select array_agg(a.name order by ta.position)
                         from track_artists ta
                         join artists a on a.spotify_artist_id = ta.spotify_artist_id
                         where ta.spotify_track_id = t.spotify_track_id), '{{}}') as artist_names
        from tracks t
        where t.spotify_track_id = any($1::text[])
        """,
        track_ids,
    )
    return {
        r["spotify_track_id"]: {
            "artist_ids": list(r["artist_ids"]),
            "artist_name_list": list(r["artist_names"]),
            "genres": list(r["genres"]),
        }
        for r in rows
    }


# --- embeddings (recommender vector space) ---


async def get_tracks_missing_embeddings(limit: int) -> list[dict[str, Any]]:
    """Tracks without a vector yet, with the fields needed to build the text doc."""
    rows = await pool.fetch(
        """
        select t.spotify_track_id, t.title, t.artist, t.album,
               coalesce((select array_agg(distinct ag.genre)
                         from track_artists ta
                         join artist_genres ag on ag.spotify_artist_id = ta.spotify_artist_id
                         where ta.spotify_track_id = t.spotify_track_id), '{}') as genres
        from tracks t
        where t.embedding is null
        limit $1
        """,
        limit,
    )
    return [
        {
            "spotify_track_id": r["spotify_track_id"],
            "title": r["title"],
            "artist": r["artist"],
            "album": r["album"],
            "genres": list(r["genres"]),
        }
        for r in rows
    ]


async def store_track_embeddings(pairs: list[tuple[str, list[float]]]) -> None:
    """(spotify_track_id, vector) — requires the pgvector codec (see _init_connection)."""
    if pairs:
        await pool.executemany(
            "update tracks set embedding = $2, updated_at = now() where spotify_track_id = $1",
            pairs,
        )


async def upsert_catalog_tracks(
    artists: list[dict[str, Any]],
    tracks: list[dict[str, Any]],
    track_artists: list[tuple[str, str, int]],
) -> None:
    """Persist live-discovery finds into the shared catalog (no per-user rows),
    so a searched track becomes a first-class, embeddable catalog record — the
    discovery flywheel. Mirrors the catalog upserts in ``sync_library``. New
    tracks land with a NULL embedding; the recommender embeds them inline and
    the next sync's backfill covers any it missed."""
    if not (artists or tracks or track_artists):
        return
    async with pool.acquire() as conn:
        async with conn.transaction():
            if artists:
                await conn.executemany(
                    """
                    insert into artists
                        (spotify_artist_id, name, image_url, external_url, popularity, updated_at)
                    values ($1, $2, $3, $4, $5, now())
                    on conflict (spotify_artist_id) do update set
                        name = excluded.name, updated_at = now()
                    """,
                    [
                        (a["spotify_artist_id"], a["name"], a.get("image_url"),
                         a.get("external_url"), a.get("popularity"))
                        for a in artists
                    ],
                )
            if tracks:
                await conn.executemany(
                    """
                    insert into tracks
                        (spotify_track_id, title, artist, album, image_url, external_url,
                         popularity, explicit, duration_ms, updated_at)
                    values ($1, $2, $3, $4, $5, $6, $7, $8, $9, now())
                    on conflict (spotify_track_id) do update set
                        popularity = excluded.popularity, updated_at = now()
                    """,
                    [
                        (t["spotify_track_id"], t["title"], t["artist"], t.get("album"),
                         t.get("image_url"), t.get("external_url"), t.get("popularity"),
                         bool(t.get("explicit")), t.get("duration_ms"))
                        for t in tracks
                    ],
                )
            if track_artists:
                await conn.executemany(
                    "insert into track_artists (spotify_track_id, spotify_artist_id, position) "
                    "values ($1, $2, $3) "
                    "on conflict (spotify_track_id, spotify_artist_id) do nothing",
                    track_artists,
                )


# --- vector retrieval (ANN) & taste ranking (kNN) ---


async def vector_search_catalog(
    user_id: str, query_vec: list[float], k: int, allow_explicit: bool
) -> list[dict[str, Any]]:
    """ANN retrieval: catalog tracks nearest ``query_vec`` (cosine), excluding
    tracks the user already owns. Uses the HNSW index; most-similar first.
    ``similarity`` is 1 - cosine_distance (1.0 = identical, 0.0 = orthogonal)."""
    rows = await pool.fetch(
        f"""
        with lib as ({_LIBRARY_IDS_SQL})
        select t.spotify_track_id, t.title, t.artist, t.album, t.image_url, t.external_url,
               t.popularity, t.explicit,
               1 - (t.embedding <=> $2) as similarity
        from tracks t
        where t.embedding is not null
          and t.spotify_track_id not in (select spotify_track_id from lib)
          and ($3 or t.explicit = false)
        order by t.embedding <=> $2
        limit $4
        """,
        user_id, query_vec, allow_explicit, k,
    )
    return [
        {
            "spotify_track_id": r["spotify_track_id"],
            "title": r["title"],
            "artist": r["artist"],
            "album": r["album"],
            "image_url": r["image_url"],
            "external_url": r["external_url"],
            "popularity": r["popularity"] or 0,
            "explicit": r["explicit"],
            "similarity": float(r["similarity"]),
        }
        for r in rows
    ]


async def vibe_scores(track_ids: list[str], query_vec: list[float]) -> dict[str, float]:
    """Cosine similarity (1 - distance) of each track to a query vector. Used to
    rank the user's *familiar* tracks by how well they fit the request's vibe —
    taste-fit can't (a library track's nearest library neighbor is itself), so
    without this the familiar half ignores the request. Missing/unembedded ids
    are absent from the result."""
    if not track_ids:
        return {}
    rows = await pool.fetch(
        """
        select spotify_track_id, 1 - (embedding <=> $2) as similarity
        from tracks
        where spotify_track_id = any($1::text[]) and embedding is not null
        """,
        track_ids, query_vec,
    )
    return {r["spotify_track_id"]: float(r["similarity"]) for r in rows}


def _to_list(vec: Any) -> list[float]:
    """Read a pgvector column value back to a plain list. The asyncpg codec returns a
    ``pgvector.Vector`` (not directly iterable); numpy arrays and lists also pass through."""
    if hasattr(vec, "to_list"):
        return vec.to_list()
    return list(vec)


async def get_track_embeddings(track_ids: list[str]) -> dict[str, list[float]]:
    """Stored embedding vectors for the given track ids (used to build a seed
    centroid from anchor songs). Missing / unembedded ids are omitted."""
    if not track_ids:
        return {}
    rows = await pool.fetch(
        "select spotify_track_id, embedding from tracks "
        "where spotify_track_id = any($1::text[]) and embedding is not null",
        track_ids,
    )
    return {r["spotify_track_id"]: _to_list(r["embedding"]) for r in rows}


async def get_artist_track_embeddings(artist_ids: list[str], limit: int) -> list[list[float]]:
    """Embedding vectors for catalog tracks by the given artists (for a seed-artist
    centroid). Most-popular first, capped at ``limit``."""
    if not artist_ids:
        return []
    rows = await pool.fetch(
        """
        select t.embedding
        from tracks t
        join track_artists ta on ta.spotify_track_id = t.spotify_track_id
        where ta.spotify_artist_id = any($1::text[]) and t.embedding is not null
        order by t.popularity desc nulls last
        limit $2
        """,
        artist_ids, limit,
    )
    return [_to_list(r["embedding"]) for r in rows]


async def get_user_library_vectors(user_id: str) -> list[dict[str, Any]]:
    """The user's library tracks that have an embedding, with light metadata — for
    taste-mode clustering and centroids. ``embedding`` is a python list of floats."""
    rows = await pool.fetch(
        f"""
        with lib as ({_LIBRARY_IDS_SQL})
        select t.spotify_track_id, t.title, t.artist, t.embedding
        from lib join tracks t on t.spotify_track_id = lib.spotify_track_id
        where t.embedding is not null
        """,
        user_id,
    )
    return [
        {
            "spotify_track_id": r["spotify_track_id"],
            "title": r["title"],
            "artist": r["artist"],
            "embedding": _to_list(r["embedding"]),
        }
        for r in rows
    ]


async def get_seed_tracks(user_id: str, limit: int) -> list[dict[str, Any]]:
    """Recent high-signal tracks with embeddings — seeds for the 'Because you liked X'
    rows. Liked songs first (most recent), falling back to top tracks."""
    rows = await pool.fetch(
        """
        select t.spotify_track_id, t.title, t.artist, t.image_url, t.embedding
        from user_saved_tracks ust
        join tracks t on t.spotify_track_id = ust.spotify_track_id
        where ust.user_id = $1 and t.embedding is not null
        order by ust.saved_at desc nulls last
        limit $2
        """,
        user_id, limit,
    )
    if not rows:
        rows = await pool.fetch(
            """
            select t.spotify_track_id, t.title, t.artist, t.image_url, t.embedding
            from user_top_tracks utt
            join tracks t on t.spotify_track_id = utt.spotify_track_id
            where utt.user_id = $1 and t.embedding is not null
            order by utt.rank asc
            limit $2
            """,
            user_id, limit,
        )
    return [
        {
            "spotify_track_id": r["spotify_track_id"],
            "title": r["title"],
            "artist": r["artist"],
            "image_url": r["image_url"],
            "embedding": _to_list(r["embedding"]),
        }
        for r in rows
    ]


async def vector_search_near_track(
    user_id: str, seed_track_id: str, k: int, allow_explicit: bool
) -> list[dict[str, Any]]:
    """Catalog tracks nearest a seed track's *stored* embedding (cosine), excluding the
    seed and anything the user owns. Same row shape as ``vector_search_catalog``."""
    rows = await pool.fetch(
        f"""
        with lib as ({_LIBRARY_IDS_SQL}),
             seed as (select embedding from tracks where spotify_track_id = $2)
        select t.spotify_track_id, t.title, t.artist, t.album, t.image_url, t.external_url,
               t.popularity, t.explicit,
               1 - (t.embedding <=> (select embedding from seed)) as similarity
        from tracks t
        where t.embedding is not null
          and (select embedding from seed) is not null
          and t.spotify_track_id <> $2
          and t.spotify_track_id not in (select spotify_track_id from lib)
          and ($3 or t.explicit = false)
        order by t.embedding <=> (select embedding from seed)
        limit $4
        """,
        user_id, seed_track_id, allow_explicit, k,
    )
    return [
        {
            "spotify_track_id": r["spotify_track_id"],
            "title": r["title"],
            "artist": r["artist"],
            "album": r["album"],
            "image_url": r["image_url"],
            "external_url": r["external_url"],
            "popularity": r["popularity"] or 0,
            "explicit": r["explicit"],
            "similarity": float(r["similarity"]),
        }
        for r in rows
    ]


async def knn_taste_scores(user_id: str, track_ids: list[str], k: int) -> dict[str, float]:
    """kNN taste-fit: for each candidate id, the mean cosine similarity to its ``k``
    nearest tracks in the user's library. Higher = closer to what they already play.
    Returns {track_id: score}; candidates without an embedding are omitted; an empty
    library yields 0.0."""
    if not track_ids:
        return {}
    rows = await pool.fetch(
        f"""
        with lib as (
            select t.embedding
            from ({_LIBRARY_IDS_SQL}) owned
            join tracks t on t.spotify_track_id = owned.spotify_track_id
            where t.embedding is not null
        )
        select c.spotify_track_id,
               coalesce((
                   select avg(1 - d) from (
                       select (l.embedding <=> c.embedding) as d
                       from lib l
                       order by d
                       limit $2
                   ) nearest
               ), 0) as taste_score
        from tracks c
        where c.spotify_track_id = any($3::text[]) and c.embedding is not null
        """,
        user_id, k, track_ids,
    )
    return {r["spotify_track_id"]: float(r["taste_score"]) for r in rows}


# --- taste profile & candidates (playlist builder) ---

# A user's tracks across sources, each weighted by how strong a taste signal it is.
_USER_TRACKS_CTE = """
    with user_tracks as (
        select spotify_track_id, 3::numeric as w from user_saved_tracks where user_id = $1
        union all
        select spotify_track_id, 3::numeric from user_top_tracks where user_id = $1
        union all
        select pt.spotify_track_id, 2::numeric
        from playlist_tracks pt
        join user_playlists up
            on up.spotify_playlist_id = pt.spotify_playlist_id and up.user_id = $1
        union all
        select spotify_track_id, 1::numeric from play_history where user_id = $1
    )
"""

# Distinct set of track ids the user already has (any source) — for de-duping discovery.
_LIBRARY_IDS_SQL = """
    select spotify_track_id from user_saved_tracks where user_id = $1
    union
    select spotify_track_id from user_top_tracks where user_id = $1
    union
    select pt.spotify_track_id
    from playlist_tracks pt
    join user_playlists up
        on up.spotify_playlist_id = pt.spotify_playlist_id and up.user_id = $1
"""


async def get_genre_weights(user_id: str) -> list[dict[str, Any]]:
    """Genre -> summed taste weight, highest first."""
    rows = await pool.fetch(
        _USER_TRACKS_CTE
        + """
        select ag.genre, sum(ut.w) as weight
        from user_tracks ut
        join track_artists ta on ta.spotify_track_id = ut.spotify_track_id
        join artist_genres ag on ag.spotify_artist_id = ta.spotify_artist_id
        group by ag.genre
        order by weight desc
        """,
        user_id,
    )
    return [{"genre": r["genre"], "weight": float(r["weight"])} for r in rows]


async def get_artist_weights(user_id: str) -> list[dict[str, Any]]:
    """Artist -> summed taste weight (from tracks + top artists), highest first."""
    rows = await pool.fetch(
        _USER_TRACKS_CTE
        + """
        , from_tracks as (
            select ta.spotify_artist_id, sum(ut.w) as weight
            from user_tracks ut
            join track_artists ta on ta.spotify_track_id = ut.spotify_track_id
            group by ta.spotify_artist_id
        ),
        combined as (
            select spotify_artist_id, weight from from_tracks
            union all
            select spotify_artist_id, 3::numeric from user_top_artists where user_id = $1
        )
        select a.spotify_artist_id, a.name, sum(c.weight) as weight
        from combined c
        join artists a on a.spotify_artist_id = c.spotify_artist_id
        group by a.spotify_artist_id, a.name
        order by weight desc
        """,
        user_id,
    )
    return [
        {"spotify_artist_id": r["spotify_artist_id"], "name": r["name"], "weight": float(r["weight"])}
        for r in rows
    ]


async def get_library_track_ids(user_id: str) -> set[str]:
    rows = await pool.fetch(_LIBRARY_IDS_SQL, user_id)
    return {r["spotify_track_id"] for r in rows}


# Per-track artist ids (ordered by billing position, so [0] is the primary
# artist) and the union of those artists' genres.
_ARTIST_IDS_AND_GENRES_SQL = """
    coalesce((select array_agg(ta.spotify_artist_id order by ta.position)
              from track_artists ta
              where ta.spotify_track_id = t.spotify_track_id), '{}') as artist_ids,
    coalesce((select array_agg(distinct ag.genre)
              from track_artists ta
              join artist_genres ag on ag.spotify_artist_id = ta.spotify_artist_id
              where ta.spotify_track_id = t.spotify_track_id), '{}') as genres
"""


def _candidate_rows_to_dicts(rows: list[asyncpg.Record]) -> list[dict[str, Any]]:
    return [
        {
            "spotify_track_id": r["spotify_track_id"],
            "title": r["title"],
            "artist": r["artist"],
            "album": r["album"],
            "image_url": r["image_url"],
            "external_url": r["external_url"],
            "popularity": r["popularity"] or 0,
            "explicit": r["explicit"],
            "artist_ids": list(r["artist_ids"]),
            "genres": list(r["genres"]),
        }
        for r in rows
    ]


async def get_library_candidates(user_id: str, allow_explicit: bool) -> list[dict[str, Any]]:
    """The user's own stored tracks (familiar pool), each with its artist ids + genres."""
    rows = await pool.fetch(
        f"""
        with lib as ({_LIBRARY_IDS_SQL})
        select t.spotify_track_id, t.title, t.artist, t.album, t.image_url, t.external_url,
               t.popularity, t.explicit,
               {_ARTIST_IDS_AND_GENRES_SQL}
        from lib
        join tracks t on t.spotify_track_id = lib.spotify_track_id
        where ($2 or t.explicit = false)
        """,
        user_id, allow_explicit,
    )
    return _candidate_rows_to_dicts(rows)
