import XCTest
@testable import DeviceMeshMacAgent

final class PayloadTests: XCTestCase {
    func testHeartbeatUsesProtocolV1AndMacOSIdentity() throws {
        let payload = HeartbeatPayload(
            agentId: "mac-test",
            timestamp: "2026-09-24T10:00:00.000Z",
            device: DeviceIdentity(
                hostname: "MacBook",
                operatingSystem: "macOS",
                operatingSystemVersion: "macOS 26",
                architecture: "arm64",
                manufacturer: "Apple Inc.",
                ipAddresses: ["192.168.1.20"],
                macAddresses: []
            )
        )
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: JSONEncoder().encode(payload)) as? [String: Any])
        XCTAssertEqual(object["type"] as? String, "heartbeat")
        XCTAssertEqual(object["protocolVersion"] as? Int, 1)
        XCTAssertEqual(object["agentId"] as? String, "mac-test")
    }

    func testMetricsUsePortableNames() {
        let names = Set(MacHostMetricsCollector().collect().map(\.name))
        XCTAssertTrue(names.contains("host.memory.total.bytes"))
        XCTAssertTrue(names.contains("host.disk.total.bytes"))
        XCTAssertTrue(names.contains("host.network.received.bytes"))
        XCTAssertTrue(names.contains("host.uptime.seconds"))
    }
}
