import Foundation
import OSLog

struct AgentLogger: Sendable {
    private let logger: Logger

    init(category: String = "agent") {
        logger = Logger(
            subsystem: "io.github.davidegeacalatayud.devicemesh",
            category: category
        )
    }

    func info(_ message: String) {
        logger.info("\(message, privacy: .public)")
    }

    func warning(_ message: String) {
        logger.warning("\(message, privacy: .public)")
    }

    func error(_ message: String) {
        logger.error("\(message, privacy: .public)")
    }
}
