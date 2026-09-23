namespace DeviceMesh.Agent.Host;

public sealed class AgentOptions
{
    public string AgentId { get; set; } = Environment.MachineName;
    public string ServerBaseUrl { get; set; } = "http://localhost:8000";
    public int IntervalSeconds { get; set; } = 30;
}
