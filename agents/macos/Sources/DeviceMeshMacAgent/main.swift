import Foundation

let logger = AgentLogger(category: "bootstrap")
let config: AgentConfig

do {
    config = try AgentConfig.fromEnvironment()
} catch {
    logger.error("macOS agent configuration error: \(String(describing: error))")
    exit(EXIT_FAILURE)
}

let agent = DeviceMeshMacAgent(config: config)
Task {
    let worker = Task {
        await agent.runForever()
    }

    let receivedSignal = await ShutdownSignal.wait()
    logger.info("Received signal \(receivedSignal); stopping macOS agent")
    worker.cancel()
    await worker.value
    exit(EXIT_SUCCESS)
}

RunLoop.main.run()
