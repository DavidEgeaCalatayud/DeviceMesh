import Foundation

@main
enum DeviceMeshMacAgentMain {
    static func main() async {
        do {
            let config = try AgentConfig.fromEnvironment()
            let agent = DeviceMeshMacAgent(config: config)
            await agent.runForever()
        } catch {
            FileHandle.standardError.write(Data("DeviceMesh macOS agent configuration error: \(error)\n".utf8))
            exit(EXIT_FAILURE)
        }
    }
}
