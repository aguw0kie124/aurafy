using Dapper;
using Statify.Api.Contracts;

namespace Statify.Api.Data;

public sealed class StatsRepository(PostgresConnectionFactory connectionFactory)
{
    public async Task<DashboardSummaryResponse> GetDashboardSummaryAsync(
        Guid userId,
        DateTime? startDate,
        CancellationToken cancellationToken)
    {
        await using var connection = await connectionFactory.OpenConnectionAsync(cancellationToken);

        var filter = BuildDateFilter("d", startDate);
        var parameters = new { UserId = userId, StartDate = startDate };

        var totals = await connection.QuerySingleAsync<DashboardTotalsRecord>(
            new CommandDefinition(
                $"""
                select
                    coalesce(sum(d.play_count), 0)::int as "TotalPlays",
                    coalesce(sum(d.listening_ms), 0)::bigint as "ListeningMs",
                    max(d.last_played_at) as "LastPlayedAt"
                from daily_user_totals d
                where d.user_id = @UserId
                {filter};
                """,
                parameters,
                cancellationToken: cancellationToken));

        var uniqueTracks = await connection.QuerySingleAsync<int>(
            new CommandDefinition(
                $"""
                select count(distinct d.track_id)::int
                from daily_user_track_stats d
                where d.user_id = @UserId
                {filter};
                """,
                parameters,
                cancellationToken: cancellationToken));

        var topGenre = await connection.QuerySingleOrDefaultAsync<string?>(
            new CommandDefinition(
                $"""
                select d.genre
                from daily_user_genre_stats d
                where d.user_id = @UserId
                {filter}
                group by d.genre
                order by sum(d.listening_ms) desc, sum(d.play_count) desc, d.genre
                limit 1;
                """,
                parameters,
                cancellationToken: cancellationToken));

        var topArtist = await connection.QuerySingleOrDefaultAsync<TopArtistRecord>(
            new CommandDefinition(
                $"""
                select
                    a.name as "Name",
                    a.image_url as "ImageUrl"
                from daily_user_artist_stats d
                join artists a on a.spotify_artist_id = d.artist_id
                where d.user_id = @UserId
                {filter}
                group by a.spotify_artist_id, a.name, a.image_url
                order by sum(d.listening_ms) desc, sum(d.play_count) desc, a.name
                limit 1;
                """,
                parameters,
                cancellationToken: cancellationToken));

        var uniqueArtists = await connection.QuerySingleAsync<int>(
            new CommandDefinition(
                $"""
                select count(distinct d.artist_id)::int
                from daily_user_artist_stats d
                where d.user_id = @UserId
                {filter};
                """,
                parameters,
                cancellationToken: cancellationToken));

        var lastSyncedAt = await connection.QuerySingleOrDefaultAsync<DateTime?>(
            new CommandDefinition(
                """
                select max(completed_at)
                from sync_runs
                where user_id = @UserId
                    and status = 'completed';
                """,
                new { UserId = userId },
                cancellationToken: cancellationToken));

        return new DashboardSummaryResponse(
            TotalMinutes: ToMinutes(totals.ListeningMs),
            ArtistsDiscovered: uniqueArtists,
            TopGenre: topGenre,
            CurrentArtist: topArtist?.Name,
            CurrentRank: topArtist is null ? null : 1,
            CurrentArtistImageUrl: topArtist?.ImageUrl,
            TotalPlays: totals.TotalPlays,
            UniqueTracks: uniqueTracks,
            LastPlayedAt: totals.LastPlayedAt is null ? null : DbDateTime.ToUtcOffset(totals.LastPlayedAt.Value),
            LastSyncedAt: lastSyncedAt is null ? null : DbDateTime.ToUtcOffset(lastSyncedAt.Value));
    }

    public async Task<IReadOnlyList<TrackStatsResponse>> GetTopTracksAsync(
        Guid userId,
        DateTime? startDate,
        int limit,
        CancellationToken cancellationToken)
    {
        await using var connection = await connectionFactory.OpenConnectionAsync(cancellationToken);
        var filter = BuildDateFilter("d", startDate);

        var rows = await connection.QueryAsync<TrackStatsResponse>(
            new CommandDefinition(
                $"""
                with stats as (
                    select
                        d.track_id,
                        sum(d.play_count)::int as plays,
                        sum(d.listening_ms)::bigint as listening_ms
                    from daily_user_track_stats d
                    where d.user_id = @UserId
                    {filter}
                    group by d.track_id
                )
                select
                    t.spotify_track_id as "SpotifyTrackId",
                    t.name as "Title",
                    coalesce(string_agg(ar.name, ', ' order by ta.artist_order), 'Unknown Artist') as "Artist",
                    al.name as "Album",
                    s.plays as "Plays",
                    round(s.listening_ms / 60000.0)::bigint as "ListeningMinutes",
                    al.image_url as "CoverUrl",
                    t.external_url as "ExternalUrl"
                from stats s
                join tracks t on t.spotify_track_id = s.track_id
                left join albums al on al.spotify_album_id = t.album_id
                left join track_artists ta on ta.track_id = t.spotify_track_id
                left join artists ar on ar.spotify_artist_id = ta.artist_id
                group by
                    t.spotify_track_id,
                    t.name,
                    al.name,
                    al.image_url,
                    t.external_url,
                    s.plays,
                    s.listening_ms
                order by s.listening_ms desc, s.plays desc, t.name
                limit @Limit;
                """,
                new { UserId = userId, StartDate = startDate, Limit = ClampLimit(limit) },
                cancellationToken: cancellationToken));

        return rows.AsList();
    }

    public async Task<IReadOnlyList<ArtistStatsResponse>> GetTopArtistsAsync(
        Guid userId,
        DateTime? startDate,
        int limit,
        CancellationToken cancellationToken)
    {
        await using var connection = await connectionFactory.OpenConnectionAsync(cancellationToken);
        var filter = BuildDateFilter("d", startDate);

        var rows = await connection.QueryAsync<ArtistStatsResponse>(
            new CommandDefinition(
                $"""
                with stats as (
                    select
                        d.artist_id,
                        sum(d.play_count)::int as plays,
                        sum(d.listening_ms)::bigint as listening_ms
                    from daily_user_artist_stats d
                    where d.user_id = @UserId
                    {filter}
                    group by d.artist_id
                )
                select
                    a.spotify_artist_id as "SpotifyArtistId",
                    a.name as "Name",
                    s.plays as "Plays",
                    round(s.listening_ms / 60000.0)::bigint as "ListeningMinutes",
                    a.image_url as "ImageUrl",
                    a.external_url as "ExternalUrl"
                from stats s
                join artists a on a.spotify_artist_id = s.artist_id
                order by s.listening_ms desc, s.plays desc, a.name
                limit @Limit;
                """,
                new { UserId = userId, StartDate = startDate, Limit = ClampLimit(limit) },
                cancellationToken: cancellationToken));

        return rows.AsList();
    }

    public async Task<IReadOnlyList<AlbumStatsResponse>> GetTopAlbumsAsync(
        Guid userId,
        DateTime? startDate,
        int limit,
        CancellationToken cancellationToken)
    {
        await using var connection = await connectionFactory.OpenConnectionAsync(cancellationToken);
        var filter = BuildDateFilter("d", startDate);

        var rows = await connection.QueryAsync<AlbumStatsResponse>(
            new CommandDefinition(
                $"""
                with stats as (
                    select
                        d.album_id,
                        sum(d.play_count)::int as plays,
                        sum(d.listening_ms)::bigint as listening_ms
                    from daily_user_album_stats d
                    where d.user_id = @UserId
                    {filter}
                    group by d.album_id
                ),
                album_artists as (
                    select
                        t.album_id,
                        string_agg(distinct ar.name, ', ') as artist
                    from tracks t
                    join track_artists ta on ta.track_id = t.spotify_track_id
                    join artists ar on ar.spotify_artist_id = ta.artist_id
                    where t.album_id is not null
                    group by t.album_id
                )
                select
                    al.spotify_album_id as "SpotifyAlbumId",
                    al.name as "Title",
                    coalesce(album_artists.artist, 'Unknown Artist') as "Artist",
                    s.plays as "Plays",
                    round(s.listening_ms / 60000.0)::bigint as "ListeningMinutes",
                    al.image_url as "CoverUrl",
                    al.external_url as "ExternalUrl"
                from stats s
                join albums al on al.spotify_album_id = s.album_id
                left join album_artists on album_artists.album_id = al.spotify_album_id
                where lower(coalesce(al.album_type, 'album')) <> 'single'
                    and coalesce(al.total_tracks, 2) > 1
                order by s.listening_ms desc, s.plays desc, al.name
                limit @Limit;
                """,
                new { UserId = userId, StartDate = startDate, Limit = ClampLimit(limit) },
                cancellationToken: cancellationToken));

        return rows.AsList();
    }

    public async Task<IReadOnlyList<GenreStatsResponse>> GetTopGenresAsync(
        Guid userId,
        DateTime? startDate,
        int limit,
        CancellationToken cancellationToken)
    {
        await using var connection = await connectionFactory.OpenConnectionAsync(cancellationToken);
        var filter = BuildDateFilter("d", startDate);

        var rows = await connection.QueryAsync<GenreStatsResponse>(
            new CommandDefinition(
                $"""
                with stats as (
                    select
                        d.genre,
                        sum(d.play_count)::int as plays,
                        sum(d.listening_ms)::bigint as listening_ms
                    from daily_user_genre_stats d
                    where d.user_id = @UserId
                    {filter}
                    group by d.genre
                ),
                totals as (
                    select coalesce(sum(listening_ms), 0)::bigint as total_listening_ms
                    from stats
                )
                select
                    stats.genre as "Label",
                    least(
                        100,
                        greatest(
                            1,
                            round(stats.listening_ms * 100.0 / nullif(totals.total_listening_ms, 0))::int
                        )
                    ) as "Value",
                    stats.plays as "Plays",
                    round(stats.listening_ms / 60000.0)::bigint as "ListeningMinutes"
                from stats
                cross join totals
                where totals.total_listening_ms > 0
                order by stats.listening_ms desc, stats.plays desc, stats.genre
                limit @Limit;
                """,
                new { UserId = userId, StartDate = startDate, Limit = ClampLimit(limit) },
                cancellationToken: cancellationToken));

        return rows.AsList();
    }

    public async Task<IReadOnlyList<TimeOfDayStatsResponse>> GetTimeOfDayStatsAsync(
        Guid userId,
        DateTime? startDate,
        CancellationToken cancellationToken)
    {
        await using var connection = await connectionFactory.OpenConnectionAsync(cancellationToken);
        var filter = BuildDateFilter("d", startDate);

        var totals = await connection.QuerySingleAsync<TimeOfDayTotalsRecord>(
            new CommandDefinition(
                $"""
                select
                    coalesce(sum(d.morning_ms), 0)::bigint as "MorningMs",
                    coalesce(sum(d.afternoon_ms), 0)::bigint as "AfternoonMs",
                    coalesce(sum(d.evening_ms), 0)::bigint as "EveningMs",
                    coalesce(sum(d.late_night_ms), 0)::bigint as "LateNightMs"
                from daily_user_totals d
                where d.user_id = @UserId
                {filter};
                """,
                new { UserId = userId, StartDate = startDate },
                cancellationToken: cancellationToken));

        var totalMs = totals.MorningMs + totals.AfternoonMs + totals.EveningMs + totals.LateNightMs;

        return
        [
            BuildTimeOfDay("Morning", totals.MorningMs, totalMs),
            BuildTimeOfDay("Afternoon", totals.AfternoonMs, totalMs),
            BuildTimeOfDay("Evening", totals.EveningMs, totalMs),
            BuildTimeOfDay("Late night", totals.LateNightMs, totalMs)
        ];
    }

    public async Task<RecapResponse> GetRecapAsync(
        Guid userId,
        DateTime? startDate,
        CancellationToken cancellationToken)
    {
        var summary = await GetDashboardSummaryAsync(userId, startDate, cancellationToken);
        var tracks = await GetTopTracksAsync(userId, startDate, 5, cancellationToken);
        var artists = await GetTopArtistsAsync(userId, startDate, 5, cancellationToken);
        var albums = await GetTopAlbumsAsync(userId, startDate, 5, cancellationToken);
        var genres = await GetTopGenresAsync(userId, startDate, 5, cancellationToken);
        var timeOfDay = await GetTimeOfDayStatsAsync(userId, startDate, cancellationToken);

        return new RecapResponse(summary, tracks, artists, albums, genres, timeOfDay);
    }

    private static TimeOfDayStatsResponse BuildTimeOfDay(string label, long listeningMs, long totalMs)
    {
        var value = totalMs <= 0 ? 0 : (int)Math.Round(listeningMs * 100.0 / totalMs);

        return new TimeOfDayStatsResponse(label, value, ToMinutes(listeningMs));
    }

    private static string BuildDateFilter(string alias, DateTime? startDate)
    {
        return startDate is null ? string.Empty : $"and {alias}.stat_date >= @StartDate::date";
    }

    private static int ClampLimit(int limit) => Math.Clamp(limit, 1, 50);

    private static long ToMinutes(long milliseconds) => (long)Math.Round(milliseconds / 60000.0);
}

public sealed record DashboardTotalsRecord(
    int TotalPlays,
    long ListeningMs,
    DateTime? LastPlayedAt);

public sealed record TopArtistRecord(
    string Name,
    string? ImageUrl);

public sealed record TimeOfDayTotalsRecord(
    long MorningMs,
    long AfternoonMs,
    long EveningMs,
    long LateNightMs);
