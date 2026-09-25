using System.Diagnostics;
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
        CollectProcessInventory(metrics);
        metrics.Add(new Metric("host.cpu.logical.count", Environment.ProcessorCount, "count"));
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
        metrics.Add(new Metric("host.memory.available.bytes", status.AvailablePhysical, "bytes"));
        metrics.Add(new Metric("host.memory.used.bytes", used, "bytes"));
        metrics.Add(
            new Metric(
                "host.memory.utilization.percent",
                used * 100d / status.TotalPhysical,
                "percent"));

        if (status.TotalPageFile > 0)
        {
            var pageFileUsed = status.TotalPageFile - status.AvailablePageFile;
            metrics.Add(new Metric("host.pagefile.total.bytes", status.TotalPageFile, "bytes"));
            metrics.Add(new Metric("host.pagefile.used.bytes", pageFileUsed, "bytes"));
            metrics.Add(
                new Metric(
                    "host.pagefile.utilization.percent",
                    pageFileUsed * 100d / status.TotalPageFile,
                    "percent"));
        }
    }

    private static void CollectDisks(ICollection<Metric> metrics)
    {
        long total = 0;
        long free = 0;
        var volumeCount = 0;
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
                volumeCount += 1;
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

        metrics.Add(new Metric("host.disk.volume.count", volumeCount, "count"));
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
        var activeInterfaces = 0;
        foreach (var network in NetworkInterface.GetAllNetworkInterfaces())
        {
            if (network.OperationalStatus != OperationalStatus.Up ||
                network.NetworkInterfaceType == NetworkInterfaceType.Loopback)
            {
                continue;
            }

            activeInterfaces += 1;
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

        metrics.Add(new Metric("host.network.interfaces.up.count", activeInterfaces, "count"));
        metrics.Add(new Metric("host.network.received.bytes", received, "bytes"));
        metrics.Add(new Metric("host.network.sent.bytes", sent, "bytes"));
    }

    private static void CollectProcessInventory(ICollection<Metric> metrics)
    {
        Process[] processes;
        try
        {
            processes = Process.GetProcesses();
        }
        catch (InvalidOperationException)
        {
            return;
        }

        try
        {
            metrics.Add(new Metric("host.process.count", processes.Length, "count"));
        }
        finally
        {
            foreach (var process in processes)
            {
                process.Dispose();
            }
        }
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
