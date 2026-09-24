import Darwin
import Foundation

final class MacHostMetricsCollector: @unchecked Sendable {
    private var previousCPU: (user: UInt64, system: UInt64, idle: UInt64, nice: UInt64)?

    func collect() -> [MetricPayload] {
        var metrics = [MetricPayload]()
        if let cpu = cpuUtilization() {
            metrics.append(.init(name: "host.cpu.utilization.percent", value: cpu, unit: "percent"))
        }
        metrics.append(contentsOf: memoryMetrics())
        metrics.append(contentsOf: diskMetrics())
        metrics.append(contentsOf: networkMetrics())
        metrics.append(.init(name: "host.uptime.seconds", value: ProcessInfo.processInfo.systemUptime, unit: "seconds"))
        return metrics
    }

    private func cpuUtilization() -> Double? {
        var info = host_cpu_load_info_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<host_cpu_load_info_data_t>.size / MemoryLayout<integer_t>.size)
        let result = withUnsafeMutablePointer(to: &info) { pointer in
            pointer.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                host_statistics(mach_host_self(), HOST_CPU_LOAD_INFO, $0, &count)
            }
        }
        guard result == KERN_SUCCESS else { return nil }
        let current = (
            user: UInt64(info.cpu_ticks.0),
            system: UInt64(info.cpu_ticks.1),
            idle: UInt64(info.cpu_ticks.2),
            nice: UInt64(info.cpu_ticks.3)
        )
        defer { previousCPU = current }
        guard let previousCPU else { return nil }
        let user = current.user &- previousCPU.user
        let system = current.system &- previousCPU.system
        let idle = current.idle &- previousCPU.idle
        let nice = current.nice &- previousCPU.nice
        let total = user + system + idle + nice
        guard total > 0 else { return 0 }
        return Double(user + system + nice) / Double(total) * 100.0
    }

    private func memoryMetrics() -> [MetricPayload] {
        let total = Double(ProcessInfo.processInfo.physicalMemory)
        var pageSize: vm_size_t = 0
        guard host_page_size(mach_host_self(), &pageSize) == KERN_SUCCESS else {
            return [.init(name: "host.memory.total.bytes", value: total, unit: "bytes")]
        }
        var stats = vm_statistics64()
        var count = mach_msg_type_number_t(MemoryLayout<vm_statistics64>.size / MemoryLayout<integer_t>.size)
        let result = withUnsafeMutablePointer(to: &stats) { pointer in
            pointer.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                host_statistics64(mach_host_self(), HOST_VM_INFO64, $0, &count)
            }
        }
        guard result == KERN_SUCCESS else {
            return [.init(name: "host.memory.total.bytes", value: total, unit: "bytes")]
        }
        let availablePages = UInt64(stats.free_count) + UInt64(stats.inactive_count)
        let available = min(total, Double(availablePages) * Double(pageSize))
        let used = max(0, total - available)
        let percent = total > 0 ? used / total * 100.0 : 0
        return [
            .init(name: "host.memory.total.bytes", value: total, unit: "bytes"),
            .init(name: "host.memory.used.bytes", value: used, unit: "bytes"),
            .init(name: "host.memory.utilization.percent", value: percent, unit: "percent"),
        ]
    }

    private func diskMetrics() -> [MetricPayload] {
        guard let attributes = try? FileManager.default.attributesOfFileSystem(forPath: "/"),
              let totalNumber = attributes[.systemSize] as? NSNumber,
              let freeNumber = attributes[.systemFreeSize] as? NSNumber else { return [] }
        let total = totalNumber.doubleValue
        let free = freeNumber.doubleValue
        let used = max(0, total - free)
        let percent = total > 0 ? used / total * 100.0 : 0
        return [
            .init(name: "host.disk.total.bytes", value: total, unit: "bytes"),
            .init(name: "host.disk.free.bytes", value: free, unit: "bytes"),
            .init(name: "host.disk.used.bytes", value: used, unit: "bytes"),
            .init(name: "host.disk.utilization.percent", value: percent, unit: "percent"),
        ]
    }

    private func networkMetrics() -> [MetricPayload] {
        var head: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&head) == 0, let first = head else { return [] }
        defer { freeifaddrs(head) }
        var received: UInt64 = 0
        var sent: UInt64 = 0
        for pointer in sequence(first: first, next: { $0.pointee.ifa_next }) {
            let flags = Int32(pointer.pointee.ifa_flags)
            guard flags & IFF_LOOPBACK == 0, let raw = pointer.pointee.ifa_data else { continue }
            let data = raw.assumingMemoryBound(to: if_data.self).pointee
            received &+= UInt64(data.ifi_ibytes)
            sent &+= UInt64(data.ifi_obytes)
        }
        return [
            .init(name: "host.network.received.bytes", value: Double(received), unit: "bytes"),
            .init(name: "host.network.sent.bytes", value: Double(sent), unit: "bytes"),
        ]
    }
}
