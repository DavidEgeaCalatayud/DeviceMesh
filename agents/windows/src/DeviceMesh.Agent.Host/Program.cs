using System.Runtime.Versioning;
using DeviceMesh.Agent.Application.Telemetry;
using DeviceMesh.Agent.Host;
using DeviceMesh.Agent.Infrastructure.Collectors;
using DeviceMesh.Agent.Infrastructure.Identity;

if (!OperatingSystem.IsWindows())
{
    throw new PlatformNotSupportedException("DeviceMesh.Agent.Host requires Windows.");
}

await RunWindowsAgentAsync(args);

[SupportedOSPlatform("windows")]
static async Task RunWindowsAgentAsync(string[] args)
{
    var builder = Host.CreateApplicationBuilder(args);
    builder.Services.Configure<AgentOptions>(builder.Configuration.GetSection("DeviceMesh"));
    builder.Services.AddSingleton<IHostCollector, RuntimeCollector>();
    builder.Services.AddSingleton<IHostCollector, WindowsHostCollector>();
    builder.Services.AddSingleton<WindowsHostIdentityProvider>();
    builder.Services.AddSingleton<WindowsCredentialStore>();
    builder.Services.AddSingleton<CollectTelemetry>();
    builder.Services.AddHttpClient("server", (services, client) =>
    {
        var options = services.GetRequiredService<Microsoft.Extensions.Options.IOptions<AgentOptions>>().Value;
        client.BaseAddress = new Uri(options.ServerBaseUrl);
        client.Timeout = TimeSpan.FromSeconds(10);
    });
    builder.Services.AddHostedService<AgentWorker>();
    await builder.Build().RunAsync();
}
