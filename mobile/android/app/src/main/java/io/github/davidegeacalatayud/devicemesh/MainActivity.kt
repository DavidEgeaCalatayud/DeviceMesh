package io.github.davidegeacalatayud.devicemesh

import android.Manifest
import android.content.pm.PackageManager
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import io.github.davidegeacalatayud.devicemesh.core.designsystem.DeviceMeshTheme
import io.github.davidegeacalatayud.devicemesh.core.model.DeviceStatus

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
}

@Composable
private fun DeviceMeshApp(model: DeviceMeshViewModel = viewModel()) {
    val state = model.state
    if (state.session == null) {
        LoginScreen(state.server, state.loading, state.error, model::login)
        return
    }
    PushNotificationPermission()
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
                Tab.DEVICES -> Devices(state, model)
                Tab.INCIDENTS -> Incidents(state)
                Tab.ALERTS -> Alerts(state)
                Tab.SYNTHETICS -> Synthetics(state)
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
private fun Devices(state: MobileState, model: DeviceMeshViewModel) {
    var selectedDeviceId by rememberSaveable { mutableStateOf<String?>(null) }
    LazyColumn(Modifier.padding(16.dp)) {
        item { Text("Devices", style = MaterialTheme.typography.headlineSmall) }
        items(state.devices, key = { it.id }) { device ->
            val selected = selectedDeviceId == device.id
            Column(Modifier.fillMaxWidth().padding(vertical = 10.dp)) {
                TextButton(
                    onClick = {
                        selectedDeviceId = if (selected) null else device.id
                        if (!selected) model.loadDeviceDetails(device.id)
                    },
                ) {
                    Column(Modifier.fillMaxWidth()) {
                        Text(
                            device.hostname ?: device.id,
                            style = MaterialTheme.typography.titleMedium,
                        )
                        val ipText = device.ipAddresses.joinToString().ifBlank { "No IP" }
                        Text(device.status.name.lowercase() + " · " + ipText)
                        device.operatingSystem?.let {
                            Text(it, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
                if (selected) {
                    val health = state.deviceHealth[device.id]
                    val metrics = state.deviceMetrics[device.id].orEmpty()
                    HorizontalDivider()
                    Text("Operational health", style = MaterialTheme.typography.titleSmall)
                    if (health == null) {
                        Text("Loading…")
                    } else {
                        Text("State: " + (health.currentState ?: "unknown"))
                        health.availability24h?.let {
                            Text("Availability 24h: " + String.format("%.3f%%", it))
                        }
                        health.currentOutageSeconds?.let {
                            Text("Current outage: " + it.toLong() + " s")
                        }
                        if (health.maintenanceActive) Text("Maintenance active")
                    }
                    if (metrics.isNotEmpty()) {
                        Text(
                            "Latest metrics",
                            style = MaterialTheme.typography.titleSmall,
                            modifier = Modifier.padding(top = 8.dp),
                        )
                        metrics.take(8).forEach { metric ->
                            Text(
                                metric.name + ": " + metric.value +
                                    (metric.unit?.let { " " + it } ?: ""),
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                    if (state.session?.user?.role != "viewer") {
                        Text(
                            "Safe operations",
                            style = MaterialTheme.typography.titleSmall,
                            modifier = Modifier.padding(top = 8.dp),
                        )
                        Row {
                            TextButton(
                                onClick = {
                                    model.queueDeviceOperation(device.id, "telemetry.collect")
                                },
                            ) { Text("Collect") }
                            TextButton(
                                onClick = {
                                    model.queueDeviceOperation(device.id, "inventory.refresh")
                                },
                            ) { Text("Inventory") }
                            TextButton(
                                onClick = {
                                    model.queueDeviceOperation(device.id, "agent.health_check")
                                },
                            ) { Text("Health") }
                        }
                        state.operationMessage?.let {
                            Text(it, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
            HorizontalDivider()
        }
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
private fun PushNotificationPermission() {
    if (Build.VERSION.SDK_INT < 33) return
    val context = LocalContext.current
    val launcher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { }
    LaunchedEffect(Unit) {
        if (
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            launcher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }
}
