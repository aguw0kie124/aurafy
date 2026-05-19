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

public sealed record TrackStatsResponse(
    string SpotifyTrackId,
    string Title,
    string Artist,
    string? Album,
    int Plays,
    long ListeningMinutes,
    string? CoverUrl,
    string? ExternalUrl);

public sealed record ArtistStatsResponse(
    string SpotifyArtistId,
    string Name,
    int Plays,
    long ListeningMinutes,
    string? ImageUrl,
    string? ExternalUrl);

public sealed record AlbumStatsResponse(
    string SpotifyAlbumId,
    string Title,
    string Artist,
    int Plays,
    long ListeningMinutes,
    string? CoverUrl,
    string? ExternalUrl);

public sealed record TimeOfDayStatsResponse(
    string Label,
    int Value,
    long ListeningMinutes);

public sealed record RecapResponse(
    DashboardSummaryResponse Summary,
    IReadOnlyList<TrackStatsResponse> TopTracks,
    IReadOnlyList<ArtistStatsResponse> TopArtists,
    IReadOnlyList<AlbumStatsResponse> TopAlbums,
    IReadOnlyList<TimeOfDayStatsResponse> TimeOfDay);

public sealed record SyncRunResponse(
    long Id,
    string Status,
    int FetchedCount,
    int InsertedCount,
    DateTimeOffset StartedAt,
    DateTimeOffset? CompletedAt,
    string? ErrorMessage);
