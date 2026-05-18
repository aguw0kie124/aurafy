using Statify.Api.Contracts;

namespace Statify.Api.Services;

public sealed class PreviewStatsService
{
    public PreviewStatsResponse GetPreview() =>
        new(
            "Rolling 4 weeks",
            1284,
            [
                new RankedItemResponse("After Hours", "The Weeknd", 42, "#7cc6fe"),
                new RankedItemResponse("Nights", "Frank Ocean", 37, "#f6bd60"),
                new RankedItemResponse("Supercut", "Lorde", 31, "#84dcc6")
            ],
            [
                new RankedItemResponse("The Weeknd", "Artist", 166, "#ff7b72"),
                new RankedItemResponse("Lorde", "Artist", 121, "#c3bef0"),
                new RankedItemResponse("Khruangbin", "Artist", 94, "#95d5b2")
            ],
            [
                new TrendPointResponse("Mon", 142),
                new TrendPointResponse("Tue", 164),
                new TrendPointResponse("Wed", 118),
                new TrendPointResponse("Thu", 221),
                new TrendPointResponse("Fri", 236),
                new TrendPointResponse("Sat", 249),
                new TrendPointResponse("Sun", 154)
            ]);
}
