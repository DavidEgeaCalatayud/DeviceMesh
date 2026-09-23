using DeviceMesh.Agent.Domain.Telemetry;

namespace DeviceMesh.Agent.Application.Telemetry;

public sealed class CollectTelemetry(IEnumerable<IHostCollector> collectors)
{
    public TelemetrySnapshot Execute()
    {
        var metrics = collectors.SelectMany(collector => collector.Collect()).ToArray();
        return new TelemetrySnapshot(DateTimeOffset.UtcNow, metrics);
    }
}
