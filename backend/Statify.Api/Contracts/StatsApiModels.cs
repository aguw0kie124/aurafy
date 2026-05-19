namespace Statify.Api.Contracts;

public sealed record DashboardSummaryResponse(
    long TotalMinutes,
    int ArtistsDiscovered,
    string? CurrentArtist,
    int? CurrentRank,
    string? CurrentArtistImageUrl,
    int TotalPlays,
    int UniqueTracks,
    DateTimeOffset? LastPlayedAt,
    DateTimeOffset? LastSyncedAt);

public sealed record TimeOfDayStatsResponse(
    string Label,
    int Value,
    long ListeningMinutes);

public sealed record RecapResponse(
    DashboardSummaryResponse Summary,
    IReadOnlyList<TimeOfDayStatsResponse> TimeOfDay);

public sealed record SyncRunResponse(
    long Id,
    string Status,
    int FetchedCount,
    int InsertedCount,
    DateTimeOffset StartedAt,
    DateTimeOffset? CompletedAt,
    string? ErrorMessage);

public sealed record SpotifyTopItemsResponse(
    string Range,
    IReadOnlyList<SpotifyTopTrackResponse> Tracks,
    IReadOnlyList<SpotifyTopArtistResponse> Artists,
    IReadOnlyList<SpotifyTopAlbumResponse> Albums);

public sealed record SpotifyTopTrackResponse(
    string? SpotifyTrackId,
    string Title,
    string Artist,
    string Album,
    string? CoverUrl,
    string? ExternalUrl,
    int SpotifyRank,
    string Source);

public sealed record SpotifyTopArtistResponse(
    string? SpotifyArtistId,
    string Name,
    string? ImageUrl,
    string? ExternalUrl,
    int SpotifyRank,
    int TopTrackCount,
    string Source);

public sealed record SpotifyTopAlbumResponse(
    string? SpotifyAlbumId,
    string Title,
    string Artist,
    string? CoverUrl,
    string? ExternalUrl,
    int SpotifyRank,
    int TopTrackCount,
    string Source);
