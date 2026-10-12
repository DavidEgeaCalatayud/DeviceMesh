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
                NavigationLink {
                    DeviceDetailView(device: device)
                } label: {
                    VStack(alignment: .leading) {
                        Text(device.hostname ?? device.id).font(.headline)
                        Text(device.status + " · " + device.ipAddresses.joined(separator: ", "))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("Devices")
        }
    }
}

private struct DeviceDetailView: View {
    @EnvironmentObject private var model: AppModel
    let device: Device
    @State private var health: DeviceHealth?
    @State private var metrics: [MetricSample] = []
    @State private var dnsHost = ""
    @State private var loading = true

    var body: some View {
        List {
            Section("Device") {
                LabeledContent("Status", value: device.status)
                LabeledContent("IP", value: device.ipAddresses.joined(separator: ", "))
                LabeledContent("OS", value: device.operatingSystem ?? "—")
                LabeledContent("Manufacturer", value: device.manufacturer ?? "—")
                LabeledContent("Last seen", value: device.lastSeen ?? "—")
            }
            Section("Operational health") {
                if let health {
                    LabeledContent("State", value: health.currentState ?? "unknown")
                    if let availability = health.availability24h {
                        LabeledContent(
                            "Availability 24h",
                            value: String(format: "%.3f%%", availability)
                        )
                    }
                    if let outage = health.currentOutageSeconds {
                        LabeledContent("Current outage", value: String(Int(outage)) + " s")
                    }
                    if health.maintenanceActive {
                        Label("Maintenance active", systemImage: "wrench.and.screwdriver")
                    }
                } else if loading {
                    ProgressView()
                } else {
                    Text("Health data unavailable")
                }
            }
            if !metrics.isEmpty {
                Section("Latest metrics") {
                    ForEach(metrics.prefix(12)) { metric in
                        LabeledContent(
                            metric.name,
                            value: String(metric.value) + (metric.unit.map { " " + $0 } ?? "")
                        )
                    }
                }
            }
            if model.session?.user.role != "viewer" {
                Section("Safe operations") {
                    ForEach([
                        ("telemetry.collect", "Collect telemetry"),
                        ("inventory.refresh", "Refresh inventory"),
                        ("agent.health_check", "Agent health check"),
                        ("network.route_snapshot", "Route snapshot"),
                    ], id: \.0) { type, label in
                        Button(label) {
                            Task {
                                await model.queueOperation(
                                    deviceId: device.id,
                                    operationType: type
                                )
                            }
                        }
                    }
                    TextField("DNS hostname", text: $dnsHost)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Button("DNS lookup") {
                        Task {
                            await model.queueOperation(
                                deviceId: device.id,
                                operationType: "network.dns_lookup",
                                hostname: dnsHost
                            )
                        }
                    }
                    .disabled(
                        dnsHost.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                    )
                }
            }
            Section("Operation history") {
                ForEach(model.operationsByDevice[device.id] ?? []) { operation in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(operation.operationType).font(.headline)
                        Text(operation.status + " · " + operation.createdAt)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        if let error = operation.error {
                            Text(error).foregroundStyle(.red)
                        }
                        if !operation.result.isEmpty {
                            Text(
                                operation.result
                                    .sorted(by: { $0.key < $1.key })
                                    .map { $0.key + "=" + $0.value }
                                    .joined(separator: ", ")
                            )
                            .font(.caption2)
                        }
                    }
                }
            }
        }
        .navigationTitle(device.hostname ?? "Device")
        .task { await load() }
        .refreshable { await load() }
    }

    private func load() async {
        loading = true
        defer { loading = false }
        do {
            let detail = try await model.deviceDetail(device.id)
            health = detail.0
            metrics = detail.1
            await model.loadOperations(deviceId: device.id)
        } catch {
            model.error = error.localizedDescription
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
