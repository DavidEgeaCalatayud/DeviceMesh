namespace DeviceMesh.Agent.Domain.Telemetry;

public sealed record TelemetrySnapshot(DateTimeOffset Timestamp, IReadOnlyList<Metric> Metrics);
