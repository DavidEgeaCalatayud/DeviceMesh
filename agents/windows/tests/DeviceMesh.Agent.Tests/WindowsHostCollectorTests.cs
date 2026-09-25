using DeviceMesh.Agent.Infrastructure.Collectors;

namespace DeviceMesh.Agent.Tests;

public sealed class WindowsHostCollectorTests
{
    [Fact]
    public void CollectsHostMemoryDiskNetworkAndInventoryMetricsOnWindows()
    {
        if (!OperatingSystem.IsWindows())
        {
            return;
        }

        var metrics = new WindowsHostCollector().Collect().ToArray();

        Assert.Contains(metrics, metric => metric.Name == "host.cpu.logical.count" && metric.Value > 0);
        Assert.Contains(metrics, metric => metric.Name == "host.memory.total.bytes" && metric.Value > 0);
        Assert.Contains(metrics, metric => metric.Name == "host.memory.available.bytes");
        Assert.Contains(metrics, metric => metric.Name == "host.pagefile.total.bytes");
        Assert.Contains(metrics, metric => metric.Name == "host.disk.total.bytes");
        Assert.Contains(metrics, metric => metric.Name == "host.disk.volume.count" && metric.Value > 0);
        Assert.Contains(metrics, metric => metric.Name == "host.network.received.bytes");
        Assert.Contains(metrics, metric => metric.Name == "host.network.interfaces.up.count");
        Assert.Contains(metrics, metric => metric.Name == "host.process.count" && metric.Value > 0);
        Assert.Contains(metrics, metric => metric.Name == "host.uptime.seconds");
    }
}
