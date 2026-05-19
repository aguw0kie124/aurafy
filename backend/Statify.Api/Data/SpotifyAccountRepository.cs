using Dapper;

namespace Statify.Api.Data;

public sealed class SpotifyAccountRepository(PostgresConnectionFactory connectionFactory)
{
    public async Task<AppUserRecord> UpsertUserAndTokensAsync(
        SpotifyUserWriteModel user,
        ProtectedSpotifyTokenWriteModel tokens,
        CancellationToken cancellationToken)
    {
        await using var connection = await connectionFactory.OpenConnectionAsync(cancellationToken);
        await using var transaction = await connection.BeginTransactionAsync(cancellationToken);

        var appUser = await connection.QuerySingleAsync<AppUserRecord>(
            new CommandDefinition(
                """
                insert into app_users (spotify_user_id, display_name, profile_image_url)
                values (@SpotifyUserId, @DisplayName, @ProfileImageUrl)
                on conflict (spotify_user_id) do update set
                    display_name = excluded.display_name,
                    profile_image_url = excluded.profile_image_url,
                    updated_at = now()
                returning
                    id as "Id",
                    spotify_user_id as "SpotifyUserId",
                    display_name as "DisplayName",
                    profile_image_url as "ProfileImageUrl";
                """,
                user,
                transaction,
                cancellationToken: cancellationToken));

        await connection.ExecuteAsync(
            new CommandDefinition(
                """
                insert into spotify_tokens (
                    user_id,
                    access_token_encrypted,
                    refresh_token_encrypted,
                    token_type,
                    scope,
                    expires_at
                )
                values (
                    @UserId,
                    @AccessTokenEncrypted,
                    @RefreshTokenEncrypted,
                    @TokenType,
                    @Scope,
                    @ExpiresAt
                )
                on conflict (user_id) do update set
                    access_token_encrypted = excluded.access_token_encrypted,
                    refresh_token_encrypted = excluded.refresh_token_encrypted,
                    token_type = excluded.token_type,
                    scope = excluded.scope,
                    expires_at = excluded.expires_at,
                    updated_at = now();
                """,
                tokens with { UserId = appUser.Id },
                transaction,
                cancellationToken: cancellationToken));

        await transaction.CommitAsync(cancellationToken);

        return appUser;
    }

    public async Task<SpotifyTokenRecord?> GetTokensAsync(Guid userId, CancellationToken cancellationToken)
    {
        await using var connection = await connectionFactory.OpenConnectionAsync(cancellationToken);

        return await connection.QuerySingleOrDefaultAsync<SpotifyTokenRecord>(
            new CommandDefinition(
                """
                select
                    user_id as "UserId",
                    access_token_encrypted as "AccessTokenEncrypted",
                    refresh_token_encrypted as "RefreshTokenEncrypted",
                    token_type as "TokenType",
                    scope as "Scope",
                    expires_at as "ExpiresAt"
                from spotify_tokens
                where user_id = @UserId;
                """,
                new { UserId = userId },
                cancellationToken: cancellationToken));
    }

    public async Task UpdateTokensAsync(
        ProtectedSpotifyTokenUpdateModel tokens,
        CancellationToken cancellationToken)
    {
        await using var connection = await connectionFactory.OpenConnectionAsync(cancellationToken);

        var rowsAffected = await connection.ExecuteAsync(
            new CommandDefinition(
                """
                update spotify_tokens
                set
                    access_token_encrypted = @AccessTokenEncrypted,
                    refresh_token_encrypted = coalesce(@RefreshTokenEncrypted, refresh_token_encrypted),
                    token_type = @TokenType,
                    scope = @Scope,
                    expires_at = @ExpiresAt,
                    updated_at = now()
                where user_id = @UserId;
                """,
                tokens,
                cancellationToken: cancellationToken));

        if (rowsAffected == 0)
        {
            throw new InvalidOperationException($"No Spotify token row exists for app user {tokens.UserId}.");
        }
    }
}

public sealed record SpotifyUserWriteModel(
    string SpotifyUserId,
    string DisplayName,
    string? ProfileImageUrl);

public sealed record ProtectedSpotifyTokenWriteModel(
    Guid UserId,
    string AccessTokenEncrypted,
    string RefreshTokenEncrypted,
    string TokenType,
    string Scope,
    DateTimeOffset ExpiresAt);

public sealed record ProtectedSpotifyTokenUpdateModel(
    Guid UserId,
    string AccessTokenEncrypted,
    string? RefreshTokenEncrypted,
    string TokenType,
    string Scope,
    DateTimeOffset ExpiresAt);

public sealed record SpotifyTokenRecord(
    Guid UserId,
    string AccessTokenEncrypted,
    string RefreshTokenEncrypted,
    string TokenType,
    string Scope,
    DateTime ExpiresAt);

public sealed record AppUserRecord(
    Guid Id,
    string SpotifyUserId,
    string? DisplayName,
    string? ProfileImageUrl);
