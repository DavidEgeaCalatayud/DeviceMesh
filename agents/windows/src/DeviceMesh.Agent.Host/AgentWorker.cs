using System.Net.Http.Json;
using DeviceMesh.Agent.Application.Telemetry;
using DeviceMesh.Agent.Protocol;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace DeviceMesh.Agent.Host;

public sealed class AgentWorker(
    IHttpClientFactory httpClientFactory,
    CollectTelemetry collectTelemetry,
    IOptions<AgentOptions> options,
    ILogger<AgentWorker> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var settings = options.Value;
        var client = httpClientFactory.CreateClient("server");
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                var now = DateTimeOffset.UtcNow;
                var heartbeat = new HeartbeatMessage("heartbeat", 1, settings.AgentId, now);
                await client.PostAsJsonAsync("/api/v1/agents/heartbeat", heartbeat, ProtocolSerializer.Options, stoppingToken);

                var snapshot = collectTelemetry.Execute();
                var metrics = snapshot.Metrics.Select(metric => new MetricPayload(metric.Name, metric.Value, metric.Unit)).ToArray();
                var telemetry = new TelemetryMessage("telemetry", 1, settings.AgentId, snapshot.Timestamp, metrics);
                await client.PostAsJsonAsync("/api/v1/agents/telemetry", telemetry, ProtocolSerializer.Options, stoppingToken);
            }
            catch (Exception exception) when (exception is not OperationCanceledException)
            {
                logger.LogWarning(exception, "Failed to publish agent telemetry");
            }

            await Task.Delay(TimeSpan.FromSeconds(Math.Max(5, settings.IntervalSeconds)), stoppingToken);
        }
    }
}
