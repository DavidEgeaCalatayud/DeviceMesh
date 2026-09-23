using System.IO;
using System.Net.NetworkInformation;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using DeviceMesh.Agent.Application.Telemetry;
using DeviceMesh.Agent.Domain.Telemetry;

namespace DeviceMesh.Agent.Infrastructure.Collectors;

public sealed class WindowsHostCollector : IHostCollector
{
    private readonly object cpuSync = new();
    private ulong previousIdle;
    private ulong previousKernel;
    private ulong previousUser;
    private bool hasCpuSample;

    public IEnumerable<Metric> Collect()
    {
        if (!OperatingSystem.IsWindows())
        {
            return Array.Empty<Metric>();
        }

        var metrics = new List<Metric>();
        CollectCpu(metrics);
        CollectMemory(metrics);
        CollectDisks(metrics);
        CollectNetwork(metrics);
        metrics.Add(new Metric("host.uptime.seconds", Environment.TickCount64 / 1000d, "seconds"));
        return metrics;
    }

    private void CollectCpu(ICollection<Metric> metrics)
    {
        if (!GetSystemTimes(out var idleTime, out var kernelTime, out var userTime))
        {
            return;
        }

        var idle = ToUInt64(idleTime);
        var kernel = ToUInt64(kernelTime);
        var user = ToUInt64(userTime);

        lock (cpuSync)
        {
            if (hasCpuSample)
            {
                var idleDelta = idle - previousIdle;
                var kernelDelta = kernel - previousKernel;
                var userDelta = user - previousUser;
                var totalDelta = kernelDelta + userDelta;
                if (totalDelta > 0 && totalDelta >= idleDelta)
                {
                    var utilization = 100d * (totalDelta - idleDelta) / totalDelta;
                    metrics.Add(new Metric("host.cpu.utilization.percent", utilization, "percent"));
                }
            }

            previousIdle = idle;
            previousKernel = kernel;
            previousUser = user;
            hasCpuSample = true;
        }
    }

    private static void CollectMemory(ICollection<Metric> metrics)
    {
        var status = new MemoryStatusEx
        {
            Length = (uint)Marshal.SizeOf<MemoryStatusEx>(),
        };
        if (!GlobalMemoryStatusEx(ref status) || status.TotalPhysical == 0)
        {
            return;
        }

        var used = status.TotalPhysical - status.AvailablePhysical;
        metrics.Add(new Metric("host.memory.total.bytes", status.TotalPhysical, "bytes"));
        metrics.Add(new Metric("host.memory.used.bytes", used, "bytes"));
        metrics.Add(
            new Metric(
                "host.memory.utilization.percent",
                used * 100d / status.TotalPhysical,
                "percent"));
    }

    private static void CollectDisks(ICollection<Metric> metrics)
    {
        long total = 0;
        long free = 0;
        foreach (var drive in DriveInfo.GetDrives())
        {
            try
            {
                if (!drive.IsReady || drive.DriveType != DriveType.Fixed)
                {
                    continue;
                }

                total += drive.TotalSize;
                free += drive.AvailableFreeSpace;
            }
            catch (IOException)
            {
                // A removable/unavailable volume can disappear while enumerating drives.
            }
            catch (UnauthorizedAccessException)
            {
                // Continue collecting the rest of the host without requiring elevated access.
            }
        }

        if (total <= 0)
        {
            return;
        }

        metrics.Add(new Metric("host.disk.total.bytes", total, "bytes"));
        metrics.Add(new Metric("host.disk.free.bytes", free, "bytes"));
        metrics.Add(new Metric("host.disk.used.bytes", total - free, "bytes"));
        metrics.Add(
            new Metric(
                "host.disk.utilization.percent",
                (total - free) * 100d / total,
                "percent"));
    }

    private static void CollectNetwork(ICollection<Metric> metrics)
    {
        long received = 0;
        long sent = 0;
        foreach (var network in NetworkInterface.GetAllNetworkInterfaces())
        {
            if (network.OperationalStatus != OperationalStatus.Up ||
                network.NetworkInterfaceType == NetworkInterfaceType.Loopback)
            {
                continue;
            }

            try
            {
                var statistics = network.GetIPStatistics();
                received += statistics.BytesReceived;
                sent += statistics.BytesSent;
            }
            catch (NetworkInformationException)
            {
                // Some virtual adapters expose no counters; other adapters remain useful.
            }
        }

        metrics.Add(new Metric("host.network.received.bytes", received, "bytes"));
        metrics.Add(new Metric("host.network.sent.bytes", sent, "bytes"));
    }

    private static ulong ToUInt64(FILETIME value) =>
        ((ulong)(uint)value.dwHighDateTime << 32) | (uint)value.dwLowDateTime;

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetSystemTimes(
        out FILETIME idleTime,
        out FILETIME kernelTime,
        out FILETIME userTime);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GlobalMemoryStatusEx(ref MemoryStatusEx buffer);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
    private struct MemoryStatusEx
    {
        public uint Length;
        public uint MemoryLoad;
        public ulong TotalPhysical;
        public ulong AvailablePhysical;
        public ulong TotalPageFile;
        public ulong AvailablePageFile;
        public ulong TotalVirtual;
        public ulong AvailableVirtual;
        public ulong AvailableExtendedVirtual;
    }
}
