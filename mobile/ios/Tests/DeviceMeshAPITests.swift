import XCTest
@testable import DeviceMesh

final class DeviceMeshAPITests: XCTestCase {
    func testServerRequiresHTTPSAndRejectsEmbeddedCredentials() throws {
        XCTAssertNoThrow(try DeviceMeshAPI(baseURL: URL(string: "https://mesh.example.com")!))
        XCTAssertThrowsError(try DeviceMeshAPI(baseURL: URL(string: "http://mesh.example.com")!))
        XCTAssertThrowsError(try DeviceMeshAPI(baseURL: URL(string: "https://user:pass@mesh.example.com")!))
    }
}
