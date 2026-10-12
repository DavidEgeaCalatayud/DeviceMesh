import SwiftUI

struct RootView: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        if model.session == nil {
            LoginView()
        } else {
            OperatorTabs()
        }
    }
}

private struct LoginView: View {
    @EnvironmentObject private var model: AppModel
    @State private var server = "https://mesh.example.com"
    @State private var username = ""
    @State private var password = ""
    @State private var mfaCode = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("Server") {
                    TextField("https://mesh.example.com", text: $server)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                }
                Section("Credentials") {
                    TextField("Username", text: $username)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    SecureField("Password", text: $password)
                    SecureField("MFA possession factor (if enabled)", text: $mfaCode)
                }
                if let error = model.error {
                    Text(error).foregroundStyle(.red)
                }
                Button(model.loading ? "Signing in…" : "Sign in") {
                    Task {
                        await model.login(
                            server: server,
                            username: username,
                            password: password,
                            mfaCode: mfaCode
                        )
                    }
                }
                .disabled(model.loading || username.isEmpty || password.isEmpty)
            }
            .navigationTitle("DeviceMesh")
        }
    }
}

private struct OperatorTabs: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        TabView {
            DashboardView()
                .tabItem { Label("Dashboard", systemImage: "gauge.with.dots.needle.67percent") }
            DeviceListView()
                .tabItem { Label("Devices", systemImage: "desktopcomputer") }
            IncidentListView()
                .tabItem { Label("Incidents", systemImage: "exclamationmark.triangle") }
            AlertListView()
                .tabItem { Label("Alerts", systemImage: "bell") }
            SyntheticListView()
                .tabItem { Label("Synthetics", systemImage: "waveform.path.ecg") }
            HardwareProvisioningView()
                .tabItem { Label("Provision", systemImage: "antenna.radiowaves.left.and.right") }
        }
    }
}

struct DashboardView: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        NavigationStack {
            List {
                Section("Fleet") {
                    metric("Online devices", value: String(model.devices.filter { $0.status == "online" }.count) + " / " + String(model.devices.count))
                    metric("Open incidents", value: String(model.incidents.filter { $0.status != "resolved" }.count))
                    metric("Active alerts", value: String(model.alerts.filter { $0.closedAt == nil }.count))
                }
                Section("Synthetic monitoring") {
                    metric("Monitors", value: String(model.monitors.count))
                    metric("Online probes", value: String(model.probes.filter(\.online).count) + " / " + String(model.probes.count))
                }
            }
            .navigationTitle("DeviceMesh")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Refresh") { Task { await model.refreshAll() } }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Sign out") { Task { await model.logout() } }
                }
            }
            .refreshable { await model.refreshAll() }
        }
    }

    private func metric(_ name: String, value: String) -> some View {
        HStack { Text(name); Spacer(); Text(value).fontWeight(.semibold) }
    }
}

private struct DeviceListView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        NavigationStack {
            List(model.devices) { device in
                VStack(alignment: .leading) {
                    Text(device.hostname ?? device.id).font(.headline)
                    Text(device.status + " · " + device.ipAddresses.joined(separator: ", "))
                        .font(.caption).foregroundStyle(.secondary)
                }
            }.navigationTitle("Devices")
        }
    }
}

private struct IncidentListView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        NavigationStack {
            List(model.incidents) { incident in
                VStack(alignment: .leading) {
                    Text((incident.severity ?? "SEV") + " · " + (incident.title ?? incident.id))
                    Text(incident.status ?? "unknown").font(.caption).foregroundStyle(.secondary)
                }
            }.navigationTitle("Incidents")
        }
    }
}

private struct AlertListView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        NavigationStack {
            List(model.alerts) { alert in
                VStack(alignment: .leading) {
                    Text(alert.deviceId)
                    Text(alert.closedAt == nil ? "Active" : "Recovered")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }.navigationTitle("Alerts")
        }
    }
}

private struct SyntheticListView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        NavigationStack {
            List {
                Section("Monitors") {
                    ForEach(model.monitors) { monitor in
                        VStack(alignment: .leading) {
                            Text(monitor.name)
                            Text(monitor.kind + " · " + monitor.target)
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
                Section("Distributed probes") {
                    ForEach(model.probes) { probe in
                        Text(probe.name + " · " + probe.location + " · " + (probe.online ? "online" : "offline"))
                    }
                }
            }.navigationTitle("Synthetics")
        }
    }
}


private struct HardwareProvisioningView: View {
    @EnvironmentObject private var model: AppModel
    @StateObject private var provisioning = DeviceMeshProvisioningModel()
    @State private var selectedDeviceName = ""
    @State private var proof = ""
    @State private var ssid = ""
    @State private var passphrase = ""

    var body: some View {
        NavigationStack {
            Form {
                if model.session?.user.role != "administrator" {
                    Section {
                        Text("Administrator role is required to provision hardware.")
                            .foregroundStyle(.red)
                    }
                } else {
                    Section("DeviceMesh ESP32") {
                        Button("Scan BLE") { provisioning.scan() }
                            .disabled(provisioning.busy)
                        ForEach(provisioning.devices, id: \.name) { device in
                            Button {
                                selectedDeviceName = device.name
                            } label: {
                                HStack {
                                    Text(device.name)
                                    Spacer()
                                    if selectedDeviceName == device.name {
                                        Image(systemName: "checkmark")
                                    }
                                }
                            }
                        }
                    }
                    Section("Secure provisioning") {
                        SecureField("Proof of possession", text: $proof)
                        TextField("Wi-Fi SSID", text: $ssid)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                        SecureField("Wi-Fi password", text: $passphrase)
                        Text(model.serverURL.absoluteString)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Section {
                        Button(provisioning.busy ? "Provisioning…" : "Provision") {
                            guard let device = provisioning.devices.first(
                                where: { $0.name == selectedDeviceName }
                            ) else { return }
                            Task {
                                do {
                                    let token = try await model.createHardwareEnrollmentToken()
                                    await provisioning.provision(
                                        device: device,
                                        proofOfPossession: proof,
                                        serverURL: model.serverURL,
                                        enrollmentToken: token,
                                        ssid: ssid,
                                        passphrase: passphrase
                                    )
                                    if provisioning.status.hasPrefix("Provisioning complete") {
                                        passphrase = ""
                                    }
                                } catch {
                                    provisioning.status = error.localizedDescription
                                }
                            }
                        }
                        .disabled(
                            provisioning.busy ||
                            selectedDeviceName.isEmpty ||
                            proof.isEmpty ||
                            ssid.isEmpty
                        )
                    }
                }
                if !provisioning.status.isEmpty {
                    Section("Status") { Text(provisioning.status) }
                }
            }
            .navigationTitle("Provision hardware")
        }
    }
}
