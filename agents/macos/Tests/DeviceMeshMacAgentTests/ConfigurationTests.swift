import XCTest
@testable import DeviceMeshMacAgent

final class ConfigurationTests: XCTestCase {
    func testEnvironmentClampsIntervalAndUsesExplicitAgentId() throws {
        let config = try AgentConfig.fromEnvironment([
            "DEVICEMESH_SERVER": "https://mesh.example.test",
            "DEVICEMESH_AGENT_ID": "macbook-test",
            "DEVICEMESH_INTERVAL_SECONDS": "1",
            "DEVICEMESH_ENROLLMENT_TOKEN": "token",
        ])
        XCTAssertEqual(config.serverURL.absoluteString, "https://mesh.example.test")
        XCTAssertEqual(config.agentId, "macbook-test")
        XCTAssertEqual(config.intervalSeconds, 5)
        XCTAssertEqual(config.enrollmentToken, "token")
    }

    func testRejectsNonHTTPServerURL() {
        XCTAssertThrowsError(try AgentConfig.fromEnvironment([
            "DEVICEMESH_SERVER": "file:///tmp/device",
            "DEVICEMESH_AGENT_ID": "macbook-test",
        ]))
    }
}
