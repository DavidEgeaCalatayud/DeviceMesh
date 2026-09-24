import Foundation

let config: AgentConfig
do {
    config = try AgentConfig.fromEnvironment()
} catch {
    FileHandle.standardError.write(Data("DeviceMesh macOS agent configuration error: \(error)\n".utf8))
    exit(EXIT_FAILURE)
}

let agent = DeviceMeshMacAgent(config: config)
Task {
    await agent.runForever()
    exit(EXIT_SUCCESS)
}
RunLoop.main.run()
