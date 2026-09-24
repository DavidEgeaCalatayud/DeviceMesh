import XCTest
@testable import DeviceMeshMacAgent

final class RemoteOperationTests: XCTestCase {
    private let executor = RemoteOperationExecutor()

    func testAllowsOnlyDeclaredOperationsWithNoArguments() {
        for type in AgentOperation.allCases {
            let operation = ClaimedOperation(id: "op", operationType: type.rawValue, arguments: [:])
            XCTAssertEqual(executor.validate(operation), type)
        }
    }

    func testRejectsShellLikeOperation() {
        let operation = ClaimedOperation(
            id: "op",
            operationType: "shell.execute",
            arguments: ["command": .string("id")]
        )
        XCTAssertNil(executor.validate(operation))
    }

    func testRejectsArgumentsOnAllowedOperation() {
        let operation = ClaimedOperation(
            id: "op",
            operationType: AgentOperation.telemetryCollect.rawValue,
            arguments: ["path": .string("/tmp")]
        )
        XCTAssertNil(executor.validate(operation))
    }

    func testHealthCheckReportsMacOS() async {
        let operation = ClaimedOperation(id: "op", operationType: AgentOperation.agentHealthCheck.rawValue, arguments: [:])
        let outcome = await executor.execute(
            operation,
            agentId: "mac-1",
            publishHeartbeat: {},
            publishTelemetry: {}
        )
        XCTAssertTrue(outcome.succeeded)
        XCTAssertEqual(outcome.result["platform"], .string("macos"))
    }
}
