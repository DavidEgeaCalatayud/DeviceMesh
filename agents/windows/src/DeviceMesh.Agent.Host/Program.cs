using DeviceMesh.Agent.Application.Telemetry;
using DeviceMesh.Agent.Host;
using DeviceMesh.Agent.Infrastructure.Collectors;

var builder = Host.CreateApplicationBuilder(args);
builder.Services.Configure<AgentOptions>(builder.Configuration.GetSection("DeviceMesh"));
builder.Services.AddSingleton<IHostCollector, RuntimeCollector>();
builder.Services.AddSingleton<CollectTelemetry>();
builder.Services.AddHttpClient("server", (services, client) =>
{
    var options = services.GetRequiredService<Microsoft.Extensions.Options.IOptions<AgentOptions>>().Value;
    client.BaseAddress = new Uri(options.ServerBaseUrl);
    client.Timeout = TimeSpan.FromSeconds(10);
});
builder.Services.AddHostedService<AgentWorker>();
await builder.Build().RunAsync();
