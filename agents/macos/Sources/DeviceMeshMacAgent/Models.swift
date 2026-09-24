import Foundation

enum AgentOperation: String, CaseIterable, Sendable {
    case telemetryCollect = "telemetry.collect"
    case inventoryRefresh = "inventory.refresh"
    case agentHealthCheck = "agent.health_check"
}

struct DeviceIdentity: Codable, Equatable, Sendable {
    let hostname: String?
    let operatingSystem: String?
    let operatingSystemVersion: String?
    let architecture: String?
    let manufacturer: String?
    let ipAddresses: [String]
    let macAddresses: [String]
}

struct HeartbeatPayload: Codable, Equatable, Sendable {
    let type = "heartbeat"
    let protocolVersion = 1
    let agentId: String
    let timestamp: String
    let device: DeviceIdentity
}

struct MetricPayload: Codable, Equatable, Sendable {
    let name: String
    let value: Double
    let unit: String
}

struct TelemetryPayload: Codable, Equatable, Sendable {
    let type = "telemetry"
    let protocolVersion = 1
    let agentId: String
    let timestamp: String
    let metrics: [MetricPayload]
}

enum JSONValue: Codable, Equatable, Sendable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() { self = .null }
        else if let value = try? container.decode(Bool.self) { self = .bool(value) }
        else if let value = try? container.decode(Double.self) { self = .number(value) }
        else if let value = try? container.decode(String.self) { self = .string(value) }
        else if let value = try? container.decode([String: JSONValue].self) { self = .object(value) }
        else if let value = try? container.decode([JSONValue].self) { self = .array(value) }
        else { throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unsupported JSON value") }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value): try container.encode(value)
        case .number(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }
}

struct ClaimedOperation: Codable, Equatable, Sendable {
    let id: String
    let operationType: String
    let arguments: [String: JSONValue]
}

struct OperationCompletion: Codable, Sendable {
    let status: String
    let result: [String: JSONValue]
    let error: String?
}

struct EnrollmentRequest: Codable, Sendable {
    let token: String
    let agentId: String
}

struct EnrollmentResponse: Codable, Sendable {
    let credential: String
}
