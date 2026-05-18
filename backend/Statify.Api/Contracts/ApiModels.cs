namespace Statify.Api.Contracts;

public sealed record HealthResponse(string Status, DateTimeOffset CheckedAtUtc);

public sealed record AppMetaResponse(
    string ProductName,
    bool SpotifyConfigured,
    IReadOnlyList<string> RequiredScopes);

public sealed record ManualRefreshResponse(
    string Status,
    DateTimeOffset QueuedAtUtc,
    int CooldownMinutes);

public sealed record PreviewStatsResponse(
    string RangeLabel,
    int ListeningMinutes,
    IReadOnlyList<RankedItemResponse> TopTracks,
    IReadOnlyList<RankedItemResponse> TopArtists,
    IReadOnlyList<TrendPointResponse> Trend);

public sealed record RankedItemResponse(
    string Name,
    string Detail,
    int Value,
    string Accent);

public sealed record TrendPointResponse(
    string Label,
    int Minutes);
