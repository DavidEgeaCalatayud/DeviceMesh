import Foundation

final class DeviceMeshMacAgent {
    private let config: AgentConfig
    private let api: DeviceMeshAgentAPI
    private let credentialStore: AgentCredentialStore
    private let identityCollector: MacHostIdentityCollector
    private let metricsCollector: MacHostMetricsCollector
    private let operationExecutor = RemoteOperationExecutor()
    private var credential: String?

    init(
        config: AgentConfig,
        api: DeviceMeshAgentAPI? = nil,
        credentialStore: AgentCredentialStore = KeychainCredentialStore(),
        identityCollector: MacHostIdentityCollector = .init(),
        metricsCollector: MacHostMetricsCollector = .init()
    ) {
        self.config = config
        self.api = api ?? DeviceMeshAPIClient(serverURL: config.serverURL)
        self.credentialStore = credentialStore
        self.identityCollector = identityCollector
        self.metricsCollector = metricsCollector
    }

    func ensureCredential() async throws -> String {
        if let credential { return credential }
        if let override = config.credentialOverride {
            credential = override
            return override
        }
        if let stored = try credentialStore.load(agentId: config.agentId) {
            credential = stored
            return stored
        }
        guard let enrollmentToken = config.enrollmentToken else {
            throw AgentError.configuration("No Keychain credential found and DEVICEMESH_ENROLLMENT_TOKEN is not set")
        }
        let enrolled = try await api.enroll(token: enrollmentToken, agentId: config.agentId)
        try credentialStore.save(enrolled, agentId: config.agentId)
        credential = enrolled
        return enrolled
    }

    func publishHeartbeat() async throws {
        let credential = try await ensureCredential()
        let payload = HeartbeatPayload(
            agentId: config.agentId,
            timestamp: iso8601Now(),
            device: identityCollector.collect()
        )
        try await api.heartbeat(payload, credential: credential, agentId: config.agentId)
    }

    func publishTelemetry() async throws {
        let credential = try await ensureCredential()
        let payload = TelemetryPayload(
            agentId: config.agentId,
            timestamp: iso8601Now(),
            metrics: metricsCollector.collect()
        )
        try await api.telemetry(payload, credential: credential, agentId: config.agentId)
    }

    func processOneOperation() async throws {
        let credential = try await ensureCredential()
        guard let operation = try await api.claimOperation(credential: credential, agentId: config.agentId) else { return }
        let outcome = await operationExecutor.execute(
            operation,
            agentId: config.agentId,
            publishHeartbeat: { try await self.publishHeartbeat() },
            publishTelemetry: { try await self.publishTelemetry() }
        )
        let completion = OperationCompletion(
            status: outcome.succeeded ? "succeeded" : "failed",
            result: outcome.result,
            error: outcome.error.map { String($0.prefix(1024)) }
        )
        try await api.completeOperation(operation.id, completion: completion, credential: credential, agentId: config.agentId)
    }

    func runCycle() async throws {
        try await publishHeartbeat()
        try await publishTelemetry()
        try await processOneOperation()
    }

    func runForever() async {
        while !Task.isCancelled {
            do {
                try await runCycle()
            } catch {
                FileHandle.standardError.write(Data("DeviceMesh macOS agent error: \(error)\n".utf8))
            }
            try? await Task.sleep(for: .seconds(config.intervalSeconds))
        }
    }
}
