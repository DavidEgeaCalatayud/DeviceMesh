import Foundation
import XCTest
@testable import DeviceMeshMacAgent

final class APIClientContractTests: XCTestCase {
    override func tearDown() {
        URLProtocolStub.storage.handler = nil
        super.tearDown()
    }

    func testHeartbeatUsesAgentAuthenticationContract() async throws {
        let session = makeStubSession()
        let client = DeviceMeshAPIClient(
            serverURL: try XCTUnwrap(URL(string: "https://mesh.example.test")),
            session: session
        )
        let payload = HeartbeatPayload(
            agentId: "mac-01",
            timestamp: "2026-09-24T10:00:00.000Z",
            device: DeviceIdentity(
                hostname: "Mac",
                operatingSystem: "macOS",
                operatingSystemVersion: "26.0",
                architecture: "arm64",
                manufacturer: "Apple Inc.",
                ipAddresses: ["192.168.1.20"],
                macAddresses: ["AA:BB:CC:DD:EE:FF"]
            )
        )

        URLProtocolStub.storage.handler = { request in
            XCTAssertEqual(request.httpMethod, "POST")
            XCTAssertEqual(request.url?.path, "/api/v1/agents/heartbeat")
            XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Agent secret")
            XCTAssertEqual(request.value(forHTTPHeaderField: "X-DeviceMesh-Agent-ID"), "mac-01")
            XCTAssertNotNil(request.value(forHTTPHeaderField: "X-DeviceMesh-Timestamp"))
            let nonce = try XCTUnwrap(request.value(forHTTPHeaderField: "X-DeviceMesh-Nonce"))
            XCTAssertEqual(nonce.count, 32)
            XCTAssertTrue(nonce.allSatisfy { $0.isHexDigit })
            return stubResponse(request, status: 204)
        }

        try await client.heartbeat(payload, credential: "secret", agentId: "mac-01")
    }

    func testEnrollmentUsesUnauthenticatedEnrollmentEndpoint() async throws {
        let session = makeStubSession()
        let client = DeviceMeshAPIClient(
            serverURL: try XCTUnwrap(URL(string: "https://mesh.example.test")),
            session: session
        )

        URLProtocolStub.storage.handler = { request in
            XCTAssertEqual(request.url?.path, "/api/v1/agents/enroll")
            XCTAssertNil(request.value(forHTTPHeaderField: "Authorization"))
            let body = try requestBodyData(request)
            let object = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: String])
            XCTAssertEqual(object["token"], "one-time")
            XCTAssertEqual(object["agentId"], "mac-01")
            let response = try XCTUnwrap(HTTPURLResponse(
                url: try XCTUnwrap(request.url),
                statusCode: 200,
                httpVersion: nil,
                headerFields: ["Content-Type": "application/json"]
            ))
            return (response, Data("{\"credential\":\"issued-secret\"}".utf8))
        }

        let credential = try await client.enroll(token: "one-time", agentId: "mac-01")
        XCTAssertEqual(credential, "issued-secret")
    }

    func testNoContentOperationClaimReturnsNil() async throws {
        let session = makeStubSession()
        let client = DeviceMeshAPIClient(
            serverURL: try XCTUnwrap(URL(string: "https://mesh.example.test")),
            session: session
        )

        URLProtocolStub.storage.handler = { request in
            XCTAssertEqual(request.url?.path, "/api/v1/agents/operations/claim")
            return stubResponse(request, status: 204)
        }

        let operation = try await client.claimOperation(credential: "secret", agentId: "mac-01")
        XCTAssertNil(operation)
    }

    func testOperationCompletionUsesAuthenticatedOperationPath() async throws {
        let session = makeStubSession()
        let client = DeviceMeshAPIClient(
            serverURL: try XCTUnwrap(URL(string: "https://mesh.example.test")),
            session: session
        )
        let completion = OperationCompletion(
            status: "succeeded",
            result: ["status": .string("ok")],
            error: nil
        )

        URLProtocolStub.storage.handler = { request in
            XCTAssertEqual(request.url?.path, "/api/v1/agents/operations/op-123/complete")
            XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Agent secret")
            return stubResponse(request, status: 200)
        }

        try await client.completeOperation(
            "op-123",
            completion: completion,
            credential: "secret",
            agentId: "mac-01"
        )
    }

    private func makeStubSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [URLProtocolStub.self]
        return URLSession(configuration: configuration)
    }
}

private func requestBodyData(_ request: URLRequest) throws -> Data {
    if let body = request.httpBody {
        return body
    }
    guard let stream = request.httpBodyStream else {
        throw StubError.missingRequestBody
    }

    stream.open()
    defer { stream.close() }
    var result = Data()
    var buffer = [UInt8](repeating: 0, count: 1024)
    while true {
        let read = stream.read(&buffer, maxLength: buffer.count)
        if read > 0 {
            result.append(contentsOf: buffer[0..<read])
        } else if read == 0 {
            break
        } else {
            throw stream.streamError ?? StubError.requestBodyReadFailed
        }
    }
    return result
}

private func stubResponse(_ request: URLRequest, status: Int) -> (HTTPURLResponse, Data) {
    let response = HTTPURLResponse(
        url: request.url!,
        statusCode: status,
        httpVersion: nil,
        headerFields: nil
    )!
    return (response, Data())
}

private final class URLProtocolStub: URLProtocol {
    static let storage = HandlerStorage()

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let handler = Self.storage.handler else {
            client?.urlProtocol(self, didFailWithError: StubError.missingHandler)
            return
        }
        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}

private final class HandlerStorage: @unchecked Sendable {
    private let lock = NSLock()
    private var stored: ((URLRequest) throws -> (HTTPURLResponse, Data))?

    var handler: ((URLRequest) throws -> (HTTPURLResponse, Data))? {
        get {
            lock.lock()
            defer { lock.unlock() }
            return stored
        }
        set {
            lock.lock()
            stored = newValue
            lock.unlock()
        }
    }
}

private enum StubError: Error {
    case missingHandler
    case missingRequestBody
    case requestBodyReadFailed
}
