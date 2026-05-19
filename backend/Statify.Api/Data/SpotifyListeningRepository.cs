using Dapper;

namespace Statify.Api.Data;

public sealed class SpotifyListeningRepository(PostgresConnectionFactory connectionFactory)
{
    public async Task<DateTimeOffset?> GetLatestPlayedAtAsync(
        Guid userId,
        CancellationToken cancellationToken)
    {
        await using var connection = await connectionFactory.OpenConnectionAsync(cancellationToken);

        var latestPlayedAt = await connection.QuerySingleOrDefaultAsync<DateTime?>(
            new CommandDefinition(
                """
                select max(played_at)
                from play_events
                where user_id = @UserId;
                """,
                new { UserId = userId },
                cancellationToken: cancellationToken));

        return latestPlayedAt is null ? null : DbDateTime.ToUtcOffset(latestPlayedAt.Value);
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



    private static Task UpsertAlbumAsync(
        Npgsql.NpgsqlConnection connection,
        Npgsql.NpgsqlTransaction? transaction,
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
                insert into albums (
                    spotify_album_id,
                    name,
                    release_date,
                    album_type,
                    total_tracks,
                    image_url,
                    external_url
                )
                values (
                    @SpotifyAlbumId,
                    @Name,
                    @ReleaseDate,
                    @AlbumType,
                    @TotalTracks,
                    @ImageUrl,
                    @ExternalUrl
                )
                on conflict (spotify_album_id) do update set
                    name = excluded.name,
                    release_date = excluded.release_date,
                    album_type = coalesce(excluded.album_type, albums.album_type),
                    total_tracks = coalesce(excluded.total_tracks, albums.total_tracks),
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
        Npgsql.NpgsqlTransaction? transaction,
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
    string? AlbumType,
    int? TotalTracks,
    string? ImageUrl,
    string? ExternalUrl);

public sealed record SpotifyArtistWriteModel(
    string SpotifyArtistId,
    string Name,
    string[] Genres,
    string? ImageUrl,
    string? ExternalUrl);

public sealed class SyncRunRecord
{
    public long Id { get; set; }

    public string Status { get; set; } = string.Empty;

    public int FetchedCount { get; set; }

    public int InsertedCount { get; set; }

    public DateTime StartedAt { get; set; }

    public DateTime? CompletedAt { get; set; }

    public string? ErrorMessage { get; set; }
}

internal static class DbDateTime
{
    public static DateTimeOffset ToUtcOffset(DateTime dateTime)
    {
        var utcDateTime = dateTime.Kind == DateTimeKind.Utc
            ? dateTime
            : DateTime.SpecifyKind(dateTime, DateTimeKind.Utc);

        return new DateTimeOffset(utcDateTime);
    }
}
