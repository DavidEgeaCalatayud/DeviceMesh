import Foundation
import Security

final class SecureSessionStore {
    private let service = "io.github.davidegeacalatayud.devicemesh.session"
    private let account = "human-session"

    func save(_ session: SessionTokens) throws {
        let data = try JSONEncoder().encode(session)
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

    func load() -> SessionTokens? {
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return try? JSONDecoder().decode(SessionTokens.self, from: data)
    }

    func clear() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
    }

    var server: URL {
        get {
            if let value = UserDefaults.standard.string(forKey: "DeviceMeshServer"),
               let url = URL(string: value) { return url }
            return URL(string: "https://mesh.example.com")!
        }
        set { UserDefaults.standard.set(newValue.absoluteString, forKey: "DeviceMeshServer") }
    }

    enum StoreError: Error { case keychain(OSStatus) }
}
