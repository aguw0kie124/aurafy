using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.WebUtilities;
using Microsoft.Extensions.Options;
using Statify.Api.Options;

namespace Statify.Api.Services;

public sealed class SpotifyAuthService(
    HttpClient httpClient,
    IOptions<SpotifyOptions> spotifyOptions)
{
    public const string StateCookieName = "spotify_oauth_state";

    private static readonly string[] RequiredScopes =
    [
        "user-read-recently-played",
        "user-top-read"
    ];

    private readonly SpotifyOptions _spotifyOptions = spotifyOptions.Value;

    public IReadOnlyList<string> Scopes => RequiredScopes;

    public string CreateState()
    {
        var bytes = RandomNumberGenerator.GetBytes(32);
        return WebEncoders.Base64UrlEncode(bytes);
    }

    public string BuildAuthorizationUrl(string state)
    {
        var query = new Dictionary<string, string?>
        {
            ["response_type"] = "code",
            ["client_id"] = _spotifyOptions.ClientId,
            ["scope"] = string.Join(' ', RequiredScopes),
            ["redirect_uri"] = _spotifyOptions.RedirectUri,
            ["state"] = state
        };

        return QueryHelpers.AddQueryString("https://accounts.spotify.com/authorize", query);
    }

    public async Task<SpotifyTokenResponse> ExchangeCodeForTokensAsync(
        string code,
        CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, "https://accounts.spotify.com/api/token");
        request.Headers.Authorization = CreateBasicAuthHeader();
        request.Content = new FormUrlEncodedContent(new Dictionary<string, string>
        {
            ["grant_type"] = "authorization_code",
            ["code"] = code,
            ["redirect_uri"] = _spotifyOptions.RedirectUri
        });

        using var response = await httpClient.SendAsync(request, cancellationToken);
        var body = await response.Content.ReadAsStringAsync(cancellationToken);

        if (!response.IsSuccessStatusCode)
        {
            throw new SpotifyAuthException(
                $"Spotify token exchange failed with status {(int)response.StatusCode}.",
                body);
        }

        var tokenResponse = JsonSerializer.Deserialize<SpotifyTokenResponse>(body);

        return tokenResponse ?? throw new SpotifyAuthException(
            "Spotify returned an empty token response.",
            body);
    }

    public async Task<SpotifyUserProfileResponse> GetCurrentUserAsync(
        string accessToken,
        CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, "https://api.spotify.com/v1/me");
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);

        using var response = await httpClient.SendAsync(request, cancellationToken);
        var body = await response.Content.ReadAsStringAsync(cancellationToken);

        if (!response.IsSuccessStatusCode)
        {
            throw new SpotifyAuthException(
                $"Spotify profile request failed with status {(int)response.StatusCode}.",
                body);
        }

        var profile = JsonSerializer.Deserialize<SpotifyUserProfileResponse>(body);

        if (profile is null || string.IsNullOrWhiteSpace(profile.Id))
        {
            throw new SpotifyAuthException("Spotify returned an invalid profile response.", body);
        }

        return profile;
    }

    private AuthenticationHeaderValue CreateBasicAuthHeader()
    {
        var credentials = $"{_spotifyOptions.ClientId}:{_spotifyOptions.ClientSecret}";
        var encodedCredentials = Convert.ToBase64String(Encoding.UTF8.GetBytes(credentials));

        return new AuthenticationHeaderValue("Basic", encodedCredentials);
    }
}

public sealed record SpotifyTokenResponse(
    [property: JsonPropertyName("access_token")] string AccessToken,
    [property: JsonPropertyName("token_type")] string TokenType,
    [property: JsonPropertyName("scope")] string Scope,
    [property: JsonPropertyName("expires_in")] int ExpiresInSeconds,
    [property: JsonPropertyName("refresh_token")] string? RefreshToken);

public sealed record SpotifyUserProfileResponse(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("display_name")] string? DisplayName,
    [property: JsonPropertyName("images")] IReadOnlyList<SpotifyImageResponse>? Images);

public sealed record SpotifyImageResponse(
    [property: JsonPropertyName("url")] string Url,
    [property: JsonPropertyName("height")] int? Height,
    [property: JsonPropertyName("width")] int? Width);

public sealed class SpotifyAuthException(string message, string responseBody) : Exception(message)
{
    public string ResponseBody { get; } = responseBody;
}
