import Darwin
import Dispatch
import Foundation

enum ShutdownSignal {
    static func wait() async -> Int32 {
        await withCheckedContinuation { continuation in
            signal(SIGINT, SIG_IGN)
            signal(SIGTERM, SIG_IGN)

            let queue = DispatchQueue(label: "io.github.davidegeacalatayud.devicemesh.macos-agent.signals")
            let interrupt = DispatchSource.makeSignalSource(signal: SIGINT, queue: queue)
            let terminate = DispatchSource.makeSignalSource(signal: SIGTERM, queue: queue)
            let state = SignalContinuation(continuation: continuation, interrupt: interrupt, terminate: terminate)

            interrupt.setEventHandler { state.finish(signal: SIGINT) }
            terminate.setEventHandler { state.finish(signal: SIGTERM) }
            interrupt.resume()
            terminate.resume()
        }
    }
}

private final class SignalContinuation: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<Int32, Never>?
    private let interrupt: DispatchSourceSignal
    private let terminate: DispatchSourceSignal

    init(
        continuation: CheckedContinuation<Int32, Never>,
        interrupt: DispatchSourceSignal,
        terminate: DispatchSourceSignal
    ) {
        self.continuation = continuation
        self.interrupt = interrupt
        self.terminate = terminate
    }

    func finish(signal: Int32) {
        lock.lock()
        guard let continuation else {
            lock.unlock()
            return
        }
        self.continuation = nil
        lock.unlock()

        interrupt.cancel()
        terminate.cancel()
        continuation.resume(returning: signal)
    }
}
