namespace Statify.Api.Contracts;

public sealed record AuthStatusResponse(
    bool Authenticated,
    AuthUserResponse? User);

public sealed record AuthUserResponse(
    string SpotifyUserId,
    string DisplayName,
    string? ImageUrl);
