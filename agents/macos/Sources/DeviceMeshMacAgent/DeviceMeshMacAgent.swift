import Foundation

final class DeviceMeshMacAgent {
    private let config: AgentConfig
    private let api: DeviceMeshAgentAPI
    private let credentialStore: AgentCredentialStore
    private let identityCollector: MacHostIdentityCollector
    private let metricsCollector: MacHostMetricsCollector
    private let operationExecutor = RemoteOperationExecutor()
    private let logger: AgentLogger
    private var credential: String?

    init(
        config: AgentConfig,
        api: DeviceMeshAgentAPI? = nil,
        credentialStore: AgentCredentialStore = KeychainCredentialStore(),
        identityCollector: MacHostIdentityCollector = .init(),
        metricsCollector: MacHostMetricsCollector = .init(),
        logger: AgentLogger = .init()
    ) {
        self.config = config
        self.api = api ?? DeviceMeshAPIClient(serverURL: config.serverURL)
        self.credentialStore = credentialStore
        self.identityCollector = identityCollector
        self.metricsCollector = metricsCollector
        self.logger = logger
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
            throw AgentError.configuration(
                "No Keychain credential found and DEVICEMESH_ENROLLMENT_TOKEN is not set"
            )
        }

        let enrolled = try await api.enroll(token: enrollmentToken, agentId: config.agentId)
        try credentialStore.save(enrolled, agentId: config.agentId)
        credential = enrolled
        logger.info("Enrollment completed for agent \(config.agentId)")
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
        guard let operation = try await api.claimOperation(
            credential: credential,
            agentId: config.agentId
        ) else {
            return
        }

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
        try await api.completeOperation(
            operation.id,
            completion: completion,
            credential: credential,
            agentId: config.agentId
        )
    }

    func runCycle() async throws {
        try await publishHeartbeat()
        try await publishTelemetry()
        try await processOneOperation()
    }

    func runForever() async {
        logger.info(
            "Starting macOS agent \(AgentVersion.current) for \(config.agentId) with protocol v\(AgentVersion.protocolVersion)"
        )
        while !Task.isCancelled {
            do {
                try await runCycle()
            } catch is CancellationError {
                break
            } catch {
                logger.warning("Agent cycle failed: \(String(describing: error))")
            }

            do {
                try await Task.sleep(nanoseconds: config.intervalSeconds * 1_000_000_000)
            } catch is CancellationError {
                break
            } catch {
                logger.warning("Agent sleep interrupted: \(String(describing: error))")
            }
        }
        logger.info("macOS agent stopped for \(config.agentId)")
    }
}
