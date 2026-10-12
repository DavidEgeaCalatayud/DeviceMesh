import Foundation
import Security

final class SecureSessionStore {
    private let service = "io.github.davidegeacalatayud.devicemesh.session"
    private let sessionAccount = "human-session"
    private let pushAccount = "apns-token"

    func save(_ session: SessionTokens) throws {
        try saveKeychain(
            account: sessionAccount,
            data: JSONEncoder().encode(session)
        )
    }

    func load() -> SessionTokens? {
        guard let data = readKeychain(account: sessionAccount) else { return nil }
        return try? JSONDecoder().decode(SessionTokens.self, from: data)
    }

    func clear() {
        deleteKeychain(account: sessionAccount)
    }

    func savePushToken(_ token: String) throws {
        guard let data = token.data(using: .utf8) else {
            throw StoreError.encoding
        }
        try saveKeychain(account: pushAccount, data: data)
    }

    func pushToken() -> String? {
        guard let data = readKeychain(account: pushAccount) else { return nil }
        return String(data: data, encoding: .utf8)
    }

    var installationId: String {
        if let value = UserDefaults.standard.string(forKey: "DeviceMeshInstallationId") {
            return value
        }
        let value = UUID().uuidString
        UserDefaults.standard.set(value, forKey: "DeviceMeshInstallationId")
        return value
    }

    var server: URL {
        get {
            if let value = UserDefaults.standard.string(forKey: "DeviceMeshServer"),
               let url = URL(string: value) { return url }
            return URL(string: "https://mesh.example.com")!
        }
        set { UserDefaults.standard.set(newValue.absoluteString, forKey: "DeviceMeshServer") }
    }

    private func saveKeychain(account: String, data: Data) throws {
        let base: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(base as CFDictionary)
        var add = base
        add[kSecValueData as String] = data
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(add as CFDictionary, nil)
        guard status == errSecSuccess else { throw StoreError.keychain(status) }
    }

    private func readKeychain(account: String) -> Data? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return data
    }

    private func deleteKeychain(account: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
    }

    enum StoreError: Error {
        case encoding
        case keychain(OSStatus)
    }
}
