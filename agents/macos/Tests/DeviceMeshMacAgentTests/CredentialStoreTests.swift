import XCTest
@testable import DeviceMeshMacAgent

final class CredentialStoreTests: XCTestCase {
    func testKeychainCredentialRoundTripAndReplacement() throws {
        let service = "\(KeychainCredentialStore.defaultService).tests.\(UUID().uuidString)"
        let store = KeychainCredentialStore(service: service)
        let agentId = "mac-keychain-test"
        defer { try? store.remove(agentId: agentId) }

        XCTAssertNil(try store.load(agentId: agentId))

        try store.save("credential-one", agentId: agentId)
        XCTAssertEqual(try store.load(agentId: agentId), "credential-one")

        try store.save("credential-two", agentId: agentId)
        XCTAssertEqual(try store.load(agentId: agentId), "credential-two")

        try store.remove(agentId: agentId)
        XCTAssertNil(try store.load(agentId: agentId))
    }

    func testKeychainRejectsEmptyCredential() {
        let store = KeychainCredentialStore(
            service: "\(KeychainCredentialStore.defaultService).tests.\(UUID().uuidString)"
        )
        XCTAssertThrowsError(try store.save("", agentId: "mac-keychain-test"))
    }
}
