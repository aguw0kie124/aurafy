using Dapper;
using Statify.Api.Contracts;

namespace Statify.Api.Data;

public sealed class StatsRepository(PostgresConnectionFactory connectionFactory)
{
    public async Task<RecapResponse> GetRecapAsync(
        Guid userId,
        DateTime? startDate,
        CancellationToken cancellationToken)
    {
        await using var connection = await connectionFactory.OpenConnectionAsync(cancellationToken);

        var dateFilter = startDate is null ? string.Empty : "and pe.played_at >= @StartDate::timestamptz";
        var parameters = new { UserId = userId, StartDate = startDate };

        // 1. Get totals
        var totals = await connection.QuerySingleOrDefaultAsync<dynamic>(
            new CommandDefinition(
                $"""
                select
                    count(*)::int as "TotalPlays",
                    coalesce(sum(t.duration_ms), 0)::bigint as "ListeningMs",
                    max(pe.played_at) as "LastPlayedAt"
                from play_events pe
                join tracks t on t.spotify_track_id = pe.track_id
                where pe.user_id = @UserId
                {dateFilter};
                """,
                parameters,
                cancellationToken: cancellationToken));

        int totalPlays = totals?.TotalPlays ?? 0;
        long listeningMs = totals?.ListeningMs ?? 0;
        DateTime? lastPlayedAt = totals?.LastPlayedAt;

        // 2. Get top artist
        var topArtist = await connection.QuerySingleOrDefaultAsync<dynamic>(
            new CommandDefinition(
                $"""
                select
                    a.name as "Name",
                    a.image_url as "ImageUrl"
                from play_events pe
                join tracks t on t.spotify_track_id = pe.track_id
                join track_artists ta on ta.track_id = t.spotify_track_id and ta.artist_order = 0
                join artists a on a.spotify_artist_id = ta.artist_id
                where pe.user_id = @UserId
                {dateFilter}
                group by a.spotify_artist_id, a.name, a.image_url
                order by sum(t.duration_ms) desc, count(pe.id) desc, a.name
                limit 1;
                """,
                parameters,
                cancellationToken: cancellationToken));

        string? currentArtist = topArtist?.Name;
        string? currentArtistImageUrl = topArtist?.ImageUrl;

        // 3. Get last sync time
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

        var summary = new DashboardSummaryResponse(
            TotalMinutes: (long)Math.Round(listeningMs / 60000.0),
            ArtistsDiscovered: 0,
            CurrentArtist: currentArtist,
            CurrentRank: currentArtist is null ? null : 1,
            CurrentArtistImageUrl: currentArtistImageUrl,
            TotalPlays: totalPlays,
            UniqueTracks: 0,
            LastPlayedAt: lastPlayedAt is null ? null : DbDateTime.ToUtcOffset(lastPlayedAt.Value),
            LastSyncedAt: lastSyncedAt is null ? null : DbDateTime.ToUtcOffset(lastSyncedAt.Value));

        // 4. Get time of day breakdown
        var hourlyStats = await connection.QuerySingleOrDefaultAsync<dynamic>(
            new CommandDefinition(
                $"""
                with hourly as (
                    select
                        extract(hour from pe.played_at at time zone 'UTC')::int as played_hour,
                        t.duration_ms
                    from play_events pe
                    join tracks t on t.spotify_track_id = pe.track_id
                    where pe.user_id = @UserId
                    {dateFilter}
                )
                select
                    coalesce(sum(case when played_hour between 5 and 11 then duration_ms else 0 end), 0)::bigint as "MorningMs",
                    coalesce(sum(case when played_hour between 12 and 16 then duration_ms else 0 end), 0)::bigint as "AfternoonMs",
                    coalesce(sum(case when played_hour between 17 and 21 then duration_ms else 0 end), 0)::bigint as "EveningMs",
                    coalesce(sum(case when played_hour >= 22 or played_hour < 5 then duration_ms else 0 end), 0)::bigint as "LateNightMs"
                from hourly;
                """,
                parameters,
                cancellationToken: cancellationToken));

        long morningMs = hourlyStats?.MorningMs ?? 0;
        long afternoonMs = hourlyStats?.AfternoonMs ?? 0;
        long eveningMs = hourlyStats?.EveningMs ?? 0;
        long lateNightMs = hourlyStats?.LateNightMs ?? 0;
        long totalMs = morningMs + afternoonMs + eveningMs + lateNightMs;

        var timeOfDay = new List<TimeOfDayStatsResponse>
        {
            BuildTimeOfDay("Morning", morningMs, totalMs),
            BuildTimeOfDay("Afternoon", afternoonMs, totalMs),
            BuildTimeOfDay("Evening", eveningMs, totalMs),
            BuildTimeOfDay("Late night", lateNightMs, totalMs)
        };

        return new RecapResponse(summary, timeOfDay);
    }

    private static TimeOfDayStatsResponse BuildTimeOfDay(string label, long listeningMs, long totalMs)
    {
        var value = totalMs <= 0 ? 0 : (int)Math.Round(listeningMs * 100.0 / totalMs);
        return new TimeOfDayStatsResponse(label, value, (long)Math.Round(listeningMs / 60000.0));
    }
}
