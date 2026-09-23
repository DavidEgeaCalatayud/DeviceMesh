namespace DeviceMesh.Agent.Host;

public sealed class AgentOptions
{
    public string AgentId { get; set; } = Environment.MachineName;
    public string ServerBaseUrl { get; set; } = "http://localhost:8000";
    public int IntervalSeconds { get; set; } = 30;
    public string? EnrollmentToken { get; set; }
    public string CredentialFilePath { get; set; } = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "DeviceMesh",
        "agent.credential");
}
