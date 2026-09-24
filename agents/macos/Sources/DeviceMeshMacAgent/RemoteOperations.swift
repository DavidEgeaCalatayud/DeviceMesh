import Foundation

struct OperationOutcome: Equatable, Sendable {
    let succeeded: Bool
    let result: [String: JSONValue]
    let error: String?
}

struct RemoteOperationExecutor {
    func validate(_ operation: ClaimedOperation) -> AgentOperation? {
        guard operation.arguments.isEmpty else { return nil }
        return AgentOperation(rawValue: operation.operationType)
    }

    func execute(
        _ operation: ClaimedOperation,
        agentId: String,
        publishHeartbeat: () async throws -> Void,
        publishTelemetry: () async throws -> Void
    ) async -> OperationOutcome {
        guard let type = validate(operation) else {
            return .init(succeeded: false, result: [:], error: "unsupported operation type or arguments")
        }
        do {
            switch type {
            case .telemetryCollect:
                try await publishTelemetry()
                return .init(succeeded: true, result: ["collectedAt": .string(iso8601Now())], error: nil)
            case .inventoryRefresh:
                try await publishHeartbeat()
                return .init(succeeded: true, result: ["refreshedAt": .string(iso8601Now())], error: nil)
            case .agentHealthCheck:
                return .init(
                    succeeded: true,
                    result: [
                        "agentId": .string(agentId),
                        "status": .string("ok"),
                        "checkedAt": .string(iso8601Now()),
                        "platform": .string("macos"),
                        "agentVersion": .string(DeviceMeshMacAgentVersion.current),
                        "protocolVersion": .number(Double(DeviceMeshMacAgentVersion.protocolVersion)),
                    ],
                    error: nil
                )
            }
        } catch {
            return .init(succeeded: false, result: [:], error: String(describing: error))
        }
    }
}
