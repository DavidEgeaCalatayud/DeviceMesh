namespace DeviceMesh.Agent.Protocol;

public sealed record DeviceIdentityPayload(
    string? Hostname,
    string? OperatingSystem,
    string? OperatingSystemVersion,
    string? Architecture,
    string? Manufacturer,
    IReadOnlyList<string> IpAddresses,
    IReadOnlyList<string> MacAddresses);

public sealed record HeartbeatMessage(
    string Type,
    int ProtocolVersion,
    string AgentId,
    DateTimeOffset Timestamp,
    DeviceIdentityPayload? Device = null);

public sealed record MetricPayload(string Name, double Value, string? Unit);

public sealed record TelemetryMessage(
    string Type,
    int ProtocolVersion,
    string AgentId,
    DateTimeOffset Timestamp,
    IReadOnlyList<MetricPayload> Metrics);
