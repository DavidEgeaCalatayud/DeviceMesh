import Foundation

struct AgentConfig: Equatable, Sendable {
    let serverURL: URL
    let agentId: String
    let intervalSeconds: UInt64
    let enrollmentToken: String?
    let credentialOverride: String?

    static func fromEnvironment(_ environment: [String: String] = ProcessInfo.processInfo.environment) throws -> AgentConfig {
        let rawServer = environment["DEVICEMESH_SERVER"] ?? "http://localhost:8000"
        guard let serverURL = URL(string: rawServer), let scheme = serverURL.scheme, ["http", "https"].contains(scheme) else {
            throw AgentError.configuration("DEVICEMESH_SERVER must be a valid http/https URL")
        }
        let hostname = Host.current().localizedName ?? ProcessInfo.processInfo.hostName
        let agentId = (environment["DEVICEMESH_AGENT_ID"] ?? hostname).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !agentId.isEmpty else { throw AgentError.configuration("DEVICEMESH_AGENT_ID cannot be empty") }
        let requestedInterval = UInt64(environment["DEVICEMESH_INTERVAL_SECONDS"] ?? "30") ?? 30
        return AgentConfig(
            serverURL: serverURL,
            agentId: agentId,
            intervalSeconds: max(5, requestedInterval),
            enrollmentToken: environment["DEVICEMESH_ENROLLMENT_TOKEN"]?.nilIfEmpty,
            credentialOverride: environment["DEVICEMESH_AGENT_CREDENTIAL"]?.nilIfEmpty
        )
    }
}

extension String {
    var nilIfEmpty: String? {
        let value = trimmingCharacters(in: .whitespacesAndNewlines)
        return value.isEmpty ? nil : value
    }
}

enum AgentError: Error, LocalizedError {
    case configuration(String)
    case keychain(OSStatus)
    case enrollment(String)
    case http(Int, String)
    case malformedResponse(String)

    var errorDescription: String? {
        switch self {
        case .configuration(let message), .enrollment(let message), .malformedResponse(let message): return message
        case .keychain(let status): return "Keychain error: \(status)"
        case .http(let status, let body): return "HTTP \(status): \(body)"
        }
    }
}

func iso8601Now() -> String {
    ISO8601DateFormatter.deviceMesh.string(from: Date())
}

extension ISO8601DateFormatter {
    static let deviceMesh: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()
}
