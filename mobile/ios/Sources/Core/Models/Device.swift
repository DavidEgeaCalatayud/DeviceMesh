import Foundation

struct Device: Codable, Identifiable {
    let id: String
    let hostname: String?
    let ipAddresses: [String]
    let status: String
    let operatingSystem: String?
    let manufacturer: String?
    let lastSeen: String?
}

struct HumanUser: Codable {
    let id: String
    let username: String
    let role: String
    let mfaEnabled: Bool
}

struct SessionTokens: Codable {
    let accessToken: String
    let refreshToken: String
    let expiresAt: String
    let user: HumanUser
}

struct Incident: Codable, Identifiable {
    let id: String
    let title: String?
    let severity: String?
    let status: String?
    let assignedTo: String?
}

struct Alert: Codable, Identifiable {
    let id: Int
    let deviceId: String
    let openedAt: String?
    let closedAt: String?
}

struct SyntheticMonitor: Codable, Identifiable {
    let id: String
    let name: String
    let kind: String
    let target: String
    let enabled: Bool
}

struct SyntheticProbe: Codable, Identifiable {
    let id: String
    let name: String
    let location: String
    let online: Bool
    let lastSeenAt: String?
}
