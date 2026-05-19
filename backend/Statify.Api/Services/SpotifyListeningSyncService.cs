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

            var artistIds = playbacks
                .SelectMany(playback => playback.Track.Artists)
                .Select(artist => artist.Id)
                .Where(id => !string.IsNullOrWhiteSpace(id))
                .Cast<string>()
                .Distinct(StringComparer.Ordinal)
                .ToArray();

            var hydratedArtistsById = await TryGetHydratedArtistsByIdAsync(
                accessToken,
                artistIds,
                cancellationToken);
            var topArtistsById = await TryGetTopArtistsByIdAsync(accessToken, cancellationToken);
            var simpleArtistsById = playbacks
                .SelectMany(playback => playback.Track.Artists)
                .Where(artist => !string.IsNullOrWhiteSpace(artist.Id))
                .GroupBy(artist => artist.Id!, StringComparer.Ordinal)
                .ToDictionary(group => group.Key, group => group.First(), StringComparer.Ordinal);

            foreach (var (artistId, artist) in topArtistsById)
            {
                hydratedArtistsById[artistId] = artist;
            }

            await SearchMissingArtistMetadataAsync(
                accessToken,
                simpleArtistsById,
                hydratedArtistsById,
                cancellationToken);

            var writeModels = playbacks
                .Select(playback => ToWriteModel(playback.Item, playback.Track, hydratedArtistsById))
                .Where(model => model is not null)
                .Cast<SpotifyPlaybackWriteModel>()
                .ToList();

            insertedCount = await spotifyListeningRepository.UpsertPlaybackBatchAsync(
                userId,
                writeModels,
                cancellationToken);
            await spotifyListeningRepository.UpsertArtistsAsync(
                topArtistsById.Values.Select(ToArtistWriteModel).ToArray(),
                cancellationToken);

            await spotifyListeningRepository.RebuildDailyAggregatesAsync(userId, cancellationToken);

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

    private async Task<Dictionary<string, SpotifyArtistObject>> TryGetHydratedArtistsByIdAsync(
        string accessToken,
        IReadOnlyCollection<string> artistIds,
        CancellationToken cancellationToken)
    {
        try
        {
            var hydratedArtists = await spotifyWebApiClient.GetArtistsByIdsAsync(
                accessToken,
                artistIds,
                cancellationToken);

            return hydratedArtists
                .Where(artist => !string.IsNullOrWhiteSpace(artist.Id))
                .ToDictionary(artist => artist.Id!, StringComparer.Ordinal);
        }
        catch (SpotifyApiException exception) when (exception.StatusCode == System.Net.HttpStatusCode.Forbidden)
        {
            logger.LogWarning(
                exception,
                "Spotify bulk artist hydration was forbidden. Trying single-artist hydration. Response body: {ResponseBody}",
                exception.ResponseBody);

            return await TryGetArtistsIndividuallyByIdAsync(
                accessToken,
                artistIds,
                cancellationToken);
        }
    }

    private async Task<Dictionary<string, SpotifyArtistObject>> TryGetArtistsIndividuallyByIdAsync(
        string accessToken,
        IReadOnlyCollection<string> artistIds,
        CancellationToken cancellationToken)
    {
        var artists = new Dictionary<string, SpotifyArtistObject>(StringComparer.Ordinal);

        foreach (var artistId in artistIds)
        {
            try
            {
                var artist = await spotifyWebApiClient.GetArtistByIdAsync(
                    accessToken,
                    artistId,
                    cancellationToken);

                if (!string.IsNullOrWhiteSpace(artist.Id))
                {
                    artists[artist.Id] = artist;
                }
            }
            catch (SpotifyApiException exception)
            {
                logger.LogWarning(
                    exception,
                    "Spotify single-artist hydration failed for {ArtistId}. Continuing with other artists. Response body: {ResponseBody}",
                    artistId,
                    exception.ResponseBody);
            }
        }

        return artists;
    }

    private async Task<Dictionary<string, SpotifyArtistObject>> TryGetTopArtistsByIdAsync(
        string accessToken,
        CancellationToken cancellationToken)
    {
        var artists = new Dictionary<string, SpotifyArtistObject>(StringComparer.Ordinal);

        foreach (var range in new[] { StatsRange.ShortTerm, StatsRange.MediumTerm, StatsRange.LongTerm })
        {
            try
            {
                var response = await spotifyWebApiClient.GetTopArtistsAsync(
                    accessToken,
                    range,
                    50,
                    cancellationToken);

                foreach (var artist in response.Items.Where(artist => !string.IsNullOrWhiteSpace(artist.Id)))
                {
                    artists[artist.Id!] = artist;
                }
            }
            catch (SpotifyApiException exception)
            {
                logger.LogWarning(
                    exception,
                    "Spotify top artists enrichment failed for {Range}. Continuing without that artist metadata. Response body: {ResponseBody}",
                    range,
                    exception.ResponseBody);
            }
        }

        return artists;
    }

    private async Task SearchMissingArtistMetadataAsync(
        string accessToken,
        IReadOnlyDictionary<string, SpotifySimpleArtistObject> simpleArtistsById,
        Dictionary<string, SpotifyArtistObject> hydratedArtistsById,
        CancellationToken cancellationToken)
    {
        foreach (var (artistId, simpleArtist) in simpleArtistsById)
        {
            if (hydratedArtistsById.TryGetValue(artistId, out var hydratedArtist) &&
                HasUsefulArtistMetadata(hydratedArtist))
            {
                continue;
            }

            try
            {
                var matches = await spotifyWebApiClient.SearchArtistsAsync(
                    accessToken,
                    $"artist:{simpleArtist.Name}",
                    5,
                    cancellationToken);
                var match = matches.FirstOrDefault(artist => string.Equals(artist.Id, artistId, StringComparison.Ordinal)) ??
                    matches.FirstOrDefault(artist => string.Equals(artist.Name, simpleArtist.Name, StringComparison.OrdinalIgnoreCase));

                if (match is not null && HasUsefulArtistMetadata(match))
                {
                    hydratedArtistsById[artistId] = match;
                }
            }
            catch (SpotifyApiException exception)
            {
                logger.LogWarning(
                    exception,
                    "Spotify artist search enrichment failed for {ArtistName}. Continuing with simplified artist data. Response body: {ResponseBody}",
                    simpleArtist.Name,
                    exception.ResponseBody);
            }
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

    private static SpotifyArtistWriteModel ToArtistWriteModel(SpotifyArtistObject artist)
    {
        return new SpotifyArtistWriteModel(
            artist.Id!,
            artist.Name,
            artist.Genres.ToArray(),
            SelectImageUrl(artist.Images),
            artist.ExternalUrls?.Spotify);
    }

    private static bool HasUsefulArtistMetadata(SpotifyArtistObject artist)
    {
        return artist.Genres.Count > 0 || artist.Images.Count > 0;
    }

    private static string? SelectImageUrl(IReadOnlyList<SpotifyImageResponse> images)
    {
        return images
            .OrderByDescending(image => image.Width ?? 0)
            .ThenByDescending(image => image.Height ?? 0)
            .FirstOrDefault()
            ?.Url;
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
