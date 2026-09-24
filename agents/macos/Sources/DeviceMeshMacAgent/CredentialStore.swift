import Foundation
import Security

protocol AgentCredentialStore: Sendable {
    func load(agentId: String) throws -> String?
    func save(_ credential: String, agentId: String) throws
}

struct KeychainCredentialStore: AgentCredentialStore {
    private let service = "io.github.davidegeacalatayud.devicemesh.macos-agent"

    func load(agentId: String) throws -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: agentId,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess else { throw AgentError.keychain(status) }
        guard let data = item as? Data, let value = String(data: data, encoding: .utf8), !value.isEmpty else {
            throw AgentError.malformedResponse("Stored Keychain credential is invalid")
        }
        return value
    }

    func save(_ credential: String, agentId: String) throws {
        guard let data = credential.data(using: .utf8), !credential.isEmpty else {
            throw AgentError.configuration("Cannot save an empty agent credential")
        }
        let key: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: agentId,
        ]
        let attributes: [String: Any] = [kSecValueData as String: data]
        let updateStatus = SecItemUpdate(key as CFDictionary, attributes as CFDictionary)
        if updateStatus == errSecSuccess { return }
        guard updateStatus == errSecItemNotFound else { throw AgentError.keychain(updateStatus) }

        var add = key
        add[kSecValueData as String] = data
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        let addStatus = SecItemAdd(add as CFDictionary, nil)
        guard addStatus == errSecSuccess else { throw AgentError.keychain(addStatus) }
    }
}
