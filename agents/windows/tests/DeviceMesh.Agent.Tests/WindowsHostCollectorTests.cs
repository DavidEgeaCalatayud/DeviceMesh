using DeviceMesh.Agent.Infrastructure.Collectors;

namespace DeviceMesh.Agent.Tests;

public sealed class WindowsHostCollectorTests
{
    [Fact]
    public void CollectsHostMemoryDiskAndNetworkMetricsOnWindows()
    {
        if (!OperatingSystem.IsWindows())
        {
            return;
        }

        var metrics = new WindowsHostCollector().Collect().ToArray();

        Assert.Contains(metrics, metric => metric.Name == "host.memory.total.bytes");
        Assert.Contains(metrics, metric => metric.Name == "host.disk.total.bytes");
        Assert.Contains(metrics, metric => metric.Name == "host.network.received.bytes");
        Assert.Contains(metrics, metric => metric.Name == "host.uptime.seconds");
    }
}
