using System.Globalization;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using DeviceMesh.Agent.Application.Telemetry;
using DeviceMesh.Agent.Infrastructure.Identity;
using DeviceMesh.Agent.Protocol;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace DeviceMesh.Agent.Host;

public sealed class AgentWorker(
    IHttpClientFactory httpClientFactory,
    CollectTelemetry collectTelemetry,
    WindowsHostIdentityProvider identityProvider,
    WindowsCredentialStore credentialStore,
    IOptions<AgentOptions> options,
    ILogger<AgentWorker> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var settings = options.Value;
        var client = httpClientFactory.CreateClient("server");
        string? credential = null;

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                credential ??= await EnsureCredentialAsync(client, settings, stoppingToken);
                var now = DateTimeOffset.UtcNow;
                var heartbeat = new HeartbeatMessage(
                    "heartbeat",
                    1,
                    settings.AgentId,
                    now,
                    identityProvider.Capture());
                using var heartbeatResponse = await SendAuthenticatedAsync(
                    client,
                    "/api/v1/agents/heartbeat",
                    heartbeat,
                    settings.AgentId,
                    credential,
                    stoppingToken);
                heartbeatResponse.EnsureSuccessStatusCode();

                var snapshot = collectTelemetry.Execute();
                var metrics = snapshot.Metrics
                    .Select(metric => new MetricPayload(metric.Name, metric.Value, metric.Unit))
                    .ToArray();
                var telemetry = new TelemetryMessage(
                    "telemetry",
                    1,
                    settings.AgentId,
                    snapshot.Timestamp,
                    metrics);
                using var telemetryResponse = await SendAuthenticatedAsync(
                    client,
                    "/api/v1/agents/telemetry",
                    telemetry,
                    settings.AgentId,
                    credential,
                    stoppingToken);
                telemetryResponse.EnsureSuccessStatusCode();
            }
            catch (Exception exception) when (exception is not OperationCanceledException)
            {
                logger.LogWarning(exception, "Failed to publish agent telemetry");
            }

            await Task.Delay(
                TimeSpan.FromSeconds(Math.Max(5, settings.IntervalSeconds)),
                stoppingToken);
        }
    }

    private async Task<string> EnsureCredentialAsync(
        HttpClient client,
        AgentOptions settings,
        CancellationToken cancellationToken)
    {
        var stored = credentialStore.TryLoad();
        if (!string.IsNullOrWhiteSpace(stored))
        {
            return stored;
        }

        if (string.IsNullOrWhiteSpace(settings.EnrollmentToken))
        {
            throw new InvalidOperationException(
                "No agent credential is stored and no enrollment token was supplied.");
        }

        var request = new AgentEnrollmentRequest(settings.EnrollmentToken, settings.AgentId);
        using var response = await client.PostAsJsonAsync(
            "/api/v1/agents/enroll",
            request,
            ProtocolSerializer.Options,
            cancellationToken);
        response.EnsureSuccessStatusCode();
        var enrolled = await response.Content.ReadFromJsonAsync<AgentEnrollmentResponse>(
            ProtocolSerializer.Options,
            cancellationToken);
        if (enrolled is null || string.IsNullOrWhiteSpace(enrolled.Credential))
        {
            throw new InvalidOperationException("Agent enrollment did not return a credential.");
        }

        credentialStore.Save(enrolled.Credential);
        settings.EnrollmentToken = null;
        logger.LogInformation("DeviceMesh agent enrollment completed for {AgentId}", settings.AgentId);
        return enrolled.Credential;
    }

    private static async Task<HttpResponseMessage> SendAuthenticatedAsync<T>(
        HttpClient client,
        string path,
        T payload,
        string agentId,
        string credential,
        CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, path)
        {
            Content = JsonContent.Create(payload, options: ProtocolSerializer.Options)
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Agent", credential);
        request.Headers.Add("X-DeviceMesh-Agent-ID", agentId);
        request.Headers.Add(
            "X-DeviceMesh-Timestamp",
            DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture));
        request.Headers.Add("X-DeviceMesh-Nonce", Guid.NewGuid().ToString("N"));
        return await client.SendAsync(request, cancellationToken);
    }

    private sealed record AgentEnrollmentRequest(string Token, string AgentId);

    private sealed record AgentEnrollmentResponse(
        string AgentId,
        string CredentialId,
        string Credential);
}
