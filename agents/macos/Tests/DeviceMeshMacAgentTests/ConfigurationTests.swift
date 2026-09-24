import XCTest
@testable import DeviceMeshMacAgent

final class ConfigurationTests: XCTestCase {
    func testEnvironmentClampsIntervalAndUsesExplicitAgentId() throws {
        let config = try AgentConfig.fromEnvironment([
            "DEVICEMESH_SERVER": "https://mesh.example.test",
            "DEVICEMESH_AGENT_ID": "macbook-test",
            "DEVICEMESH_INTERVAL_SECONDS": "1",
            "DEVICEMESH_ENROLLMENT_TOKEN": " token ",
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

    func testRejectsEmbeddedServerCredentials() {
        XCTAssertThrowsError(try AgentConfig.fromEnvironment([
            "DEVICEMESH_SERVER": "https://user:secret@mesh.example.test",
            "DEVICEMESH_AGENT_ID": "macbook-test",
        ]))
    }

    func testRejectsServerQueryAndFragment() {
        XCTAssertThrowsError(try AgentConfig.fromEnvironment([
            "DEVICEMESH_SERVER": "https://mesh.example.test?debug=true",
            "DEVICEMESH_AGENT_ID": "macbook-test",
        ]))
        XCTAssertThrowsError(try AgentConfig.fromEnvironment([
            "DEVICEMESH_SERVER": "https://mesh.example.test#fragment",
            "DEVICEMESH_AGENT_ID": "macbook-test",
        ]))
    }

    func testRejectsAgentIdBeyondProtocolLimit() {
        XCTAssertThrowsError(try AgentConfig.fromEnvironment([
            "DEVICEMESH_SERVER": "https://mesh.example.test",
            "DEVICEMESH_AGENT_ID": String(repeating: "a", count: AgentConfig.maximumAgentIdLength + 1),
        ]))
    }

    func testRejectsInvalidIntervalInsteadOfSilentlyFallingBack() {
        XCTAssertThrowsError(try AgentConfig.fromEnvironment([
            "DEVICEMESH_SERVER": "https://mesh.example.test",
            "DEVICEMESH_AGENT_ID": "macbook-test",
            "DEVICEMESH_INTERVAL_SECONDS": "not-a-number",
        ]))
    }
}
