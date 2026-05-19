namespace Statify.Api.Services;

public static class StatsRange
{
    public const string ShortTerm = "short_term";
    public const string MediumTerm = "medium_term";
    public const string LongTerm = "long_term";

    public static string Normalize(string? range)
    {
        return range?.Trim().ToLowerInvariant() switch
        {
            ShortTerm or "short" or "4_weeks" or "4weeks" or "four_weeks" => ShortTerm,
            MediumTerm or "medium" or "6_months" or "6months" or "six_months" => MediumTerm,
            LongTerm or "long" or "all_time" or "alltime" => LongTerm,
            _ => ShortTerm
        };
    }

    public static DateTime? GetStartDate(string? range, DateTimeOffset now)
    {
        return Normalize(range) switch
        {
            ShortTerm => now.UtcDateTime.Date.AddDays(-28),
            MediumTerm => now.UtcDateTime.Date.AddMonths(-6),
            LongTerm => null,
            _ => now.UtcDateTime.Date.AddDays(-28)
        };
    }
}
