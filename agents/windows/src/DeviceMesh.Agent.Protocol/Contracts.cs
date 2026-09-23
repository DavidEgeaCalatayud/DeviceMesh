namespace DeviceMesh.Agent.Protocol;

public sealed record HeartbeatMessage(string Type, int ProtocolVersion, string AgentId, DateTimeOffset Timestamp);
public sealed record MetricPayload(string Name, double Value, string? Unit);
public sealed record TelemetryMessage(string Type, int ProtocolVersion, string AgentId, DateTimeOffset Timestamp, IReadOnlyList<MetricPayload> Metrics);
