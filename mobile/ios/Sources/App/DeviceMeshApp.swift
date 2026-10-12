import SwiftUI

@main
struct DeviceMeshApp: App {
    @UIApplicationDelegateAdaptor(DeviceMeshAppDelegate.self) private var appDelegate
    @StateObject private var model = AppModel()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(model)
        }
    }
}
