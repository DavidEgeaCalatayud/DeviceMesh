using DeviceMesh.Agent.Domain.Telemetry;

namespace DeviceMesh.Agent.Application.Telemetry;

public interface IHostCollector
{
    IEnumerable<Metric> Collect();
}
