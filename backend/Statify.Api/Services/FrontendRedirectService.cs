using Microsoft.AspNetCore.WebUtilities;

namespace Statify.Api.Services;

public sealed class FrontendRedirectService(IConfiguration configuration)
{
    private readonly string _origin = configuration["Frontend:Origin"] ?? "http://127.0.0.1:5173";

    public string AppHome()
    {
        return BuildUrl("/");
    }

    public string LoginError(string reason)
    {
        return BuildUrl("/", new Dictionary<string, string?>
        {
            ["auth_error"] = reason
        });
    }

    private string BuildUrl(string path, Dictionary<string, string?>? query = null)
    {
        var origin = _origin.TrimEnd('/');
        var url = $"{origin}{path}";

        return query is null ? url : QueryHelpers.AddQueryString(url, query);
    }
}
