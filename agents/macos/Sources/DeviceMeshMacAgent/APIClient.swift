import Foundation

protocol DeviceMeshAgentAPI: Sendable {
    func enroll(token: String, agentId: String) async throws -> String
    func heartbeat(_ payload: HeartbeatPayload, credential: String, agentId: String) async throws
    func telemetry(_ payload: TelemetryPayload, credential: String, agentId: String) async throws
    func claimOperation(credential: String, agentId: String) async throws -> ClaimedOperation?
    func completeOperation(_ operationId: String, completion: OperationCompletion, credential: String, agentId: String) async throws
}

struct DeviceMeshAPIClient: DeviceMeshAgentAPI {
    let serverURL: URL
    let session: URLSession
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()

    init(serverURL: URL, session: URLSession = .shared) {
        self.serverURL = serverURL
        self.session = session
    }

    func enroll(token: String, agentId: String) async throws -> String {
        let request = try request(path: "/api/v1/agents/enroll", body: EnrollmentRequest(token: token, agentId: agentId))
        let (data, response) = try await session.data(for: request)
        try validate(response: response, data: data, allowNoContent: false)
        let enrollment = try decoder.decode(EnrollmentResponse.self, from: data)
        guard !enrollment.credential.isEmpty else { throw AgentError.enrollment("Enrollment returned an empty credential") }
        return enrollment.credential
    }

    func heartbeat(_ payload: HeartbeatPayload, credential: String, agentId: String) async throws {
        let req = try authenticatedRequest(path: "/api/v1/agents/heartbeat", body: payload, credential: credential, agentId: agentId)
        let (data, response) = try await session.data(for: req)
        try validate(response: response, data: data)
    }

    func telemetry(_ payload: TelemetryPayload, credential: String, agentId: String) async throws {
        let req = try authenticatedRequest(path: "/api/v1/agents/telemetry", body: payload, credential: credential, agentId: agentId)
        let (data, response) = try await session.data(for: req)
        try validate(response: response, data: data)
    }

    func claimOperation(credential: String, agentId: String) async throws -> ClaimedOperation? {
        let req = try authenticatedRequest(path: "/api/v1/agents/operations/claim", body: EmptyObject(), credential: credential, agentId: agentId)
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw AgentError.malformedResponse("Missing HTTP response") }
        if http.statusCode == 204 { return nil }
        try validate(response: response, data: data, allowNoContent: false)
        return try decoder.decode(ClaimedOperation.self, from: data)
    }

    func completeOperation(_ operationId: String, completion: OperationCompletion, credential: String, agentId: String) async throws {
        let path = "/api/v1/agents/operations/\(operationId)/complete"
        let req = try authenticatedRequest(path: path, body: completion, credential: credential, agentId: agentId)
        let (data, response) = try await session.data(for: req)
        try validate(response: response, data: data)
    }

    private func request<T: Encodable>(path: String, body: T) throws -> URLRequest {
        let url = serverURL.appendingPathComponent(path.trimmingCharacters(in: CharacterSet(charactersIn: "/")))
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(body)
        request.timeoutInterval = 10
        return request
    }

    private func authenticatedRequest<T: Encodable>(path: String, body: T, credential: String, agentId: String) throws -> URLRequest {
        var req = try request(path: path, body: body)
        req.setValue("Agent \(credential)", forHTTPHeaderField: "Authorization")
        req.setValue(agentId, forHTTPHeaderField: "X-DeviceMesh-Agent-ID")
        req.setValue(iso8601Now(), forHTTPHeaderField: "X-DeviceMesh-Timestamp")
        req.setValue(UUID().uuidString.replacingOccurrences(of: "-", with: ""), forHTTPHeaderField: "X-DeviceMesh-Nonce")
        return req
    }

    private func validate(response: URLResponse, data: Data, allowNoContent: Bool = true) throws {
        guard let http = response as? HTTPURLResponse else { throw AgentError.malformedResponse("Missing HTTP response") }
        let ok = (200..<300).contains(http.statusCode) && (allowNoContent || http.statusCode != 204)
        guard ok else {
            throw AgentError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
    }
}

private struct EmptyObject: Codable {}
