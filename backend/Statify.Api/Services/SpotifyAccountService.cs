using Microsoft.AspNetCore.DataProtection;
using Statify.Api.Data;

namespace Statify.Api.Services;

public sealed class SpotifyAccountService(
    SpotifyAccountRepository spotifyAccountRepository,
    SpotifyAuthService spotifyAuthService,
    IDataProtectionProvider dataProtectionProvider)
{
    private static readonly TimeSpan ExpiryRefreshBuffer = TimeSpan.FromMinutes(1);

    private readonly IDataProtector _tokenProtector =
        dataProtectionProvider.CreateProtector("Statify.Api.SpotifyTokens.v1");

    public async Task<AppUserRecord> UpsertLoggedInUserAsync(
        SpotifyUserProfileResponse spotifyUser,
        string displayName,
        string? imageUrl,
        SpotifyTokenResponse tokens,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(tokens.RefreshToken))
        {
            throw new SpotifyAuthException("Spotify did not return a refresh token.", string.Empty);
        }

        var expiresAt = DateTimeOffset.UtcNow.AddSeconds(tokens.ExpiresInSeconds);

        return await spotifyAccountRepository.UpsertUserAndTokensAsync(
            new SpotifyUserWriteModel(
                spotifyUser.Id,
                displayName,
                imageUrl),
            new ProtectedSpotifyTokenWriteModel(
                Guid.Empty,
                _tokenProtector.Protect(tokens.AccessToken),
                _tokenProtector.Protect(tokens.RefreshToken),
                NormalizeTokenType(tokens.TokenType),
                NormalizeScope(tokens.Scope),
                expiresAt),
            cancellationToken);
    }

    public async Task<string> GetValidAccessTokenAsync(
        Guid userId,
        CancellationToken cancellationToken)
    {
        var tokens = await spotifyAccountRepository.GetTokensAsync(userId, cancellationToken)
            ?? throw new InvalidOperationException($"No Spotify tokens found for app user {userId}.");

        var expiresAt = DbDateTime.ToUtcOffset(tokens.ExpiresAt);

        if (expiresAt > DateTimeOffset.UtcNow.Add(ExpiryRefreshBuffer))
        {
            return _tokenProtector.Unprotect(tokens.AccessTokenEncrypted);
        }

        var refreshToken = _tokenProtector.Unprotect(tokens.RefreshTokenEncrypted);
        var refreshedTokens = await spotifyAuthService.RefreshAccessTokenAsync(refreshToken, cancellationToken);
        var refreshedAccessToken = refreshedTokens.AccessToken;

        await spotifyAccountRepository.UpdateTokensAsync(
            new ProtectedSpotifyTokenUpdateModel(
                userId,
                _tokenProtector.Protect(refreshedAccessToken),
                string.IsNullOrWhiteSpace(refreshedTokens.RefreshToken)
                    ? null
                    : _tokenProtector.Protect(refreshedTokens.RefreshToken),
                NormalizeTokenType(refreshedTokens.TokenType),
                string.IsNullOrWhiteSpace(refreshedTokens.Scope)
                    ? tokens.Scope
                    : refreshedTokens.Scope,
                DateTimeOffset.UtcNow.AddSeconds(refreshedTokens.ExpiresInSeconds)),
            cancellationToken);

        return refreshedAccessToken;
    }

    private static string NormalizeTokenType(string? tokenType) =>
        string.IsNullOrWhiteSpace(tokenType) ? "Bearer" : tokenType;

    private static string NormalizeScope(string? scope) =>
        string.IsNullOrWhiteSpace(scope) ? string.Empty : scope;
}
