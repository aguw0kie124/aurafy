using Microsoft.Extensions.Options;
using Statify.Api.Contracts;
using Statify.Api.Options;
using Statify.Api.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.Configure<SpotifyOptions>(builder.Configuration.GetSection(SpotifyOptions.SectionName));
builder.Services.Configure<SyncOptions>(builder.Configuration.GetSection(SyncOptions.SectionName));
builder.Services.AddSingleton<PreviewStatsService>();
builder.Services.AddHostedService<ListeningHistorySyncWorker>();

builder.Services.AddCors(options =>
{
    options.AddPolicy("frontend", policy =>
    {
        policy.WithOrigins(builder.Configuration["Frontend:Origin"] ?? "http://localhost:5173")
            .AllowAnyHeader()
            .AllowAnyMethod();
    });
});

var app = builder.Build();

if (!app.Environment.IsDevelopment())
{
    app.UseHttpsRedirection();
}
app.UseCors("frontend");

app.MapGet("/api/health", () =>
    Results.Ok(new HealthResponse("ok", DateTimeOffset.UtcNow)));

app.MapGet("/api/meta", (IOptions<SpotifyOptions> spotifyOptions) =>
{
    var configured = spotifyOptions.Value.IsConfigured;

    return Results.Ok(new AppMetaResponse(
        "Aurafy",
        configured,
        [
            "user-read-recently-played",
            "user-top-read"
        ]));
});

app.MapGet("/api/stats/preview", (PreviewStatsService previewStatsService) =>
    Results.Ok(previewStatsService.GetPreview()));

app.MapPost("/api/sync/manual", (IOptions<SyncOptions> syncOptions) =>
{
    var response = new ManualRefreshResponse(
        "queued",
        DateTimeOffset.UtcNow,
        syncOptions.Value.ManualRefreshCooldownMinutes);

    return Results.Accepted("/api/sync/manual", response);
});

app.Run();
