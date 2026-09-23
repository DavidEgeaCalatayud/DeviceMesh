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
}
