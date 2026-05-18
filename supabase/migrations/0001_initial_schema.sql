create extension if not exists pgcrypto;

create table if not exists app_users (
    id uuid primary key default gen_random_uuid(),
    spotify_user_id text not null unique,
    display_name text,
    email text,
    profile_image_url text,
    connected_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists spotify_tokens (
    user_id uuid primary key references app_users(id) on delete cascade,
    access_token_encrypted text not null,
    refresh_token_encrypted text not null,
    token_type text not null,
    scope text not null,
    expires_at timestamptz not null,
    updated_at timestamptz not null default now()
);

create table if not exists artists (
    spotify_artist_id text primary key,
    name text not null,
    genres text[] not null default '{}',
    image_url text,
    external_url text,
    updated_at timestamptz not null default now()
);

create table if not exists albums (
    spotify_album_id text primary key,
    name text not null,
    release_date text,
    image_url text,
    external_url text,
    updated_at timestamptz not null default now()
);

create table if not exists tracks (
    spotify_track_id text primary key,
    album_id text references albums(spotify_album_id),
    name text not null,
    duration_ms integer not null,
    explicit boolean not null default false,
    popularity integer,
    external_url text,
    updated_at timestamptz not null default now()
);

create table if not exists track_artists (
    track_id text not null references tracks(spotify_track_id) on delete cascade,
    artist_id text not null references artists(spotify_artist_id) on delete cascade,
    artist_order integer not null,
    primary key (track_id, artist_id)
);

create table if not exists play_events (
    id bigint generated always as identity primary key,
    user_id uuid not null references app_users(id) on delete cascade,
    track_id text not null references tracks(spotify_track_id),
    played_at timestamptz not null,
    context_uri text,
    source text not null default 'spotify_recently_played',
    inserted_at timestamptz not null default now(),
    unique (user_id, played_at, track_id)
);

create index if not exists ix_play_events_user_played_at
    on play_events (user_id, played_at desc);

create table if not exists sync_runs (
    id bigint generated always as identity primary key,
    user_id uuid not null references app_users(id) on delete cascade,
    requested_by text not null,
    started_at timestamptz not null default now(),
    completed_at timestamptz,
    status text not null,
    fetched_count integer not null default 0,
    inserted_count integer not null default 0,
    error_message text
);

create index if not exists ix_sync_runs_user_started_at
    on sync_runs (user_id, started_at desc);

create table if not exists daily_user_totals (
    user_id uuid not null references app_users(id) on delete cascade,
    stat_date date not null,
    play_count integer not null default 0,
    listening_ms bigint not null default 0,
    unique_tracks integer not null default 0,
    unique_artists integer not null default 0,
    morning_ms bigint not null default 0,
    afternoon_ms bigint not null default 0,
    evening_ms bigint not null default 0,
    late_night_ms bigint not null default 0,
    first_played_at timestamptz,
    last_played_at timestamptz,
    rebuilt_at timestamptz not null default now(),
    primary key (user_id, stat_date)
);

create table if not exists daily_user_track_stats (
    user_id uuid not null references app_users(id) on delete cascade,
    stat_date date not null,
    track_id text not null references tracks(spotify_track_id),
    play_count integer not null default 0,
    listening_ms bigint not null default 0,
    primary key (user_id, stat_date, track_id)
);

create table if not exists daily_user_artist_stats (
    user_id uuid not null references app_users(id) on delete cascade,
    stat_date date not null,
    artist_id text not null references artists(spotify_artist_id),
    play_count integer not null default 0,
    listening_ms bigint not null default 0,
    primary key (user_id, stat_date, artist_id)
);

create table if not exists daily_user_album_stats (
    user_id uuid not null references app_users(id) on delete cascade,
    stat_date date not null,
    album_id text not null references albums(spotify_album_id),
    play_count integer not null default 0,
    listening_ms bigint not null default 0,
    primary key (user_id, stat_date, album_id)
);

create table if not exists daily_user_genre_stats (
    user_id uuid not null references app_users(id) on delete cascade,
    stat_date date not null,
    genre text not null,
    play_count integer not null default 0,
    listening_ms bigint not null default 0,
    primary key (user_id, stat_date, genre)
);
