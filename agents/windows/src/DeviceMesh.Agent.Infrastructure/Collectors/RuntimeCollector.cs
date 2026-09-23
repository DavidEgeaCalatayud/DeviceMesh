using System.Diagnostics;
using DeviceMesh.Agent.Application.Telemetry;
using DeviceMesh.Agent.Domain.Telemetry;

namespace DeviceMesh.Agent.Infrastructure.Collectors;

public sealed class RuntimeCollector : IHostCollector
{
    public IEnumerable<Metric> Collect()
    {
        using var process = Process.GetCurrentProcess();
        yield return new Metric("agent.process.memory.bytes", process.WorkingSet64, "bytes");
        yield return new Metric("host.logical_processors", Environment.ProcessorCount, "count");
        yield return new Metric("agent.uptime.seconds", Environment.TickCount64 / 1000d, "seconds");
    }
}
