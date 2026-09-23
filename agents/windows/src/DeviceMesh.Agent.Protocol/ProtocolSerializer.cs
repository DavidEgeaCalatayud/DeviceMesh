using System.Text.Json;

namespace DeviceMesh.Agent.Protocol;

public static class ProtocolSerializer
{
    public static readonly JsonSerializerOptions Options = new(JsonSerializerDefaults.Web)
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase
    };

    public static string Serialize<T>(T message) => JsonSerializer.Serialize(message, Options);
}
