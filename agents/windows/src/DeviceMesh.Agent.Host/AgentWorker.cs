using System.Globalization;
using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Net.NetworkInformation;
using System.Runtime.Versioning;
using System.Text.Json;
using DeviceMesh.Agent.Application.Telemetry;
using DeviceMesh.Agent.Infrastructure.Identity;
using DeviceMesh.Agent.Protocol;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace DeviceMesh.Agent.Host;

[SupportedOSPlatform("windows")]
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
                await PublishHeartbeatAsync(client, settings, credential, stoppingToken);
                await PublishTelemetryAsync(client, settings, credential, stoppingToken);
                await ProcessOneRemoteOperationAsync(client, settings, credential, stoppingToken);
            }
            catch (Exception exception) when (exception is not OperationCanceledException)
            {
                logger.LogWarning(exception, "Failed to publish agent telemetry or process remote operation");
            }

            await Task.Delay(
                TimeSpan.FromSeconds(Math.Max(5, settings.IntervalSeconds)),
                stoppingToken);
        }
    }

    private async Task PublishHeartbeatAsync(
        HttpClient client,
        AgentOptions settings,
        string credential,
        CancellationToken cancellationToken)
    {
        var heartbeat = new HeartbeatMessage(
            "heartbeat",
            1,
            settings.AgentId,
            DateTimeOffset.UtcNow,
            identityProvider.Capture());
        using var response = await SendAuthenticatedAsync(
            client,
            "/api/v1/agents/heartbeat",
            heartbeat,
            settings.AgentId,
            credential,
            cancellationToken);
        response.EnsureSuccessStatusCode();
    }

    private async Task PublishTelemetryAsync(
        HttpClient client,
        AgentOptions settings,
        string credential,
        CancellationToken cancellationToken)
    {
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
        using var response = await SendAuthenticatedAsync(
            client,
            "/api/v1/agents/telemetry",
            telemetry,
            settings.AgentId,
            credential,
            cancellationToken);
        response.EnsureSuccessStatusCode();
    }

    private async Task ProcessOneRemoteOperationAsync(
        HttpClient client,
        AgentOptions settings,
        string credential,
        CancellationToken cancellationToken)
    {
        using var claimResponse = await SendAuthenticatedAsync(
            client,
            "/api/v1/agents/operations/claim",
            new { },
            settings.AgentId,
            credential,
            cancellationToken);
        if (claimResponse.StatusCode == HttpStatusCode.NoContent)
        {
            return;
        }

        claimResponse.EnsureSuccessStatusCode();
        var operation = await claimResponse.Content.ReadFromJsonAsync<RemoteOperationClaim>(
            ProtocolSerializer.Options,
            cancellationToken);
        if (operation is null)
        {
            throw new InvalidOperationException("Remote operation claim did not return a payload.");
        }

        RemoteOperationCompletion completion;
        try
        {
            completion = await ExecuteRemoteOperationAsync(
                operation,
                client,
                settings,
                credential,
                cancellationToken);
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            completion = new RemoteOperationCompletion(
                "failed",
                new Dictionary<string, object?>(),
                exception.Message);
        }

        using var completionResponse = await SendAuthenticatedAsync(
            client,
            $"/api/v1/agents/operations/{Uri.EscapeDataString(operation.Id)}/complete",
            completion,
            settings.AgentId,
            credential,
            cancellationToken);
        completionResponse.EnsureSuccessStatusCode();
    }

    private async Task<RemoteOperationCompletion> ExecuteRemoteOperationAsync(
        RemoteOperationClaim operation,
        HttpClient client,
        AgentOptions settings,
        string credential,
        CancellationToken cancellationToken)
    {
        switch (operation.OperationType)
        {
            case RemoteOperationTypes.TelemetryCollect:
                if (operation.Arguments.Count != 0)
                {
                    return Failure("telemetry.collect does not accept arguments");
                }
                await PublishTelemetryAsync(client, settings, credential, cancellationToken);
                return Success(new Dictionary<string, object?>
                {
                    ["collectedAt"] = DateTimeOffset.UtcNow
                });

            case RemoteOperationTypes.InventoryRefresh:
                if (operation.Arguments.Count != 0)
                {
                    return Failure("inventory.refresh does not accept arguments");
                }
                await PublishHeartbeatAsync(client, settings, credential, cancellationToken);
                return Success(new Dictionary<string, object?>
                {
                    ["refreshedAt"] = DateTimeOffset.UtcNow
                });

            case RemoteOperationTypes.AgentHealthCheck:
                if (operation.Arguments.Count != 0)
                {
                    return Failure("agent.health_check does not accept arguments");
                }
                return Success(new Dictionary<string, object?>
                {
                    ["agentId"] = settings.AgentId,
                    ["status"] = "ok",
                    ["checkedAt"] = DateTimeOffset.UtcNow,
                    ["platform"] = "windows"
                });

            case RemoteOperationTypes.NetworkDnsLookup:
                return await ExecuteDnsLookupAsync(operation.Arguments, cancellationToken);

            case RemoteOperationTypes.NetworkRouteSnapshot:
                if (operation.Arguments.Count != 0)
                {
                    return Failure("network.route_snapshot does not accept arguments");
                }
                return Success(CaptureRouteSnapshot());

            default:
                return Failure($"unsupported remote operation type: {operation.OperationType}");
        }
    }

    private static async Task<RemoteOperationCompletion> ExecuteDnsLookupAsync(
        IReadOnlyDictionary<string, JsonElement> arguments,
        CancellationToken cancellationToken)
    {
        if (arguments.Count != 1 ||
            !arguments.TryGetValue("hostname", out var hostnameElement) ||
            hostnameElement.ValueKind != JsonValueKind.String)
        {
            return Failure("network.dns_lookup requires only a hostname string argument");
        }

        var hostname = hostnameElement.GetString()?.Trim();
        if (string.IsNullOrWhiteSpace(hostname) || hostname.Length > 253)
        {
            return Failure("hostname must contain between 1 and 253 characters");
        }

        var addresses = await Dns.GetHostAddressesAsync(hostname, cancellationToken);
        return Success(new Dictionary<string, object?>
        {
            ["hostname"] = hostname,
            ["addresses"] = addresses
                .Select(address => address.ToString())
                .Distinct(StringComparer.Ordinal)
                .Order(StringComparer.Ordinal)
                .Take(32)
                .ToArray(),
            ["resolvedAt"] = DateTimeOffset.UtcNow
        });
    }

    private static Dictionary<string, object?> CaptureRouteSnapshot()
    {
        var interfaces = new List<Dictionary<string, object?>>();
        foreach (var network in NetworkInterface.GetAllNetworkInterfaces()
                     .Where(item => item.OperationalStatus == OperationalStatus.Up &&
                                    item.NetworkInterfaceType != NetworkInterfaceType.Loopback)
                     .Take(64))
        {
            try
            {
                var properties = network.GetIPProperties();
                interfaces.Add(new Dictionary<string, object?>
                {
                    ["id"] = network.Id,
                    ["name"] = network.Name,
                    ["type"] = network.NetworkInterfaceType.ToString(),
                    ["addresses"] = properties.UnicastAddresses
                        .Select(address => address.Address.ToString())
                        .Take(32)
                        .ToArray(),
                    ["gateways"] = properties.GatewayAddresses
                        .Select(gateway => gateway.Address.ToString())
                        .Where(address => address != "0.0.0.0" && address != "::")
                        .Take(16)
                        .ToArray()
                });
            }
            catch (NetworkInformationException)
            {
                // A virtual adapter may disappear between enumeration and inspection.
            }
        }

        return new Dictionary<string, object?>
        {
            ["capturedAt"] = DateTimeOffset.UtcNow,
            ["interfaces"] = interfaces
        };
    }

    private static RemoteOperationCompletion Success(IReadOnlyDictionary<string, object?> result) =>
        new("succeeded", result);

    private static RemoteOperationCompletion Failure(string error) =>
        new("failed", new Dictionary<string, object?>(), error);

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
