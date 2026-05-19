using System.Security.Cryptography;
using System.Text;
using System.Security.Claims;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.Extensions.Options;
using Npgsql;
using Statify.Api.Configuration;
using Statify.Api.Contracts;
using Statify.Api.Data;
using Statify.Api.Options;
using Statify.Api.Services;

DevelopmentEnvLoader.Load();

var builder = WebApplication.CreateBuilder(args);

builder.Services.Configure<SpotifyOptions>(builder.Configuration.GetSection(SpotifyOptions.SectionName));
builder.Services.AddDataProtection().SetApplicationName("Statify");
builder.Services
    .AddAuthentication(CookieAuthenticationDefaults.AuthenticationScheme)
    .AddCookie(options =>
    {
        options.Cookie.Name = "Aurafy.Session";
        options.Cookie.HttpOnly = true;
        options.Cookie.SameSite = SameSiteMode.Lax;
        options.Cookie.SecurePolicy = builder.Environment.IsDevelopment()
            ? CookieSecurePolicy.SameAsRequest
            : CookieSecurePolicy.Always;
        options.ExpireTimeSpan = TimeSpan.FromDays(14);
        options.SlidingExpiration = true;
        options.Events.OnRedirectToLogin = context =>
        {
            context.Response.StatusCode = StatusCodes.Status401Unauthorized;
            return Task.CompletedTask;
        };
    });
builder.Services.AddAuthorization();
builder.Services.AddSingleton<PostgresConnectionFactory>();
builder.Services.AddScoped<SpotifyAccountRepository>();
builder.Services.AddScoped<SpotifyAccountService>();
builder.Services.AddHttpClient<SpotifyAuthService>();
builder.Services.AddSingleton<FrontendRedirectService>();

builder.Services.AddCors(options =>
{
    options.AddPolicy("frontend", policy =>
    {
        policy.WithOrigins(builder.Configuration["Frontend:Origin"] ?? "http://127.0.0.1:5173")
            .AllowAnyHeader()
            .AllowAnyMethod()
            .AllowCredentials();
    });
});

var app = builder.Build();

if (!app.Environment.IsDevelopment())
{
    app.UseHttpsRedirection();
}
app.UseCors("frontend");
app.UseAuthentication();
app.UseAuthorization();

app.MapGet("/api/health", () =>
    Results.Ok(new HealthResponse("ok", DateTimeOffset.UtcNow)));

app.MapGet("/api/auth/me", (ClaimsPrincipal user) =>
{
    if (user.Identity?.IsAuthenticated != true)
    {
        return Results.Ok(new AuthStatusResponse(false, null));
    }

    var spotifyUserId = user.FindFirstValue(ClaimTypes.NameIdentifier);
    var displayName = user.FindFirstValue(ClaimTypes.Name);

    if (string.IsNullOrWhiteSpace(spotifyUserId) || string.IsNullOrWhiteSpace(displayName))
    {
        return Results.Ok(new AuthStatusResponse(false, null));
    }

    return Results.Ok(new AuthStatusResponse(
        true,
        new AuthUserResponse(
            spotifyUserId,
            displayName,
            user.FindFirstValue("spotify:image_url"))));
});

app.MapPost("/api/auth/logout", async (HttpContext httpContext) =>
{
    await httpContext.SignOutAsync(CookieAuthenticationDefaults.AuthenticationScheme);
    return Results.NoContent();
});

app.MapGet("/api/auth/spotify/login", (
    HttpResponse response,
    SpotifyAuthService spotifyAuthService,
    PostgresConnectionFactory postgresConnectionFactory,
    IOptions<SpotifyOptions> spotifyOptions) =>
{
    if (!spotifyOptions.Value.IsConfigured)
    {
        return Results.Problem(
            "Spotify auth is not configured. Add Spotify__ClientId, Spotify__ClientSecret, and Spotify__RedirectUri.",
            statusCode: StatusCodes.Status503ServiceUnavailable);
    }

    if (!postgresConnectionFactory.IsConfigured)
    {
        return Results.Problem(
            "Database is not configured. Add ConnectionStrings__Postgres to .env.",
            statusCode: StatusCodes.Status503ServiceUnavailable);
    }

    var state = spotifyAuthService.CreateState();

    response.Cookies.Append(
        SpotifyAuthService.StateCookieName,
        state,
        new CookieOptions
        {
            HttpOnly = true,
            IsEssential = true,
            MaxAge = TimeSpan.FromMinutes(10),
            SameSite = SameSiteMode.Lax,
            Secure = false
        });

    return Results.Redirect(spotifyAuthService.BuildAuthorizationUrl(state));
});

app.MapGet("/api/auth/spotify/callback", async (
    HttpContext httpContext,
    FrontendRedirectService frontendRedirectService,
    SpotifyAuthService spotifyAuthService,
    SpotifyAccountService spotifyAccountService,
    CancellationToken cancellationToken) =>
{
    var request = httpContext.Request;
    var response = httpContext.Response;
    var returnedState = request.Query["state"].ToString();
    var expectedState = request.Cookies[SpotifyAuthService.StateCookieName];
    response.Cookies.Delete(SpotifyAuthService.StateCookieName);

    if (string.IsNullOrWhiteSpace(returnedState) ||
        string.IsNullOrWhiteSpace(expectedState) ||
        !CryptographicOperations.FixedTimeEquals(
            Encoding.UTF8.GetBytes(returnedState),
            Encoding.UTF8.GetBytes(expectedState)))
    {
        return Results.Redirect(frontendRedirectService.LoginError("state_mismatch"));
    }

    var spotifyError = request.Query["error"].ToString();

    if (!string.IsNullOrWhiteSpace(spotifyError))
    {
        return Results.Redirect(frontendRedirectService.LoginError(spotifyError));
    }

    var code = request.Query["code"].ToString();

    if (string.IsNullOrWhiteSpace(code))
    {
        return Results.Redirect(frontendRedirectService.LoginError("missing_code"));
    }

    try
    {
        var tokens = await spotifyAuthService.ExchangeCodeForTokensAsync(code, cancellationToken);
        var spotifyUser = await spotifyAuthService.GetCurrentUserAsync(tokens.AccessToken, cancellationToken);
        var imageUrl = spotifyUser.Images?.FirstOrDefault()?.Url;
        var displayName = string.IsNullOrWhiteSpace(spotifyUser.DisplayName)
            ? spotifyUser.Id
            : spotifyUser.DisplayName;
        var appUser = await spotifyAccountService.UpsertLoggedInUserAsync(
            spotifyUser,
            displayName,
            imageUrl,
            tokens,
            cancellationToken);

        var claims = new List<Claim>
        {
            new(ClaimTypes.NameIdentifier, spotifyUser.Id),
            new(ClaimTypes.Name, displayName),
            new("app:user_id", appUser.Id.ToString())
        };

        if (!string.IsNullOrWhiteSpace(imageUrl))
        {
            claims.Add(new Claim("spotify:image_url", imageUrl));
        }

        var identity = new ClaimsIdentity(claims, CookieAuthenticationDefaults.AuthenticationScheme);
        var principal = new ClaimsPrincipal(identity);

        await httpContext.SignInAsync(
            CookieAuthenticationDefaults.AuthenticationScheme,
            principal,
            new AuthenticationProperties
            {
                IsPersistent = true,
                AllowRefresh = true,
                ExpiresUtc = DateTimeOffset.UtcNow.AddDays(14)
            });

        return Results.Redirect(frontendRedirectService.AppHome());
    }
    catch (SpotifyAuthException exception)
    {
        app.Logger.LogWarning(
            exception,
            "Spotify token exchange failed. Response body: {ResponseBody}",
            exception.ResponseBody);

        return Results.Redirect(frontendRedirectService.LoginError("spotify_auth_failed"));
    }
    catch (Exception exception) when (exception is NpgsqlException or InvalidOperationException)
    {
        app.Logger.LogError(exception, "Spotify sign-in persistence failed.");

        return Results.Redirect(frontendRedirectService.LoginError("server_error"));
    }
});

app.Run();
