using Statify.Api.Contracts;
using Statify.Api.Data;

namespace Statify.Api.Services;

public sealed class SpotifyListeningSyncService(
    SpotifyAccountService spotifyAccountService,
    SpotifyWebApiClient spotifyWebApiClient,
    SpotifyListeningRepository spotifyListeningRepository,
    ILogger<SpotifyListeningSyncService> logger)
{
    public async Task<SyncRunResponse> SyncRecentlyPlayedAsync(
        Guid userId,
        string requestedBy,
        bool force,
        CancellationToken cancellationToken)
    {
        var syncRun = await spotifyListeningRepository.StartSyncRunAsync(
            userId,
            requestedBy,
            cancellationToken);

        var fetchedCount = 0;
        var insertedCount = 0;

        try
        {
            var accessToken = await spotifyAccountService.GetValidAccessTokenAsync(userId, cancellationToken);
            var after = force
                ? null
                : await spotifyListeningRepository.GetLatestPlayedAtAsync(userId, cancellationToken);
            
            var recentlyPlayed = await spotifyWebApiClient.GetRecentlyPlayedAsync(
                accessToken,
                after,
                50,
                cancellationToken);

            var playbacks = recentlyPlayed.Items
                .Where(item => item.Track is not null && !string.IsNullOrWhiteSpace(item.Track.Id))
                .Select(item => (Item: item, Track: item.Track!))
                .ToList();

            fetchedCount = playbacks.Count;

            if (fetchedCount > 0)
            {
                var artistIds = playbacks
                    .SelectMany(playback => playback.Track.Artists)
                    .Select(artist => artist.Id)
                    .Where(id => !string.IsNullOrWhiteSpace(id))
                    .Cast<string>()
                    .Distinct(StringComparer.Ordinal)
                    .ToArray();

                var hydratedArtistsById = new Dictionary<string, SpotifyArtistObject>(StringComparer.Ordinal);
                try
                {
                    var hydratedArtists = await spotifyWebApiClient.GetArtistsByIdsAsync(
                        accessToken,
                        artistIds,
                        cancellationToken);

                    foreach (var artist in hydratedArtists.Where(a => !string.IsNullOrWhiteSpace(a.Id)))
                    {
                        hydratedArtistsById[artist.Id!] = artist;
                    }
                }
                catch (Exception ex)
                {
                    logger.LogWarning(ex, "Failed to bulk hydrate artist metadata. Proceeding with basic metadata.");
                }

                var writeModels = playbacks
                    .Select(playback => ToWriteModel(playback.Item, playback.Track, hydratedArtistsById))
                    .Where(model => model is not null)
                    .Cast<SpotifyPlaybackWriteModel>()
                    .ToList();

                insertedCount = await spotifyListeningRepository.UpsertPlaybackBatchAsync(
                    userId,
                    writeModels,
                    cancellationToken);
            }

            var completedRun = await spotifyListeningRepository.CompleteSyncRunAsync(
                syncRun.Id,
                fetchedCount,
                insertedCount,
                cancellationToken);

            return ToResponse(completedRun);
        }
        catch (Exception exception)
        {
            logger.LogError(exception, "Spotify recently played sync failed for user {UserId}.", userId);

            var failedRun = await spotifyListeningRepository.FailSyncRunAsync(
                syncRun.Id,
                fetchedCount,
                insertedCount,
                exception.Message,
                CancellationToken.None);

            return ToResponse(failedRun);
        }
    }

    private static SpotifyPlaybackWriteModel? ToWriteModel(
        SpotifyPlayHistoryObject playHistory,
        SpotifyTrackObject track,
        IReadOnlyDictionary<string, SpotifyArtistObject> hydratedArtistsById)
    {
        if (string.IsNullOrWhiteSpace(track.Id) || string.IsNullOrWhiteSpace(track.Name))
        {
            return null;
        }

        var album = string.IsNullOrWhiteSpace(track.Album?.Id)
            ? null
            : new SpotifyAlbumWriteModel(
                track.Album.Id,
                track.Album.Name,
                track.Album.ReleaseDate,
                track.Album.AlbumType,
                track.Album.TotalTracks,
                SelectImageUrl(track.Album.Images),
                track.Album.ExternalUrls?.Spotify);

        var artists = track.Artists
            .Where(artist => !string.IsNullOrWhiteSpace(artist.Id))
            .Select(artist =>
            {
                var hydrated = hydratedArtistsById.GetValueOrDefault(artist.Id!);

                return new SpotifyArtistWriteModel(
                    artist.Id!,
                    string.IsNullOrWhiteSpace(hydrated?.Name) ? artist.Name : hydrated.Name,
                    hydrated?.Genres.ToArray() ?? [],
                    SelectImageUrl(hydrated?.Images ?? []),
                    hydrated?.ExternalUrls?.Spotify ?? artist.ExternalUrls?.Spotify);
            })
            .Where(artist => !string.IsNullOrWhiteSpace(artist.Name))
            .ToList();

        if (artists.Count == 0)
        {
            return null;
        }

        return new SpotifyPlaybackWriteModel(
            new SpotifyTrackWriteModel(
                track.Id,
                album?.SpotifyAlbumId,
                track.Name,
                track.DurationMs,
                track.Explicit,
                track.Popularity,
                track.ExternalUrls?.Spotify),
            album,
            artists,
            playHistory.PlayedAt,
            playHistory.Context?.Uri);
    }

    private static string? SelectImageUrl(IReadOnlyList<SpotifyImageResponse> images)
    {
        return images
            .OrderByDescending(image => (image.Width ?? 0) * (image.Height ?? 0))
            .Select(image => image.Url)
            .FirstOrDefault(url => !string.IsNullOrWhiteSpace(url));
    }

    private static SyncRunResponse ToResponse(SyncRunRecord syncRun)
    {
        return new SyncRunResponse(
            syncRun.Id,
            syncRun.Status,
            syncRun.FetchedCount,
            syncRun.InsertedCount,
            DbDateTime.ToUtcOffset(syncRun.StartedAt),
            syncRun.CompletedAt is null ? null : DbDateTime.ToUtcOffset(syncRun.CompletedAt.Value),
            syncRun.ErrorMessage);
    }
}
