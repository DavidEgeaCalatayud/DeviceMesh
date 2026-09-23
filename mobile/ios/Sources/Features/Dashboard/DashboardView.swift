import SwiftUI

struct DashboardView: View {
    var body: some View {
        NavigationStack {
            List {
                Section("Fleet") { Label("Device inventory", systemImage: "network") }
                Section("Status") { Text("Connect to a DeviceMesh server to begin.") }
            }
            .navigationTitle("DeviceMesh")
        }
    }
}
