import Darwin
import Foundation

struct MacHostIdentityCollector {
    func collect() -> DeviceIdentity {
        DeviceIdentity(
            hostname: ProcessInfo.processInfo.hostName,
            operatingSystem: "macOS",
            operatingSystemVersion: ProcessInfo.processInfo.operatingSystemVersionString,
            architecture: architecture(),
            manufacturer: "Apple Inc.",
            ipAddresses: ipAddresses(),
            macAddresses: []
        )
    }

    private func architecture() -> String? {
        var systemInfo = utsname()
        guard uname(&systemInfo) == 0 else { return nil }
        return withUnsafePointer(to: &systemInfo.machine) { pointer in
            pointer.withMemoryRebound(to: CChar.self, capacity: MemoryLayout.size(ofValue: systemInfo.machine)) {
                String(cString: $0)
            }
        }
    }

    private func ipAddresses() -> [String] {
        var head: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&head) == 0, let first = head else { return [] }
        defer { freeifaddrs(head) }
        var addresses = Set<String>()
        for pointer in sequence(first: first, next: { $0.pointee.ifa_next }) {
            guard let address = pointer.pointee.ifa_addr else { continue }
            let family = Int32(address.pointee.sa_family)
            guard family == AF_INET || family == AF_INET6 else { continue }
            let flags = Int32(pointer.pointee.ifa_flags)
            guard flags & IFF_LOOPBACK == 0 else { continue }
            var host = [CChar](repeating: 0, count: Int(NI_MAXHOST))
            let length: socklen_t = family == AF_INET ? socklen_t(MemoryLayout<sockaddr_in>.size) : socklen_t(MemoryLayout<sockaddr_in6>.size)
            if getnameinfo(address, length, &host, socklen_t(host.count), nil, 0, NI_NUMERICHOST) == 0 {
                let value = String(cString: host).split(separator: "%", maxSplits: 1).first.map(String.init) ?? ""
                if !value.isEmpty { addresses.insert(value) }
            }
        }
        return addresses.sorted()
    }
}
