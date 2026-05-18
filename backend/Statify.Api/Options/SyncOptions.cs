namespace Statify.Api.Options;

public sealed class SyncOptions
{
    public const string SectionName = "Sync";

    public int IntervalMinutes { get; init; } = 15;

    public int ManualRefreshCooldownMinutes { get; init; } = 5;
}
