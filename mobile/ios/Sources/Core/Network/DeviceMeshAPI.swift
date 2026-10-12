import Foundation

enum DeviceMeshAPIError: Error, LocalizedError {
    case invalidServer
    case unauthorized
    case server(Int, String)

    var errorDescription: String? {
        switch self {
        case .invalidServer: return "DeviceMesh requires a valid HTTPS server."
        case .unauthorized: return "The DeviceMesh session is no longer valid."
        case let .server(_, message): return message
        }
    }
}

enum RemoteOperationPolicy {
    static let allowed: Set<String> = [
        "telemetry.collect",
        "inventory.refresh",
        "agent.health_check",
        "network.dns_lookup",
        "network.route_snapshot",
    ]

    static func validate(_ operationType: String) throws {
        guard allowed.contains(operationType) else {
            throw DeviceMeshAPIError.server(0, "Unsupported remote operation")
        }
    }
}

actor DeviceMeshAPI {
    private let baseURL: URL
    private var accessToken: String?

    init(baseURL: URL, accessToken: String? = nil) throws {
        guard baseURL.scheme?.lowercased() == "https",
              baseURL.host != nil,
              baseURL.user == nil,
              baseURL.password == nil else {
            throw DeviceMeshAPIError.invalidServer
        }
        self.baseURL = baseURL
        self.accessToken = accessToken
    }

    func setAccessToken(_ token: String?) {
        accessToken = token
    }

    func health() async -> Bool {
        (try? await request(path: "/health", authenticated: false) as EmptyResponse) != nil
    }

    func login(username: String, password: String, mfaCode: String?) async throws -> SessionTokens {
        var body: [String: String] = ["username": username, "password": password]
        if let mfaCode, !mfaCode.isEmpty { body["mfaCode"] = mfaCode }
        let session: SessionTokens = try await request(
            path: "/api/v1/auth/login",
            method: "POST",
            body: body,
            authenticated: false
        )
        accessToken = session.accessToken
        return session
    }

    func refresh(_ refreshToken: String) async throws -> SessionTokens {
        let session: SessionTokens = try await request(
            path: "/api/v1/auth/refresh",
            method: "POST",
            body: ["refreshToken": refreshToken],
            authenticated: false
        )
        accessToken = session.accessToken
        return session
    }

    func logout() async {
        let _: EmptyResponse? = try? await request(path: "/api/v1/auth/logout", method: "POST")
        accessToken = nil
    }

    func remoteOperations(deviceId: String) async throws -> [RemoteOperation] {
        guard let encoded = deviceId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) else {
            throw DeviceMeshAPIError.server(0, "Invalid device identifier")
        }
        return try await request(
            path: "/api/v1/operator/remote-operations?deviceId=\(encoded)&limit=100"
        )
    }

    func queueRemoteOperation(
        deviceId: String,
        operationType: String,
        hostname: String? = nil
    ) async throws -> RemoteOperation {
        try RemoteOperationPolicy.validate(operationType)
        var arguments: [String: String] = [:]
        if operationType == "network.dns_lookup" {
            guard let hostname,
                  !hostname.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                  hostname.count <= 253 else {
                throw DeviceMeshAPIError.server(0, "DNS lookup requires a valid hostname")
            }
            arguments["hostname"] = hostname.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        struct Payload: Codable {
            let deviceId: String
            let operationType: String
            let arguments: [String: String]
            let ttlSeconds: Int
        }
        return try await request(
            path: "/api/v1/operator/remote-operations",
            method: "POST",
            body: Payload(
                deviceId: deviceId,
                operationType: operationType,
                arguments: arguments,
                ttlSeconds: 300
            )
        )
    }

    func devices() async throws -> [Device] {
        try await request(path: "/api/v1/devices")
    }

    func incidents() async throws -> [Incident] {
        try await request(path: "/api/v1/incidents?limit=100&activeOnly=false")
    }

    func alerts() async throws -> [Alert] {
        try await request(path: "/api/v1/alerts?activeOnly=false&limit=100")
    }

    func syntheticMonitors() async throws -> [SyntheticMonitor] {
        try await request(path: "/api/v1/synthetic-monitors")
    }

    func syntheticProbes() async throws -> [SyntheticProbe] {
        try await request(path: "/api/v1/operator/synthetic-probes")
    }

    private func request<Response: Decodable, Body: Encodable>(
        path: String,
        method: String = "GET",
        body: Body? = Optional<String>.none,
        authenticated: Bool = true
    ) async throws -> Response {
        guard let url = URL(string: path, relativeTo: baseURL)?.absoluteURL,
              url.scheme == baseURL.scheme,
              url.host == baseURL.host else {
            throw DeviceMeshAPIError.invalidServer
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 20
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("DeviceMesh-iOS/0.2", forHTTPHeaderField: "User-Agent")
        if authenticated {
            guard let accessToken else { throw DeviceMeshAPIError.unauthorized }
            request.setValue("Bearer " + accessToken, forHTTPHeaderField: "Authorization")
        }
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONEncoder().encode(body)
        }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw DeviceMeshAPIError.server(0, "Invalid DeviceMesh response")
        }
        if http.statusCode == 401 { throw DeviceMeshAPIError.unauthorized }
        guard (200..<300).contains(http.statusCode) else {
            let detail = (try? JSONDecoder().decode(ErrorEnvelope.self, from: data).detail)
                ?? "DeviceMesh request failed"
            throw DeviceMeshAPIError.server(http.statusCode, detail)
        }
        if Response.self == EmptyResponse.self {
            return EmptyResponse() as! Response
        }
        return try JSONDecoder().decode(Response.self, from: data)
    }
}

private struct ErrorEnvelope: Codable { let detail: String? }
private struct EmptyResponse: Codable {}
