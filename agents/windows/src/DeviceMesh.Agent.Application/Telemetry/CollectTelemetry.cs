using DeviceMesh.Agent.Domain.Telemetry;

namespace DeviceMesh.Agent.Application.Telemetry;

public sealed class CollectTelemetry(IEnumerable<IHostCollector> collectors)
{
    public TelemetrySnapshot Execute()
    {
        var metrics = new List<Metric>();
        foreach (var collector in collectors)
        {
            try
            {
                metrics.AddRange(collector.Collect());
            }
            catch (Exception)
            {
                // Collectors are intentionally isolated: one unavailable subsystem must not
                // suppress heartbeat or telemetry from the remaining host collectors.
            }
        }

        return new TelemetrySnapshot(DateTimeOffset.UtcNow, metrics);
    }
}
