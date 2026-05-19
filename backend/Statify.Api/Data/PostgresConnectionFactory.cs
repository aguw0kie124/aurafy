using Microsoft.Extensions.Configuration;
using Npgsql;

namespace Statify.Api.Data;

public sealed class PostgresConnectionFactory(IConfiguration configuration)
{
    public const string ConnectionStringName = "Postgres";

    private readonly string? _connectionString = configuration.GetConnectionString(ConnectionStringName);

    public bool IsConfigured => !string.IsNullOrWhiteSpace(_connectionString);

    public async Task<NpgsqlConnection> OpenConnectionAsync(CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(_connectionString))
        {
            throw new InvalidOperationException(
                $"Database connection is not configured. Add ConnectionStrings__{ConnectionStringName} to .env.");
        }

        var connection = new NpgsqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        return connection;
    }
}
