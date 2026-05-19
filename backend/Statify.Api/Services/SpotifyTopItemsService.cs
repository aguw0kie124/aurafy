using Statify.Api.Contracts;

namespace Statify.Api.Services;

public sealed class SpotifyTopItemsService(SpotifyWebApiClient spotifyWebApiClient)
{
    public async Task<SpotifyTopItemsResponse> GetTopItemsAsync(
        string accessToken,
        string? range,
        int limit,
        CancellationToken cancellationToken)
    {
        var normalizedRange = StatsRange.Normalize(range);
        var clampedLimit = Math.Clamp(limit, 1, 50);
        var tracksTask = spotifyWebApiClient.GetTopTracksAsync(
            accessToken,
            normalizedRange,
            clampedLimit,
            cancellationToken);
        var artistsTask = spotifyWebApiClient.GetTopArtistsAsync(
            accessToken,
            normalizedRange,
            clampedLimit,
            cancellationToken);

        await Task.WhenAll(tracksTask, artistsTask);

        var trackResponse = await tracksTask;
        var artistResponse = await artistsTask;
        var tracks = trackResponse.Items
            .Select((track, index) => ToTrackResponse(track, index + 1))
            .Where(track => !string.IsNullOrWhiteSpace(track.Title))
            .ToList();
        var artists = artistResponse.Items
            .Select((artist, index) => ToArtistResponse(artist, index + 1))
            .Where(artist => !string.IsNullOrWhiteSpace(artist.Name))
            .ToList();
        var albums = BuildAlbums(trackResponse.Items);

        return new SpotifyTopItemsResponse(normalizedRange, tracks, artists, albums);
    }

    private static IReadOnlyList<SpotifyTopAlbumResponse> BuildAlbums(IReadOnlyList<SpotifyTrackObject> tracks)
    {
        var albumsByKey = new Dictionary<string, AlbumAggregate>(StringComparer.Ordinal);

        for (var trackIndex = 0; trackIndex < tracks.Count; trackIndex++)
        {
            var track = tracks[trackIndex];
            var album = track.Album;

            if (album is null || string.IsNullOrWhiteSpace(album.Name))
            {
                continue;
            }

            var trackRank = trackIndex + 1;
            var score = tracks.Count - trackIndex;
            var artist = string.Join(", ", track.Artists.Select(artist => artist.Name).Where(name => !string.IsNullOrWhiteSpace(name)));
            var key = album.Id ?? $"{album.Name}|{artist}";

            if (!albumsByKey.TryGetValue(key, out var aggregate))
            {
                aggregate = new AlbumAggregate(
                    SpotifyAlbumId: album.Id,
                    Title: album.Name,
                    Artist: string.IsNullOrWhiteSpace(artist) ? "Unknown artist" : artist,
                    CoverUrl: SelectImageUrl(album.Images),
                    ExternalUrl: album.ExternalUrls?.Spotify);
                albumsByKey[key] = aggregate;
            }

            aggregate.Score += score;
            aggregate.TopTrackCount += 1;
            aggregate.BestTrackRank = Math.Min(aggregate.BestTrackRank, trackRank);
        }

        return albumsByKey.Values
            .OrderByDescending(album => album.Score)
            .ThenBy(album => album.BestTrackRank)
            .ThenBy(album => album.Title)
            .Select((album, index) => new SpotifyTopAlbumResponse(
                album.SpotifyAlbumId,
                album.Title,
                album.Artist,
                album.CoverUrl,
                album.ExternalUrl,
                index + 1,
                album.TopTrackCount,
                "spotify_derived"))
            .ToList();
    }

    private static SpotifyTopTrackResponse ToTrackResponse(SpotifyTrackObject track, int rank)
    {
        var artist = string.Join(", ", track.Artists.Select(artist => artist.Name).Where(name => !string.IsNullOrWhiteSpace(name)));

        return new SpotifyTopTrackResponse(
            track.Id,
            track.Name,
            string.IsNullOrWhiteSpace(artist) ? "Unknown artist" : artist,
            track.Album?.Name ?? "Unknown album",
            SelectImageUrl(track.Album?.Images ?? []),
            track.ExternalUrls?.Spotify,
            rank,
            "spotify");
    }

    private static SpotifyTopArtistResponse ToArtistResponse(SpotifyArtistObject artist, int rank)
    {
        return new SpotifyTopArtistResponse(
            artist.Id,
            artist.Name,
            SelectImageUrl(artist.Images),
            artist.ExternalUrls?.Spotify,
            rank,
            0,
            "spotify");
    }

    private static string? SelectImageUrl(IReadOnlyList<SpotifyImageResponse> images)
    {
        return images
            .OrderByDescending(image => (image.Width ?? 0) * (image.Height ?? 0))
            .Select(image => image.Url)
            .FirstOrDefault(url => !string.IsNullOrWhiteSpace(url));
    }

    private sealed record AlbumAggregate(
        string? SpotifyAlbumId,
        string Title,
        string Artist,
        string? CoverUrl,
        string? ExternalUrl)
    {
        public int BestTrackRank { get; set; } = int.MaxValue;

        public int Score { get; set; }

        public int TopTrackCount { get; set; }
    }
}
