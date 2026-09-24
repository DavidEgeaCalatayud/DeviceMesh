import Foundation
import XCTest
@testable import DeviceMeshMacAgent

final class AgentLifecycleTests: XCTestCase {
    func testEnrollmentPersistsCredentialAndSecondAgentReusesIt() async throws {
        let api = MockAgentAPI()
        let store = MemoryCredentialStore()
        let config = AgentConfig(
            serverURL: try XCTUnwrap(URL(string: "https://mesh.example.test")),
            agentId: "mac-lifecycle",
            intervalSeconds: 30,
            enrollmentToken: "one-time-token",
            credentialOverride: nil
        )

        let first = DeviceMeshMacAgent(config: config, api: api, credentialStore: store)
        let firstCredential = try await first.ensureCredential()
        XCTAssertEqual(firstCredential, "issued-credential")
        XCTAssertEqual(store.value, "issued-credential")
        let enrollmentCountAfterFirst = await api.enrollmentCount()
        XCTAssertEqual(enrollmentCountAfterFirst, 1)

        let reuseConfig = AgentConfig(
            serverURL: config.serverURL,
            agentId: config.agentId,
            intervalSeconds: 30,
            enrollmentToken: nil,
            credentialOverride: nil
        )
        let second = DeviceMeshMacAgent(config: reuseConfig, api: api, credentialStore: store)
        let reusedCredential = try await second.ensureCredential()
        XCTAssertEqual(reusedCredential, "issued-credential")
        let enrollmentCountAfterReuse = await api.enrollmentCount()
        XCTAssertEqual(enrollmentCountAfterReuse, 1)
    }

    func testRunCyclePublishesHeartbeatTelemetryAndCompletesHealthOperation() async throws {
        let operation = ClaimedOperation(
            id: "health-1",
            operationType: AgentOperation.agentHealthCheck.rawValue,
            arguments: [:]
        )
        let api = MockAgentAPI(operation: operation)
        let store = MemoryCredentialStore(value: "stored-credential")
        let config = AgentConfig(
            serverURL: try XCTUnwrap(URL(string: "https://mesh.example.test")),
            agentId: "mac-lifecycle",
            intervalSeconds: 30,
            enrollmentToken: nil,
            credentialOverride: nil
        )
        let agent = DeviceMeshMacAgent(config: config, api: api, credentialStore: store)

        try await agent.runCycle()

        let snapshot = await api.snapshot()
        XCTAssertEqual(snapshot.heartbeats, 1)
        XCTAssertEqual(snapshot.telemetry, 1)
        XCTAssertEqual(snapshot.claims, 1)
        XCTAssertEqual(snapshot.completions.count, 1)
        XCTAssertEqual(snapshot.completions.first?.0, "health-1")
        XCTAssertEqual(snapshot.completions.first?.1.status, "succeeded")
        XCTAssertEqual(snapshot.completions.first?.1.result["platform"], .string("macos"))
        XCTAssertEqual(snapshot.completions.first?.1.result["agentVersion"], .string(AgentVersion.current))
        XCTAssertEqual(
            snapshot.completions.first?.1.result["protocolVersion"],
            .number(Double(AgentVersion.protocolVersion))
        )
    }
}

private final class MemoryCredentialStore: AgentCredentialStore, @unchecked Sendable {
    private let lock = NSLock()
    private var stored: String?

    init(value: String? = nil) {
        stored = value
    }

    var value: String? {
        lock.lock()
        defer { lock.unlock() }
        return stored
    }

    func load(agentId: String) throws -> String? {
        value
    }

    func save(_ credential: String, agentId: String) throws {
        lock.lock()
        stored = credential
        lock.unlock()
    }
}

private actor MockAgentAPI: DeviceMeshAgentAPI {
    struct Snapshot: Sendable {
        let heartbeats: Int
        let telemetry: Int
        let claims: Int
        let completions: [(String, OperationCompletion)]
    }

    private var enrollments = 0
    private var heartbeatCalls = 0
    private var telemetryCalls = 0
    private var claimCalls = 0
    private var completionCalls: [(String, OperationCompletion)] = []
    private var nextOperation: ClaimedOperation?

    init(operation: ClaimedOperation? = nil) {
        nextOperation = operation
    }

    func enroll(token: String, agentId: String) async throws -> String {
        enrollments += 1
        return "issued-credential"
    }

    func heartbeat(_ payload: HeartbeatPayload, credential: String, agentId: String) async throws {
        heartbeatCalls += 1
        XCTAssertEqual(credential, "stored-credential")
        XCTAssertEqual(agentId, "mac-lifecycle")
        XCTAssertEqual(payload.protocolVersion, 1)
    }

    func telemetry(_ payload: TelemetryPayload, credential: String, agentId: String) async throws {
        telemetryCalls += 1
        XCTAssertEqual(credential, "stored-credential")
        XCTAssertFalse(payload.metrics.isEmpty)
    }

    func claimOperation(credential: String, agentId: String) async throws -> ClaimedOperation? {
        claimCalls += 1
        defer { nextOperation = nil }
        return nextOperation
    }

    func completeOperation(
        _ operationId: String,
        completion: OperationCompletion,
        credential: String,
        agentId: String
    ) async throws {
        completionCalls.append((operationId, completion))
    }

    func enrollmentCount() -> Int { enrollments }

    func snapshot() -> Snapshot {
        Snapshot(
            heartbeats: heartbeatCalls,
            telemetry: telemetryCalls,
            claims: claimCalls,
            completions: completionCalls
        )
    }
}
