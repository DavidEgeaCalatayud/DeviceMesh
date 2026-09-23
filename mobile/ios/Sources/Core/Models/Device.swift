import Foundation

struct Device: Codable, Identifiable {
    let id: String
    let hostname: String?
    let ipAddresses: [String]
    let status: String
}
