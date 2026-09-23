using System.Text.Json;
using DeviceMesh.Agent.Protocol;

namespace DeviceMesh.Agent.Tests;

public sealed class ProtocolSerializerTests
{
    [Fact]
    public void HeartbeatUsesCamelCaseProtocolContract()
    {
        var message = new HeartbeatMessage("heartbeat", 1, "agent-test", DateTimeOffset.UnixEpoch);
        var json = ProtocolSerializer.Serialize(message);
        Assert.Contains("\"protocolVersion\":1", json);
        Assert.Contains("\"agentId\":\"agent-test\"", json);
    }

    [Fact]
    public void RemoteOperationClaimUsesOnlyDeclarativeOperationFields()
    {
        var claim = new RemoteOperationClaim(
            "operation-1",
            RemoteOperationTypes.AgentHealthCheck,
            new Dictionary<string, JsonElement>(),
            DateTimeOffset.UnixEpoch.AddMinutes(5));

        var json = ProtocolSerializer.Serialize(claim);
        Assert.Contains("\"operationType\":\"agent.health_check\"", json);
        Assert.Contains("\"arguments\":{}", json);
        Assert.DoesNotContain("command", json, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("shell", json, StringComparison.OrdinalIgnoreCase);
    }
}
