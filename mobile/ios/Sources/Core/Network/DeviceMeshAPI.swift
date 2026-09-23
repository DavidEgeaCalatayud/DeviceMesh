import Foundation

actor DeviceMeshAPI {
    let baseURL: URL
    init(baseURL: URL = URL(string: "http://localhost:8000")!) { self.baseURL = baseURL }

    func devices() async throws -> [Device] {
        let (data, response) = try await URLSession.shared.data(from: baseURL.appending(path: "/api/v1/devices"))
        guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw URLError(.badServerResponse) }
        return try JSONDecoder().decode([Device].self, from: data)
    }
}
