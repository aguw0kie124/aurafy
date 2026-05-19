using Dapper;

namespace Statify.Api.Data;

public sealed class SpotifyListeningRepository(PostgresConnectionFactory connectionFactory)
{
    public async Task<DateTimeOffset?> GetLatestPlayedAtAsync(
        Guid userId,
        CancellationToken cancellationToken)
    {
        await using var connection = await connectionFactory.OpenConnectionAsync(cancellationToken);

        return await connection.QuerySingleOrDefaultAsync<DateTimeOffset?>(
            new CommandDefinition(
                """
                select max(played_at)
                from play_events
                where user_id = @UserId;
                """,
                new { UserId = userId },
                cancellationToken: cancellationToken));
    }

    public async Task<SyncRunRecord> StartSyncRunAsync(
        Guid userId,
        string requestedBy,
        CancellationToken cancellationToken)
    {
        await using var connection = await connectionFactory.OpenConnectionAsync(cancellationToken);

        return await connection.QuerySingleAsync<SyncRunRecord>(
            new CommandDefinition(
                """
                insert into sync_runs (user_id, requested_by, status)
                values (@UserId, @RequestedBy, 'running')
                returning
                    id as "Id",
                    status as "Status",
                    fetched_count as "FetchedCount",
                    inserted_count as "InsertedCount",
                    started_at as "StartedAt",
                    completed_at as "CompletedAt",
                    error_message as "ErrorMessage";
                """,
                new { UserId = userId, RequestedBy = requestedBy },
                cancellationToken: cancellationToken));
    }

    public async Task<SyncRunRecord> CompleteSyncRunAsync(
        long syncRunId,
        int fetchedCount,
        int insertedCount,
        CancellationToken cancellationToken)
    {
        await using var connection = await connectionFactory.OpenConnectionAsync(cancellationToken);

        return await connection.QuerySingleAsync<SyncRunRecord>(
            new CommandDefinition(
                """
                update sync_runs
                set
                    status = 'completed',
                    fetched_count = @FetchedCount,
                    inserted_count = @InsertedCount,
                    completed_at = now(),
                    error_message = null
                where id = @SyncRunId
                returning
                    id as "Id",
                    status as "Status",
                    fetched_count as "FetchedCount",
                    inserted_count as "InsertedCount",
                    started_at as "StartedAt",
                    completed_at as "CompletedAt",
                    error_message as "ErrorMessage";
                """,
                new
                {
                    SyncRunId = syncRunId,
                    FetchedCount = fetchedCount,
                    InsertedCount = insertedCount
                },
                cancellationToken: cancellationToken));
    }

    public async Task<SyncRunRecord> FailSyncRunAsync(
        long syncRunId,
        int fetchedCount,
        int insertedCount,
        string errorMessage,
        CancellationToken cancellationToken)
    {
        await using var connection = await connectionFactory.OpenConnectionAsync(cancellationToken);

        return await connection.QuerySingleAsync<SyncRunRecord>(
            new CommandDefinition(
                """
                update sync_runs
                set
                    status = 'failed',
                    fetched_count = @FetchedCount,
                    inserted_count = @InsertedCount,
                    completed_at = now(),
                    error_message = @ErrorMessage
                where id = @SyncRunId
                returning
                    id as "Id",
                    status as "Status",
                    fetched_count as "FetchedCount",
                    inserted_count as "InsertedCount",
                    started_at as "StartedAt",
                    completed_at as "CompletedAt",
                    error_message as "ErrorMessage";
                """,
                new
                {
                    SyncRunId = syncRunId,
                    FetchedCount = fetchedCount,
                    InsertedCount = insertedCount,
                    ErrorMessage = errorMessage
                },
                cancellationToken: cancellationToken));
    }

    public async Task<int> UpsertPlaybackBatchAsync(
        Guid userId,
        IReadOnlyCollection<SpotifyPlaybackWriteModel> playbacks,
        CancellationToken cancellationToken)
    {
        if (playbacks.Count == 0)
        {
            return 0;
        }

        await using var connection = await connectionFactory.OpenConnectionAsync(cancellationToken);
        await using var transaction = await connection.BeginTransactionAsync(cancellationToken);

        var insertedCount = 0;

        foreach (var playback in playbacks)
        {
            await UpsertAlbumAsync(connection, transaction, playback.Album, cancellationToken);

            foreach (var artist in playback.Artists)
            {
                await UpsertArtistAsync(connection, transaction, artist, cancellationToken);
            }

            await UpsertTrackAsync(connection, transaction, playback.Track, cancellationToken);
            await UpsertTrackArtistsAsync(
                connection,
                transaction,
                playback.Track.SpotifyTrackId,
                playback.Artists,
                cancellationToken);

            insertedCount += await connection.ExecuteAsync(
                new CommandDefinition(
                    """
                    insert into play_events (user_id, track_id, played_at, context_uri)
                    values (@UserId, @TrackId, @PlayedAt, @ContextUri)
                    on conflict (user_id, played_at, track_id) do nothing;
                    """,
                    new
                    {
                        UserId = userId,
                        TrackId = playback.Track.SpotifyTrackId,
                        playback.PlayedAt,
                        playback.ContextUri
                    },
                    transaction,
                    cancellationToken: cancellationToken));
        }

        await transaction.CommitAsync(cancellationToken);

        return insertedCount;
    }

    public async Task RebuildDailyAggregatesAsync(Guid userId, CancellationToken cancellationToken)
    {
        await using var connection = await connectionFactory.OpenConnectionAsync(cancellationToken);
        await using var transaction = await connection.BeginTransactionAsync(cancellationToken);

        var parameters = new { UserId = userId };

        foreach (var tableName in new[]
        {
            "daily_user_genre_stats",
            "daily_user_album_stats",
            "daily_user_artist_stats",
            "daily_user_track_stats",
            "daily_user_totals"
        })
        {
            await connection.ExecuteAsync(
                new CommandDefinition(
                    $"delete from {tableName} where user_id = @UserId;",
                    parameters,
                    transaction,
                    cancellationToken: cancellationToken));
        }

        await connection.ExecuteAsync(
            new CommandDefinition(
                """
                insert into daily_user_totals (
                    user_id,
                    stat_date,
                    play_count,
                    listening_ms,
                    unique_tracks,
                    unique_artists,
                    morning_ms,
                    afternoon_ms,
                    evening_ms,
                    late_night_ms,
                    first_played_at,
                    last_played_at
                )
                with event_base as (
                    select
                        pe.user_id,
                        (pe.played_at at time zone 'UTC')::date as stat_date,
                        pe.track_id,
                        pe.played_at,
                        t.duration_ms,
                        extract(hour from pe.played_at at time zone 'UTC')::int as played_hour
                    from play_events pe
                    join tracks t on t.spotify_track_id = pe.track_id
                    where pe.user_id = @UserId
                ),
                totals as (
                    select
                        user_id,
                        stat_date,
                        count(*)::int as play_count,
                        coalesce(sum(duration_ms), 0)::bigint as listening_ms,
                        count(distinct track_id)::int as unique_tracks,
                        coalesce(sum(case when played_hour between 5 and 11 then duration_ms else 0 end), 0)::bigint as morning_ms,
                        coalesce(sum(case when played_hour between 12 and 16 then duration_ms else 0 end), 0)::bigint as afternoon_ms,
                        coalesce(sum(case when played_hour between 17 and 21 then duration_ms else 0 end), 0)::bigint as evening_ms,
                        coalesce(sum(case when played_hour >= 22 or played_hour < 5 then duration_ms else 0 end), 0)::bigint as late_night_ms,
                        min(played_at) as first_played_at,
                        max(played_at) as last_played_at
                    from event_base
                    group by user_id, stat_date
                ),
                artist_uniques as (
                    select
                        eb.user_id,
                        eb.stat_date,
                        count(distinct ta.artist_id)::int as unique_artists
                    from event_base eb
                    join track_artists ta on ta.track_id = eb.track_id
                    group by eb.user_id, eb.stat_date
                )
                select
                    totals.user_id,
                    totals.stat_date,
                    totals.play_count,
                    totals.listening_ms,
                    totals.unique_tracks,
                    coalesce(artist_uniques.unique_artists, 0),
                    totals.morning_ms,
                    totals.afternoon_ms,
                    totals.evening_ms,
                    totals.late_night_ms,
                    totals.first_played_at,
                    totals.last_played_at
                from totals
                left join artist_uniques
                    on artist_uniques.user_id = totals.user_id
                    and artist_uniques.stat_date = totals.stat_date;
                """,
                parameters,
                transaction,
                cancellationToken: cancellationToken));

        await connection.ExecuteAsync(
            new CommandDefinition(
                """
                insert into daily_user_track_stats (user_id, stat_date, track_id, play_count, listening_ms)
                select
                    pe.user_id,
                    (pe.played_at at time zone 'UTC')::date as stat_date,
                    pe.track_id,
                    count(*)::int as play_count,
                    coalesce(sum(t.duration_ms), 0)::bigint as listening_ms
                from play_events pe
                join tracks t on t.spotify_track_id = pe.track_id
                where pe.user_id = @UserId
                group by pe.user_id, stat_date, pe.track_id;
                """,
                parameters,
                transaction,
                cancellationToken: cancellationToken));

        await connection.ExecuteAsync(
            new CommandDefinition(
                """
                insert into daily_user_artist_stats (user_id, stat_date, artist_id, play_count, listening_ms)
                select
                    pe.user_id,
                    (pe.played_at at time zone 'UTC')::date as stat_date,
                    ta.artist_id,
                    count(*)::int as play_count,
                    coalesce(sum(t.duration_ms), 0)::bigint as listening_ms
                from play_events pe
                join tracks t on t.spotify_track_id = pe.track_id
                join track_artists ta on ta.track_id = pe.track_id
                where pe.user_id = @UserId
                group by pe.user_id, stat_date, ta.artist_id;
                """,
                parameters,
                transaction,
                cancellationToken: cancellationToken));

        await connection.ExecuteAsync(
            new CommandDefinition(
                """
                insert into daily_user_album_stats (user_id, stat_date, album_id, play_count, listening_ms)
                select
                    pe.user_id,
                    (pe.played_at at time zone 'UTC')::date as stat_date,
                    t.album_id,
                    count(*)::int as play_count,
                    coalesce(sum(t.duration_ms), 0)::bigint as listening_ms
                from play_events pe
                join tracks t on t.spotify_track_id = pe.track_id
                where pe.user_id = @UserId
                    and t.album_id is not null
                group by pe.user_id, stat_date, t.album_id;
                """,
                parameters,
                transaction,
                cancellationToken: cancellationToken));

        await connection.ExecuteAsync(
            new CommandDefinition(
                """
                insert into daily_user_genre_stats (user_id, stat_date, genre, play_count, listening_ms)
                select
                    pe.user_id,
                    (pe.played_at at time zone 'UTC')::date as stat_date,
                    genre.value as genre,
                    count(*)::int as play_count,
                    coalesce(sum(t.duration_ms), 0)::bigint as listening_ms
                from play_events pe
                join tracks t on t.spotify_track_id = pe.track_id
                join track_artists ta on ta.track_id = pe.track_id
                join artists a on a.spotify_artist_id = ta.artist_id
                cross join lateral unnest(a.genres) as genre(value)
                where pe.user_id = @UserId
                    and genre.value <> ''
                group by pe.user_id, stat_date, genre.value;
                """,
                parameters,
                transaction,
                cancellationToken: cancellationToken));

        await transaction.CommitAsync(cancellationToken);
    }

    private static Task UpsertAlbumAsync(
        Npgsql.NpgsqlConnection connection,
        Npgsql.NpgsqlTransaction transaction,
        SpotifyAlbumWriteModel? album,
        CancellationToken cancellationToken)
    {
        if (album is null)
        {
            return Task.CompletedTask;
        }

        return connection.ExecuteAsync(
            new CommandDefinition(
                """
                insert into albums (spotify_album_id, name, release_date, image_url, external_url)
                values (@SpotifyAlbumId, @Name, @ReleaseDate, @ImageUrl, @ExternalUrl)
                on conflict (spotify_album_id) do update set
                    name = excluded.name,
                    release_date = excluded.release_date,
                    image_url = coalesce(excluded.image_url, albums.image_url),
                    external_url = coalesce(excluded.external_url, albums.external_url),
                    updated_at = now();
                """,
                album,
                transaction,
                cancellationToken: cancellationToken));
    }

    private static Task UpsertArtistAsync(
        Npgsql.NpgsqlConnection connection,
        Npgsql.NpgsqlTransaction transaction,
        SpotifyArtistWriteModel artist,
        CancellationToken cancellationToken)
    {
        return connection.ExecuteAsync(
            new CommandDefinition(
                """
                insert into artists (spotify_artist_id, name, genres, image_url, external_url)
                values (@SpotifyArtistId, @Name, @Genres, @ImageUrl, @ExternalUrl)
                on conflict (spotify_artist_id) do update set
                    name = excluded.name,
                    genres = case
                        when cardinality(excluded.genres) > 0 then excluded.genres
                        else artists.genres
                    end,
                    image_url = coalesce(excluded.image_url, artists.image_url),
                    external_url = coalesce(excluded.external_url, artists.external_url),
                    updated_at = now();
                """,
                artist,
                transaction,
                cancellationToken: cancellationToken));
    }

    private static Task UpsertTrackAsync(
        Npgsql.NpgsqlConnection connection,
        Npgsql.NpgsqlTransaction transaction,
        SpotifyTrackWriteModel track,
        CancellationToken cancellationToken)
    {
        return connection.ExecuteAsync(
            new CommandDefinition(
                """
                insert into tracks (
                    spotify_track_id,
                    album_id,
                    name,
                    duration_ms,
                    explicit,
                    popularity,
                    external_url
                )
                values (
                    @SpotifyTrackId,
                    @AlbumId,
                    @Name,
                    @DurationMs,
                    @Explicit,
                    @Popularity,
                    @ExternalUrl
                )
                on conflict (spotify_track_id) do update set
                    album_id = excluded.album_id,
                    name = excluded.name,
                    duration_ms = excluded.duration_ms,
                    explicit = excluded.explicit,
                    popularity = excluded.popularity,
                    external_url = coalesce(excluded.external_url, tracks.external_url),
                    updated_at = now();
                """,
                track,
                transaction,
                cancellationToken: cancellationToken));
    }

    private static async Task UpsertTrackArtistsAsync(
        Npgsql.NpgsqlConnection connection,
        Npgsql.NpgsqlTransaction transaction,
        string trackId,
        IReadOnlyList<SpotifyArtistWriteModel> artists,
        CancellationToken cancellationToken)
    {
        for (var index = 0; index < artists.Count; index++)
        {
            await connection.ExecuteAsync(
                new CommandDefinition(
                    """
                    insert into track_artists (track_id, artist_id, artist_order)
                    values (@TrackId, @ArtistId, @ArtistOrder)
                    on conflict (track_id, artist_id) do update set
                        artist_order = excluded.artist_order;
                    """,
                    new
                    {
                        TrackId = trackId,
                        ArtistId = artists[index].SpotifyArtistId,
                        ArtistOrder = index
                    },
                    transaction,
                    cancellationToken: cancellationToken));
        }
    }
}

public sealed record SpotifyPlaybackWriteModel(
    SpotifyTrackWriteModel Track,
    SpotifyAlbumWriteModel? Album,
    IReadOnlyList<SpotifyArtistWriteModel> Artists,
    DateTimeOffset PlayedAt,
    string? ContextUri);

public sealed record SpotifyTrackWriteModel(
    string SpotifyTrackId,
    string? AlbumId,
    string Name,
    int DurationMs,
    bool Explicit,
    int? Popularity,
    string? ExternalUrl);

public sealed record SpotifyAlbumWriteModel(
    string SpotifyAlbumId,
    string Name,
    string? ReleaseDate,
    string? ImageUrl,
    string? ExternalUrl);

public sealed record SpotifyArtistWriteModel(
    string SpotifyArtistId,
    string Name,
    string[] Genres,
    string? ImageUrl,
    string? ExternalUrl);

public sealed record SyncRunRecord(
    long Id,
    string Status,
    int FetchedCount,
    int InsertedCount,
    DateTimeOffset StartedAt,
    DateTimeOffset? CompletedAt,
    string? ErrorMessage);
