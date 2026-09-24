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
                macAddresses: ["AA:BB:CC:DD:EE:FF"]
            )
        )
        let object = try XCTUnwrap(
            JSONSerialization.jsonObject(with: JSONEncoder().encode(payload)) as? [String: Any]
        )
        XCTAssertEqual(object["type"] as? String, "heartbeat")
        XCTAssertEqual(object["protocolVersion"] as? Int, 1)
        XCTAssertEqual(object["agentId"] as? String, "mac-test")
        let device = try XCTUnwrap(object["device"] as? [String: Any])
        XCTAssertEqual(device["operatingSystem"] as? String, "macOS")
        XCTAssertEqual(device["manufacturer"] as? String, "Apple Inc.")
        XCTAssertEqual(device["macAddresses"] as? [String], ["AA:BB:CC:DD:EE:FF"])
    }

    func testLiveIdentityHasExpectedMacOSPlatformFields() {
        let identity = MacHostIdentityCollector().collect()
        XCTAssertEqual(identity.operatingSystem, "macOS")
        XCTAssertEqual(identity.manufacturer, "Apple Inc.")
        XCTAssertFalse(identity.hostname?.isEmpty ?? true)
        XCTAssertFalse(identity.architecture?.isEmpty ?? true)
    }

    func testMetricsUsePortableNamesAndFiniteValues() {
        let metrics = MacHostMetricsCollector().collect()
        let names = Set(metrics.map(\.name))
        let required = Set([
            "host.memory.total.bytes",
            "host.memory.used.bytes",
            "host.memory.utilization.percent",
            "host.disk.total.bytes",
            "host.disk.free.bytes",
            "host.disk.used.bytes",
            "host.disk.utilization.percent",
            "host.network.received.bytes",
            "host.network.sent.bytes",
            "host.uptime.seconds",
        ])
        XCTAssertTrue(required.isSubset(of: names))
        XCTAssertTrue(metrics.allSatisfy { $0.value.isFinite && $0.value >= 0 })

        for metric in metrics where metric.name.hasSuffix("utilization.percent") {
            XCTAssertLessThanOrEqual(metric.value, 100)
        }
    }

    func testSecondCpuSampleCanPublishPortableCpuMetric() {
        let collector = MacHostMetricsCollector()
        _ = collector.collect()
        Thread.sleep(forTimeInterval: 0.05)
        let metrics = collector.collect()
        let cpu = metrics.first { $0.name == "host.cpu.utilization.percent" }
        XCTAssertNotNil(cpu)
        if let cpu {
            XCTAssertGreaterThanOrEqual(cpu.value, 0)
            XCTAssertLessThanOrEqual(cpu.value, 100)
            XCTAssertEqual(cpu.unit, "percent")
        }
    }
}
