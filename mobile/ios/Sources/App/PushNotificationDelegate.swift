import UIKit
import UserNotifications

final class DeviceMeshAppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        return true
    }

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        let store = SecureSessionStore()
        try? store.savePushToken(token)
        guard let session = store.load() else { return }
        Task {
            do {
                let api = try DeviceMeshAPI(
                    baseURL: store.server,
                    accessToken: session.accessToken
                )
                try await api.registerPushToken(
                    provider: "apns",
                    environment: Self.apnsEnvironment,
                    installationId: store.installationId,
                    token: token
                )
            } catch {
                // Registration is retried after the next login or session restoration.
            }
        }
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
#if DEBUG
        print("APNs registration unavailable: \(error.localizedDescription)")
#endif
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        [.banner, .list, .sound]
    }

    static var apnsEnvironment: String {
#if DEBUG
        "sandbox"
#else
        "production"
#endif
    }
}
