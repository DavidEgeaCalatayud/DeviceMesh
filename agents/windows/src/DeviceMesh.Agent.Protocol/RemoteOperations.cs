using System.Text.Json;

namespace DeviceMesh.Agent.Protocol;

public static class RemoteOperationTypes
{
    public const string TelemetryCollect = "telemetry.collect";
    public const string InventoryRefresh = "inventory.refresh";
    public const string AgentHealthCheck = "agent.health_check";
}

public sealed record RemoteOperationClaim(
    string Id,
    string OperationType,
    IReadOnlyDictionary<string, JsonElement> Arguments,
    DateTimeOffset ExpiresAt);

public sealed record RemoteOperationCompletion(
    string Status,
    IReadOnlyDictionary<string, object?> Result,
    string? Error = null);
