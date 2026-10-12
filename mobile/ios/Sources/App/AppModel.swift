import Foundation
import UIKit
import UserNotifications

@MainActor
final class AppModel: ObservableObject {
    @Published var session: SessionTokens?
    @Published var devices: [Device] = []
    @Published var incidents: [Incident] = []
    @Published var alerts: [Alert] = []
    @Published var monitors: [SyntheticMonitor] = []
    @Published var probes: [SyntheticProbe] = []
    @Published var operationsByDevice: [String: [RemoteOperation]] = [:]
    @Published var loading = false
    @Published var error: String?

    private let store = SecureSessionStore()
    private var api: DeviceMeshAPI

    init() {
        let arguments = ProcessInfo.processInfo.arguments
#if DEBUG
        if arguments.contains("-DeviceMeshUITestAuthenticated") {
            let fixture = SessionTokens(
                accessToken: "ui-test-access",
                refreshToken: "ui-test-refresh",
                expiresAt: "2099-01-01T00:00:00Z",
                user: HumanUser(
                    id: "ui-test-user",
                    username: "ui-test",
                    role: "administrator",
                    mfaEnabled: true
                )
            )
            self.session = fixture
            self.api = try! DeviceMeshAPI(
                baseURL: URL(string: "https://mesh.example.com")!,
                accessToken: fixture.accessToken
            )
            return
        }
#endif
        if arguments.contains("-DeviceMeshUITestReset") {
            store.clear()
        }
        let restored = store.load()
        self.session = restored
        self.api = try! DeviceMeshAPI(baseURL: store.server, accessToken: restored?.accessToken)
        if restored != nil {
            Task {
                await refreshAll()
                await enablePushNotifications()
            }
        }
    }

    func login(server: String, username: String, password: String, mfaCode: String) async {
        loading = true
        error = nil
        defer { loading = false }
        do {
            guard let url = URL(string: server) else { throw DeviceMeshAPIError.invalidServer }
            let nextAPI = try DeviceMeshAPI(baseURL: url)
            let nextSession = try await nextAPI.login(
                username: username,
                password: password,
                mfaCode: mfaCode.isEmpty ? nil : mfaCode
            )
            try store.save(nextSession)
            store.server = url
            api = nextAPI
            session = nextSession
            await refreshAll()
            await enablePushNotifications()
        } catch {
            self.error = error.localizedDescription
        }
    }

    func refreshAll() async {
        guard let current = session else { return }
        loading = true
        error = nil
        defer { loading = false }
        do {
            try await loadData()
        } catch DeviceMeshAPIError.unauthorized {
            do {
                let refreshed = try await api.refresh(current.refreshToken)
                try store.save(refreshed)
                session = refreshed
                try await loadData()
            } catch {
                store.clear()
                session = nil
                self.error = "Session expired"
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func loadData() async throws {
        async let devices = api.devices()
        async let incidents = api.incidents()
        async let alerts = api.alerts()
        async let monitors = api.syntheticMonitors()
        self.devices = try await devices
        self.incidents = try await incidents
        self.alerts = try await alerts
        self.monitors = try await monitors
        self.probes = (try? await api.syntheticProbes()) ?? []
    }

    func deviceDetail(_ deviceId: String) async throws -> (DeviceHealth, [MetricSample]) {
        async let health = api.deviceHealth(deviceId)
        async let metrics = api.latestMetrics(deviceId)
        return try await (health, metrics)
    }

    func loadOperations(deviceId: String) async {
        do {
            operationsByDevice[deviceId] = try await api.remoteOperations(deviceId: deviceId)
        } catch {
            self.error = error.localizedDescription
        }
    }

    func queueOperation(
        deviceId: String,
        operationType: String,
        hostname: String? = nil
    ) async {
        guard session?.user.role != "viewer" else {
            self.error = "Viewer role cannot queue operations"
            return
        }
        loading = true
        defer { loading = false }
        do {
            _ = try await api.queueRemoteOperation(
                deviceId: deviceId,
                operationType: operationType,
                hostname: hostname
            )
            operationsByDevice[deviceId] = try await api.remoteOperations(deviceId: deviceId)
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func enablePushNotifications() async {
        do {
            let granted = try await UNUserNotificationCenter.current().requestAuthorization(
                options: [.alert, .badge, .sound]
            )
            guard granted else { return }
            UIApplication.shared.registerForRemoteNotifications()
            if let token = store.pushToken() {
                try await api.registerPushToken(
                    provider: "apns",
                    environment: DeviceMeshAppDelegate.apnsEnvironment,
                    installationId: store.installationId,
                    token: token
                )
            }
        } catch {
            // Push is optional. Keep the operator app usable when notification permission
            // is denied or APNs registration is temporarily unavailable.
        }
    }

    var serverURL: URL { store.server }

    func createHardwareEnrollmentToken() async throws -> String {
        guard session?.user.role == "administrator" else {
            throw DeviceMeshAPIError.server(
                403,
                "Administrator role is required to provision hardware"
            )
        }
        return try await api.createAgentEnrollmentToken(ttlSeconds: 900)
    }

    func logout() async {
        try? await api.unregisterPushToken(installationId: store.installationId)
        await api.logout()
        UIApplication.shared.unregisterForRemoteNotifications()
        store.clear()
        session = nil
        devices = []
        incidents = []
        alerts = []
        monitors = []
        probes = []
    }
}
