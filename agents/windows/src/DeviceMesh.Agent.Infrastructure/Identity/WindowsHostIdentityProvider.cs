using System.Net;
using System.Net.NetworkInformation;
using System.Runtime.InteropServices;
using DeviceMesh.Agent.Protocol;

namespace DeviceMesh.Agent.Infrastructure.Identity;

public sealed class WindowsHostIdentityProvider
{
    public DeviceIdentityPayload Capture()
    {
        var ipAddresses = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);
        var macAddresses = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var network in NetworkInterface.GetAllNetworkInterfaces())
        {
            if (network.OperationalStatus != OperationalStatus.Up)
            {
                continue;
            }

            foreach (var address in network.GetIPProperties().UnicastAddresses)
            {
                if (!IPAddress.IsLoopback(address.Address))
                {
                    ipAddresses.Add(address.Address.ToString());
                }
            }

            var bytes = network.GetPhysicalAddress().GetAddressBytes();
            if (bytes.Length > 0)
            {
                macAddresses.Add(string.Join(":", bytes.Select(value => value.ToString("X2"))));
            }
        }

        return new DeviceIdentityPayload(
            Dns.GetHostName(),
            RuntimeInformation.OSDescription,
            Environment.OSVersion.Version.ToString(),
            RuntimeInformation.OSArchitecture.ToString().ToLowerInvariant(),
            null,
            ipAddresses.ToArray(),
            macAddresses.ToArray());
    }
}
