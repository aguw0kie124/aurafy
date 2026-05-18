namespace Statify.Api.Configuration;

public static class DevelopmentEnvLoader
{
    public static void Load()
    {
        var environmentName =
            Environment.GetEnvironmentVariable("ASPNETCORE_ENVIRONMENT") ??
            Environment.GetEnvironmentVariable("DOTNET_ENVIRONMENT");

        if (!string.Equals(environmentName, Environments.Development, StringComparison.OrdinalIgnoreCase))
        {
            return;
        }

        var envPath = FindEnvFile(Directory.GetCurrentDirectory());

        if (envPath is null)
        {
            return;
        }

        foreach (var line in File.ReadLines(envPath))
        {
            var trimmed = line.Trim();

            if (trimmed.Length == 0 || trimmed.StartsWith('#'))
            {
                continue;
            }

            if (trimmed.StartsWith("export ", StringComparison.Ordinal))
            {
                trimmed = trimmed["export ".Length..].TrimStart();
            }

            var separatorIndex = trimmed.IndexOf('=');

            if (separatorIndex <= 0)
            {
                continue;
            }

            var key = trimmed[..separatorIndex].Trim();
            var value = Unquote(trimmed[(separatorIndex + 1)..].Trim());

            if (key.Length == 0 || Environment.GetEnvironmentVariable(key) is not null)
            {
                continue;
            }

            Environment.SetEnvironmentVariable(key, value);
        }
    }

    private static string? FindEnvFile(string startDirectory)
    {
        var directory = new DirectoryInfo(startDirectory);

        while (directory is not null)
        {
            var candidate = Path.Combine(directory.FullName, ".env");

            if (File.Exists(candidate))
            {
                return candidate;
            }

            directory = directory.Parent;
        }

        return null;
    }

    private static string Unquote(string value)
    {
        if (value.Length < 2)
        {
            return value;
        }

        var first = value[0];
        var last = value[^1];

        return (first, last) switch
        {
            ('"', '"') => value[1..^1],
            ('\'', '\'') => value[1..^1],
            _ => value
        };
    }
}
