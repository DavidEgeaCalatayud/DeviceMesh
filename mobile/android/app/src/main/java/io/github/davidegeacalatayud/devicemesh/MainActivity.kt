package io.github.davidegeacalatayud.devicemesh

import android.os.Build
import android.os.Bundle
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import io.github.davidegeacalatayud.devicemesh.core.designsystem.DeviceMeshTheme
import io.github.davidegeacalatayud.devicemesh.core.model.DeviceStatus
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            DeviceMeshTheme {
                Surface(Modifier.fillMaxSize()) { DeviceMeshApp() }
            }
        }
    }
}

private enum class Tab(val label: String) {
    DASHBOARD("Dashboard"),
    DEVICES("Devices"),
    INCIDENTS("Incidents"),
    ALERTS("Alerts"),
    SYNTHETICS("Synthetics"),
    PROVISION("Provision"),
}

@Composable
private fun DeviceMeshApp(model: DeviceMeshViewModel = viewModel()) {
    val state = model.state
    if (state.session == null) {
        LoginScreen(state.server, state.loading, state.error, model::login)
        return
    }
    var tabName by rememberSaveable { mutableStateOf(Tab.DASHBOARD.name) }
    val tab = Tab.valueOf(tabName)
    Scaffold(
        topBar = {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column {
                    Text("DeviceMesh", style = MaterialTheme.typography.titleLarge)
                    Text(
                        state.session.user.username + " · " + state.session.user.role,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                Row {
                    TextButton(onClick = model::refreshAll) { Text("Refresh") }
                    TextButton(onClick = model::logout) { Text("Sign out") }
                }
            }
        },
        bottomBar = {
            NavigationBar {
                Tab.entries.forEach { item ->
                    NavigationBarItem(
                        selected = item == tab,
                        onClick = { tabName = item.name },
                        icon = { Text(item.label.take(1)) },
                        label = { Text(item.label) },
                    )
                }
            }
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            if (state.loading) CircularProgressIndicator(Modifier.padding(16.dp))
            state.error?.let {
                Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(16.dp))
            }
            when (tab) {
                Tab.DASHBOARD -> Dashboard(state)
                Tab.DEVICES -> Devices(state)
                Tab.INCIDENTS -> Incidents(state)
                Tab.ALERTS -> Alerts(state)
                Tab.SYNTHETICS -> Synthetics(state)
                Tab.PROVISION -> ProvisionHardware(state, model)
            }
        }
    }
}

@Composable
private fun LoginScreen(
    initialServer: String,
    loading: Boolean,
    error: String?,
    onLogin: (String, String, String, String?) -> Unit,
) {
    var server by rememberSaveable { mutableStateOf(initialServer) }
    var username by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var mfa by rememberSaveable { mutableStateOf("") }
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("DeviceMesh", style = MaterialTheme.typography.headlineLarge)
        Text("Secure operator access", modifier = Modifier.padding(bottom = 16.dp))
        OutlinedTextField(
            server,
            { server = it },
            label = { Text("HTTPS server") },
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            username,
            { username = it },
            label = { Text("Username") },
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            password,
            { password = it },
            label = { Text("Password") },
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            mfa,
            { mfa = it },
            label = { Text("MFA possession factor (if enabled)") },
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
        )
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(
            onClick = { onLogin(server, username, password, mfa.ifBlank { null }) },
            enabled = !loading && username.isNotBlank() && password.isNotBlank(),
            modifier = Modifier.padding(top = 12.dp),
        ) { Text(if (loading) "Signing in…" else "Sign in") }
    }
}

@Composable
private fun Dashboard(state: MobileState) {
    val online = state.devices.count { it.status == DeviceStatus.ONLINE }
    val openIncidents = state.incidents.count { it.status != "resolved" }
    val activeAlerts = state.alerts.count { it.closedAt == null }
    LazyColumn(Modifier.padding(16.dp)) {
        item { Text("Operational summary", style = MaterialTheme.typography.headlineSmall) }
        item { Metric("Devices online", online.toString() + " / " + state.devices.size) }
        item { Metric("Open incidents", openIncidents.toString()) }
        item { Metric("Active alerts", activeAlerts.toString()) }
        item { Metric("Synthetic monitors", state.monitors.size.toString()) }
        item { Metric("Probes online", state.probes.count { it.online }.toString() + " / " + state.probes.size) }
    }
}

@Composable
private fun Metric(label: String, value: String) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 12.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label)
        Text(value, style = MaterialTheme.typography.titleMedium)
    }
    HorizontalDivider()
}

@Composable
private fun Devices(state: MobileState) = LazyColumn(Modifier.padding(16.dp)) {
    item { Text("Devices", style = MaterialTheme.typography.headlineSmall) }
    items(state.devices, key = { it.id }) { device ->
        Column(Modifier.fillMaxWidth().padding(vertical = 10.dp)) {
            Text(device.hostname ?: device.id, style = MaterialTheme.typography.titleMedium)
            val ipText = device.ipAddresses.joinToString().ifBlank { "No IP" }
            Text(device.status.name.lowercase() + " · " + ipText)
            device.operatingSystem?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
        }
        HorizontalDivider()
    }
}

@Composable
private fun Incidents(state: MobileState) = LazyColumn(Modifier.padding(16.dp)) {
    item { Text("Incidents", style = MaterialTheme.typography.headlineSmall) }
    items(state.incidents, key = { it.id }) { incident ->
        Column(Modifier.fillMaxWidth().padding(vertical = 10.dp)) {
            Text(incident.severity + " · " + incident.title, style = MaterialTheme.typography.titleMedium)
            Text(incident.status + (incident.assignedTo?.let { " · " + it } ?: ""))
        }
        HorizontalDivider()
    }
}

@Composable
private fun Alerts(state: MobileState) = LazyColumn(Modifier.padding(16.dp)) {
    item { Text("Alerts", style = MaterialTheme.typography.headlineSmall) }
    items(state.alerts, key = { it.id }) { alert ->
        Column(Modifier.fillMaxWidth().padding(vertical = 10.dp)) {
            Text(alert.deviceId, style = MaterialTheme.typography.titleMedium)
            Text(if (alert.closedAt == null) "Active" else "Recovered")
        }
        HorizontalDivider()
    }
}

@Composable
private fun Synthetics(state: MobileState) = LazyColumn(Modifier.padding(16.dp)) {
    item { Text("Synthetics", style = MaterialTheme.typography.headlineSmall) }
    items(state.monitors, key = { it.id }) { monitor ->
        Column(Modifier.fillMaxWidth().padding(vertical = 10.dp)) {
            Text(monitor.name, style = MaterialTheme.typography.titleMedium)
            Text(
                monitor.kind + " · " + monitor.target + " · " +
                    if (monitor.enabled) "enabled" else "disabled",
            )
        }
        HorizontalDivider()
    }
    item {
        Text(
            "Distributed probes",
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(top = 20.dp),
        )
    }
    items(state.probes, key = { it.id }) { probe ->
        Text(
            probe.name + " · " + probe.location + " · " + if (probe.online) "online" else "offline",
            modifier = Modifier.padding(vertical = 8.dp),
        )
    }
}


@Composable
private fun ProvisionHardware(state: MobileState, model: DeviceMeshViewModel) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val provisioner = remember { DeviceMeshBleProvisioner(context) }
    val devices = remember { mutableStateListOf<ProvisioningDevice>() }
    var selectedAddress by rememberSaveable { mutableStateOf<String?>(null) }
    var proof by rememberSaveable { mutableStateOf("") }
    var ssid by rememberSaveable { mutableStateOf("") }
    var wifiPassword by rememberSaveable { mutableStateOf("") }
    var status by rememberSaveable { mutableStateOf("") }
    var working by rememberSaveable { mutableStateOf(false) }

    fun startScan() {
        devices.clear()
        selectedAddress = null
        status = "Scanning for DeviceMesh hardware…"
        provisioner.scan(
            onDevice = { found ->
                if (devices.none { it.address == found.address }) devices.add(found)
            },
            onComplete = { status = if (devices.isEmpty()) "No DM-* devices found" else "Select a device" },
            onFailure = { status = it.message ?: "Bluetooth scan failed" },
        )
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { grants ->
        if (grants.values.all { it }) startScan()
        else status = "Bluetooth permission is required for provisioning"
    }

    LazyColumn(Modifier.padding(16.dp)) {
        item {
            Text("Provision DeviceMesh hardware", style = MaterialTheme.typography.headlineSmall)
            Text(
                "Creates a one-use 15 minute enrollment token and sends it with the HTTPS server " +
                    "inside the encrypted ESP-IDF BLE provisioning session.",
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(vertical = 8.dp),
            )
        }
        if (state.session?.user?.role != "administrator") {
            item {
                Text(
                    "Administrator role is required.",
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(vertical = 8.dp),
                )
            }
            return@LazyColumn
        }
        item {
            Button(
                enabled = !working,
                onClick = {
                    if (Build.VERSION.SDK_INT >= 31) {
                        permissionLauncher.launch(DeviceMeshBleProvisioner.runtimePermissions)
                    } else {
                        startScan()
                    }
                },
            ) { Text("Scan BLE") }
        }
        items(devices, key = { it.address }) { device ->
            TextButton(onClick = { selectedAddress = device.address }) {
                Text((if (selectedAddress == device.address) "✓ " else "") + device.name)
            }
        }
        item {
            OutlinedTextField(
                value = proof,
                onValueChange = { proof = it },
                label = { Text("Proof of possession") },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = ssid,
                onValueChange = { ssid = it },
                label = { Text("Wi-Fi SSID") },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = wifiPassword,
                onValueChange = { wifiPassword = it },
                label = { Text("Wi-Fi password") },
                visualTransformation = PasswordVisualTransformation(),
                modifier = Modifier.fillMaxWidth(),
            )
            Button(
                enabled = !working &&
                    selectedAddress != null &&
                    proof.isNotBlank() &&
                    ssid.isNotBlank(),
                onClick = {
                    val selected = devices.firstOrNull { it.address == selectedAddress }
                        ?: return@Button
                    scope.launch {
                        working = true
                        status = "Creating enrollment token…"
                        try {
                            val token = model.createHardwareEnrollmentToken()
                            status = "Provisioning secure BLE session…"
                            provisioner.provision(
                                device = selected,
                                proofOfPossession = proof.trim(),
                                serverUrl = state.server,
                                enrollmentToken = token,
                                ssid = ssid,
                                passphrase = wifiPassword,
                            )
                            status = "Provisioning complete. Device will enroll automatically."
                            wifiPassword = ""
                        } catch (error: Exception) {
                            status = error.message ?: "Provisioning failed"
                        } finally {
                            working = false
                        }
                    }
                },
                modifier = Modifier.padding(top = 12.dp),
            ) { Text(if (working) "Provisioning…" else "Provision") }
            if (status.isNotBlank()) {
                Text(status, modifier = Modifier.padding(top = 12.dp))
            }
        }
    }
}
