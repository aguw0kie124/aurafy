using System.Globalization;
using System.Net;
using System.Net.Http.Headers;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.WebUtilities;

namespace Statify.Api.Services;

public sealed class SpotifyWebApiClient(HttpClient httpClient, ILogger<SpotifyWebApiClient> logger)
{
    private const int MaxAttempts = 3;

    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    public async Task<SpotifyUserProfileResponse> GetCurrentUserProfileAsync(
        string accessToken,
        CancellationToken cancellationToken)
    {
        var profile = await SendAsync<SpotifyUserProfileResponse>(
            () => CreateBearerRequest(HttpMethod.Get, "https://api.spotify.com/v1/me", accessToken),
            cancellationToken);

        if (string.IsNullOrWhiteSpace(profile.Id))
        {
            throw new SpotifyApiException(
                "Spotify returned an invalid profile response.",
                HttpStatusCode.OK,
                string.Empty,
                null);
        }

        return profile;
    }

    public Task<SpotifyPagingResponse<SpotifyTrackObject>> GetTopTracksAsync(
        string accessToken,
        string timeRange,
        int limit,
        CancellationToken cancellationToken)
    {
        return GetTopItemsAsync<SpotifyTrackObject>("tracks", accessToken, timeRange, limit, cancellationToken);
    }

    public Task<SpotifyPagingResponse<SpotifyArtistObject>> GetTopArtistsAsync(
        string accessToken,
        string timeRange,
        int limit,
        CancellationToken cancellationToken)
    {
        return GetTopItemsAsync<SpotifyArtistObject>("artists", accessToken, timeRange, limit, cancellationToken);
    }

    public Task<SpotifyRecentlyPlayedResponse> GetRecentlyPlayedAsync(
        string accessToken,
        DateTimeOffset? after,
        int limit,
        CancellationToken cancellationToken)
    {
        var query = new Dictionary<string, string?>
        {
            ["limit"] = ClampLimit(limit).ToString(CultureInfo.InvariantCulture)
        };

        if (after is not null)
        {
            query["after"] = after.Value.ToUnixTimeMilliseconds().ToString(CultureInfo.InvariantCulture);
        }

        var url = QueryHelpers.AddQueryString(
            "https://api.spotify.com/v1/me/player/recently-played",
            query);

        return SendAsync<SpotifyRecentlyPlayedResponse>(
            () => CreateBearerRequest(HttpMethod.Get, url, accessToken),
            cancellationToken);
    }

    public async Task<IReadOnlyList<SpotifyArtistObject>> GetArtistsByIdsAsync(
        string accessToken,
        IReadOnlyCollection<string> artistIds,
        CancellationToken cancellationToken)
    {
        if (artistIds.Count == 0)
        {
            return [];
        }

        var artists = new List<SpotifyArtistObject>();

        foreach (var batch in artistIds.Distinct(StringComparer.Ordinal).Chunk(50))
        {
            var url = QueryHelpers.AddQueryString(
                "https://api.spotify.com/v1/artists",
                new Dictionary<string, string?>
                {
                    ["ids"] = string.Join(',', batch)
                });

            var response = await SendAsync<SpotifyArtistsResponse>(
                () => CreateBearerRequest(HttpMethod.Get, url, accessToken),
                cancellationToken);

            artists.AddRange(response.Artists.Where(artist => !string.IsNullOrWhiteSpace(artist.Id)));
        }

        return artists;
    }



    private Task<SpotifyPagingResponse<T>> GetTopItemsAsync<T>(
        string type,
        string accessToken,
        string timeRange,
        int limit,
        CancellationToken cancellationToken)
    {
        var normalizedRange = StatsRange.Normalize(timeRange);
        var query = new Dictionary<string, string?>
        {
            ["time_range"] = normalizedRange,
            ["limit"] = ClampLimit(limit).ToString(CultureInfo.InvariantCulture)
        };

        var url = QueryHelpers.AddQueryString($"https://api.spotify.com/v1/me/top/{type}", query);

        return SendAsync<SpotifyPagingResponse<T>>(
            () => CreateBearerRequest(HttpMethod.Get, url, accessToken),
            cancellationToken);
    }

    private async Task<T> SendAsync<T>(
        Func<HttpRequestMessage> requestFactory,
        CancellationToken cancellationToken)
    {
        for (var attempt = 0; attempt < MaxAttempts; attempt++)
        {
            try
            {
                using var request = requestFactory();
                using var response = await httpClient.SendAsync(request, cancellationToken);
                var body = await response.Content.ReadAsStringAsync(cancellationToken);

                if (IsRetryableStatus(response.StatusCode) && attempt < MaxAttempts - 1)
                {
                    var retryAfter = GetRetryDelay(response, attempt);
                    logger.LogWarning(
                        "Spotify request returned {StatusCode}. Retrying attempt {Attempt}/{MaxAttempts} after {RetryAfterSeconds} seconds.",
                        (int)response.StatusCode,
                        attempt + 2,
                        MaxAttempts,
                        retryAfter.TotalSeconds);

                    await Task.Delay(retryAfter, cancellationToken);
                    continue;
                }

                if (!response.IsSuccessStatusCode)
                {
                    throw new SpotifyApiException(
                        $"Spotify API request failed with status {(int)response.StatusCode}.",
                        response.StatusCode,
                        body,
                        response.Headers.RetryAfter?.Delta);
                }

                var result = JsonSerializer.Deserialize<T>(body, JsonOptions);

                return result ?? throw new SpotifyApiException(
                    "Spotify returned an empty or invalid JSON response.",
                    response.StatusCode,
                    body,
                    null);
            }
            catch (HttpRequestException exception) when (attempt < MaxAttempts - 1)
            {
                var retryAfter = GetRetryDelay(null, attempt);
                logger.LogWarning(
                    exception,
                    "Spotify request failed before receiving a response. Retrying attempt {Attempt}/{MaxAttempts} after {RetryAfterSeconds} seconds.",
                    attempt + 2,
                    MaxAttempts,
                    retryAfter.TotalSeconds);

                await Task.Delay(retryAfter, cancellationToken);
            }
        }

        throw new SpotifyApiException(
            "Spotify API request failed after retries.",
            HttpStatusCode.ServiceUnavailable,
            string.Empty,
            null);
    }

    private static HttpRequestMessage CreateBearerRequest(HttpMethod method, string url, string accessToken)
    {
        var request = new HttpRequestMessage(method, url);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);

        return request;
    }

    private static int ClampLimit(int limit) => Math.Clamp(limit, 1, 50);

    private static bool IsRetryableStatus(HttpStatusCode statusCode)
    {
        return statusCode is
            HttpStatusCode.RequestTimeout or
            HttpStatusCode.TooManyRequests or
            HttpStatusCode.InternalServerError or
            HttpStatusCode.BadGateway or
            HttpStatusCode.ServiceUnavailable or
            HttpStatusCode.GatewayTimeout;
    }

    private static TimeSpan GetRetryDelay(HttpResponseMessage? response, int attempt)
    {
        var retryAfter = response?.Headers.RetryAfter?.Delta;
        var fallback = TimeSpan.FromSeconds(Math.Pow(2, attempt));
        var delay = retryAfter is null || retryAfter.Value <= TimeSpan.Zero ? fallback : retryAfter.Value;

        return delay > TimeSpan.FromSeconds(10) ? TimeSpan.FromSeconds(10) : delay;
    }
}

public sealed class SpotifyPagingResponse<T>
{
    [JsonPropertyName("href")]
    public string? Href { get; init; }

    [JsonPropertyName("limit")]
    public int Limit { get; init; }

    [JsonPropertyName("next")]
    public string? Next { get; init; }

    [JsonPropertyName("offset")]
    public int Offset { get; init; }

    [JsonPropertyName("previous")]
    public string? Previous { get; init; }

    [JsonPropertyName("total")]
    public int Total { get; init; }

    [JsonPropertyName("items")]
    public IReadOnlyList<T> Items { get; init; } = [];
}

public sealed class SpotifyRecentlyPlayedResponse
{
    [JsonPropertyName("href")]
    public string? Href { get; init; }

    [JsonPropertyName("limit")]
    public int Limit { get; init; }

    [JsonPropertyName("next")]
    public string? Next { get; init; }

    [JsonPropertyName("cursors")]
    public SpotifyCursorResponse? Cursors { get; init; }

    [JsonPropertyName("items")]
    public IReadOnlyList<SpotifyPlayHistoryObject> Items { get; init; } = [];
}

public sealed class SpotifyArtistsResponse
{
    [JsonPropertyName("artists")]
    public IReadOnlyList<SpotifyArtistObject> Artists { get; init; } = [];
}



public sealed class SpotifyCursorResponse
{
    [JsonPropertyName("after")]
    public string? After { get; init; }

    [JsonPropertyName("before")]
    public string? Before { get; init; }
}

public sealed class SpotifyPlayHistoryObject
{
    [JsonPropertyName("track")]
    public SpotifyTrackObject? Track { get; init; }

    [JsonPropertyName("played_at")]
    public DateTimeOffset PlayedAt { get; init; }

    [JsonPropertyName("context")]
    public SpotifyContextObject? Context { get; init; }
}

public sealed class SpotifyTrackObject
{
    [JsonPropertyName("id")]
    public string? Id { get; init; }

    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;

    [JsonPropertyName("duration_ms")]
    public int DurationMs { get; init; }

    [JsonPropertyName("explicit")]
    public bool Explicit { get; init; }

    [JsonPropertyName("popularity")]
    public int? Popularity { get; init; }

    [JsonPropertyName("external_urls")]
    public SpotifyExternalUrls? ExternalUrls { get; init; }

    [JsonPropertyName("album")]
    public SpotifyAlbumObject? Album { get; init; }

    [JsonPropertyName("artists")]
    public IReadOnlyList<SpotifySimpleArtistObject> Artists { get; init; } = [];
}

public sealed class SpotifyAlbumObject
{
    [JsonPropertyName("id")]
    public string? Id { get; init; }

    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;

    [JsonPropertyName("album_type")]
    public string? AlbumType { get; init; }

    [JsonPropertyName("total_tracks")]
    public int? TotalTracks { get; init; }

    [JsonPropertyName("release_date")]
    public string? ReleaseDate { get; init; }

    [JsonPropertyName("external_urls")]
    public SpotifyExternalUrls? ExternalUrls { get; init; }

    [JsonPropertyName("images")]
    public IReadOnlyList<SpotifyImageResponse> Images { get; init; } = [];
}

public sealed class SpotifySimpleArtistObject
{
    [JsonPropertyName("id")]
    public string? Id { get; init; }

    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;

    [JsonPropertyName("external_urls")]
    public SpotifyExternalUrls? ExternalUrls { get; init; }
}

public sealed class SpotifyArtistObject
{
    [JsonPropertyName("id")]
    public string? Id { get; init; }

    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;

    [JsonPropertyName("genres")]
    public IReadOnlyList<string> Genres { get; init; } = [];

    [JsonPropertyName("external_urls")]
    public SpotifyExternalUrls? ExternalUrls { get; init; }

    [JsonPropertyName("images")]
    public IReadOnlyList<SpotifyImageResponse> Images { get; init; } = [];
}

public sealed class SpotifyExternalUrls
{
    [JsonPropertyName("spotify")]
    public string? Spotify { get; init; }
}

public sealed class SpotifyContextObject
{
    [JsonPropertyName("uri")]
    public string? Uri { get; init; }
}

public sealed class SpotifyApiException(
    string message,
    HttpStatusCode statusCode,
    string responseBody,
    TimeSpan? retryAfter) : Exception(message)
{
    public HttpStatusCode StatusCode { get; } = statusCode;

    public string ResponseBody { get; } = responseBody;

    public TimeSpan? RetryAfter { get; } = retryAfter;
}
