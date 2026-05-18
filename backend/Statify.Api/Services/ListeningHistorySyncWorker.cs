using Microsoft.Extensions.Options;
using Statify.Api.Options;

namespace Statify.Api.Services;

public sealed class ListeningHistorySyncWorker(
    ILogger<ListeningHistorySyncWorker> logger,
    IOptions<SyncOptions> syncOptions) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var interval = TimeSpan.FromMinutes(Math.Max(1, syncOptions.Value.IntervalMinutes));

        logger.LogInformation("Listening history sync worker started with a {Interval} interval.", interval);

        using var timer = new PeriodicTimer(interval);

        while (await timer.WaitForNextTickAsync(stoppingToken))
        {
            logger.LogInformation("Listening history sync tick at {Timestamp}.", DateTimeOffset.UtcNow);
        }
    }
}
