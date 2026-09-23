using DeviceMesh.Agent.Application.Telemetry;
using DeviceMesh.Agent.Domain.Telemetry;

namespace DeviceMesh.Agent.Tests;

public sealed class CollectTelemetryTests
{
    [Fact]
    public void FailedCollectorDoesNotSuppressHealthyCollectors()
    {
        IHostCollector[] collectors = [new FailingCollector(), new HealthyCollector()];
        var useCase = new CollectTelemetry(collectors);

        var snapshot = useCase.Execute();

        Assert.Single(snapshot.Metrics);
        Assert.Equal("host.test.value", snapshot.Metrics[0].Name);
    }

    private sealed class FailingCollector : IHostCollector
    {
        public IEnumerable<Metric> Collect() => throw new InvalidOperationException("boom");
    }

    private sealed class HealthyCollector : IHostCollector
    {
        public IEnumerable<Metric> Collect()
        {
            yield return new Metric("host.test.value", 1, "count");
        }
    }
}
