namespace DeviceMesh.Agent.Domain.Telemetry;

public sealed record Metric(string Name, double Value, string? Unit = null);
