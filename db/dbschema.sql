-- Aurafy database schema. Paste into the Supabase SQL editor and run once.

create extension if not exists pgcrypto;
-- pgvector: semantic embeddings for the recommender's vector space.
create extension if not exists vector;

create table if not exists app_users (
    id uuid primary key default gen_random_uuid(),
    spotify_user_id text not null unique,
    display_name text,
    image_url text,
    created_at timestamptz not null default now()
);

-- Spotify OAuth tokens, encrypted at rest with TOKEN_ENCRYPTION_KEY (Fernet).
create table if not exists spotify_tokens (
    user_id uuid primary key references app_users(id) on delete cascade,
    access_token_encrypted text not null,
    refresh_token_encrypted text not null,
    expires_at timestamptz not null,
    updated_at timestamptz not null default now()
);

-- Server-side sessions; id is the value of the session cookie.
create table if not exists sessions (
    id text primary key,
    user_id uuid not null references app_users(id) on delete cascade,
    expires_at timestamptz not null,
    created_at timestamptz not null default now()
);

-- Track catalog. `artist` is the denormalized display string; the normalized
-- track -> artist links live in track_artists.
create table if not exists tracks (
    spotify_track_id text primary key,
    title text not null,
    artist text not null,
    album text,
    image_url text,
    external_url text,
    popularity integer,
    explicit boolean not null default false,
    duration_ms integer,
    updated_at timestamptz not null default now()
);

-- Add duration_ms if upgrading an existing tracks table.
alter table tracks add column if not exists duration_ms integer;

-- Gemini text-embedding-004 vector (768-dim) of the track's text doc; NULL until embedded.
alter table tracks add column if not exists embedding vector(768);

-- Artists referenced by any stored track or top list (with genres for the
-- content signal the recommender/playlist builder needs).
create table if not exists artists (
    spotify_artist_id text primary key,
    name text not null,
    image_url text,
    external_url text,
    popularity integer,
    updated_at timestamptz not null default now()
);

-- Gemini text-embedding-004 vector (768-dim) of the artist's text doc; NULL until embedded.
alter table artists add column if not exists embedding vector(768);

create table if not exists artist_genres (
    spotify_artist_id text not null references artists(spotify_artist_id) on delete cascade,
    genre text not null,
    primary key (spotify_artist_id, genre)
);

-- Track <-> artist relationship (position 0 = primary artist).
create table if not exists track_artists (
    spotify_track_id text not null references tracks(spotify_track_id) on delete cascade,
    spotify_artist_id text not null references artists(spotify_artist_id) on delete cascade,
    position integer not null default 0,
    primary key (spotify_track_id, spotify_artist_id)
);

-- The user's saved/liked songs.
create table if not exists user_saved_tracks (
    user_id uuid not null references app_users(id) on delete cascade,
    spotify_track_id text not null references tracks(spotify_track_id) on delete cascade,
    saved_at timestamptz,
    primary key (user_id, spotify_track_id)
);

-- The user's playlists.
create table if not exists user_playlists (
    user_id uuid not null references app_users(id) on delete cascade,
    spotify_playlist_id text not null,
    name text,
    track_total integer,
    updated_at timestamptz not null default now(),
    primary key (user_id, spotify_playlist_id)
);

-- Tracks inside a playlist.
create table if not exists playlist_tracks (
    spotify_playlist_id text not null,
    spotify_track_id text not null references tracks(spotify_track_id) on delete cascade,
    position integer not null default 0,
    primary key (spotify_playlist_id, spotify_track_id)
);

-- Top tracks/artists snapshot per time range (short_term / medium_term / long_term).
create table if not exists user_top_tracks (
    user_id uuid not null references app_users(id) on delete cascade,
    spotify_track_id text not null references tracks(spotify_track_id) on delete cascade,
    time_range text not null,
    rank integer not null,
    captured_at timestamptz not null default now(),
    primary key (user_id, spotify_track_id, time_range)
);

create table if not exists user_top_artists (
    user_id uuid not null references app_users(id) on delete cascade,
    spotify_artist_id text not null references artists(spotify_artist_id) on delete cascade,
    time_range text not null,
    rank integer not null,
    captured_at timestamptz not null default now(),
    primary key (user_id, spotify_artist_id, time_range)
);

-- Recently-played history (append-only).
create table if not exists play_history (
    user_id uuid not null references app_users(id) on delete cascade,
    spotify_track_id text not null references tracks(spotify_track_id) on delete cascade,
    played_at timestamptz not null,
    primary key (user_id, spotify_track_id, played_at)
);

create index if not exists ix_user_saved_tracks_user on user_saved_tracks(user_id);
create index if not exists ix_track_artists_artist on track_artists(spotify_artist_id);
create index if not exists ix_play_history_user on play_history(user_id);

-- Approximate-nearest-neighbor index for catalog/discovery vector search (cosine).
create index if not exists ix_tracks_embedding
    on tracks using hnsw (embedding vector_cosine_ops);
