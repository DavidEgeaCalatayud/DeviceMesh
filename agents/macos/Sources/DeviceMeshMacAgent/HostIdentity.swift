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
            macAddresses: macAddresses()
        )
    }

    private func architecture() -> String? {
        var systemInfo = utsname()
        guard uname(&systemInfo) == 0 else { return nil }
        let identifier = Mirror(reflecting: systemInfo.machine).children.reduce(into: "") { result, child in
            guard let value = child.value as? Int8, value != 0 else { return }
            result.append(Character(UnicodeScalar(UInt8(value))))
        }
        return identifier.nilIfEmpty
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

    private func macAddresses() -> [String] {
        var head: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&head) == 0, let first = head else { return [] }
        defer { freeifaddrs(head) }
        var addresses = Set<String>()
        for pointer in sequence(first: first, next: { $0.pointee.ifa_next }) {
            guard let address = pointer.pointee.ifa_addr,
                  Int32(address.pointee.sa_family) == AF_LINK else { continue }
            let flags = Int32(pointer.pointee.ifa_flags)
            guard flags & IFF_LOOPBACK == 0 else { continue }
            var link = UnsafeRawPointer(address).assumingMemoryBound(to: sockaddr_dl.self).pointee
            let nameLength = Int(link.sdl_nlen)
            let addressLength = Int(link.sdl_alen)
            guard addressLength > 0 else { continue }
            let mac: String? = withUnsafeBytes(of: &link.sdl_data) { rawBuffer in
                let bytes = rawBuffer.bindMemory(to: UInt8.self)
                guard nameLength + addressLength <= bytes.count else { return nil }
                return bytes[nameLength..<(nameLength + addressLength)]
                    .map { String(format: "%02X", $0) }
                    .joined(separator: ":")
            }
            if let mac, !mac.isEmpty, mac != "00:00:00:00:00:00" {
                addresses.insert(mac)
            }
        }
        return addresses.sorted()
    }
}
