package io.github.davidegeacalatayud.devicemesh

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import io.github.davidegeacalatayud.devicemesh.core.model.Alert
import io.github.davidegeacalatayud.devicemesh.core.model.Device
import io.github.davidegeacalatayud.devicemesh.core.model.DeviceHealth
import io.github.davidegeacalatayud.devicemesh.core.model.Incident
import io.github.davidegeacalatayud.devicemesh.core.model.MetricSample
import io.github.davidegeacalatayud.devicemesh.core.model.SessionTokens
import io.github.davidegeacalatayud.devicemesh.core.model.SyntheticMonitor
import io.github.davidegeacalatayud.devicemesh.core.model.SyntheticProbe
import io.github.davidegeacalatayud.devicemesh.core.network.ApiException
import io.github.davidegeacalatayud.devicemesh.core.network.HttpDeviceMeshApi
import io.github.davidegeacalatayud.devicemesh.core.network.validateBaseUrl
import kotlinx.coroutines.async
import kotlinx.coroutines.launch

data class MobileState(
    val server: String,
    val session: SessionTokens? = null,
    val loading: Boolean = false,
    val error: String? = null,
    val devices: List<Device> = emptyList(),
    val incidents: List<Incident> = emptyList(),
    val alerts: List<Alert> = emptyList(),
    val monitors: List<SyntheticMonitor> = emptyList(),
    val probes: List<SyntheticProbe> = emptyList(),
    val deviceHealth: Map<String, DeviceHealth> = emptyMap(),
    val deviceMetrics: Map<String, List<MetricSample>> = emptyMap(),
    val operationMessage: String? = null,
)

class DeviceMeshViewModel(application: Application) : AndroidViewModel(application) {
    private val store = SecureSessionStore(application)
    var state by mutableStateOf(MobileState(server = store.server(), session = store.load()))
        private set
    private var api = HttpDeviceMeshApi(store.server()) { state.session?.accessToken }

    init {
        if (state.session != null) refreshAll()
    }

    fun login(server: String, username: String, password: String, mfaCode: String?) {
        viewModelScope.launch {
            state = state.copy(loading = true, error = null)
            try {
                val normalized = validateBaseUrl(server)
                store.saveServer(normalized)
                api = HttpDeviceMeshApi(normalized) { state.session?.accessToken }
                val session = api.login(username, password, mfaCode)
                store.save(session)
                state = state.copy(server = normalized, session = session, loading = false)
                syncPushRegistration()
                refreshAll()
            } catch (error: Exception) {
                state = state.copy(loading = false, error = error.message ?: "Login failed")
            }
        }
    }

    fun refreshAll() {
        val current = state.session ?: return
        viewModelScope.launch {
            state = state.copy(loading = true, error = null)
            try {
                loadData()
                syncPushRegistration()
            } catch (error: ApiException) {
                if (error.statusCode == 401) {
                    try {
                        val refreshed = api.refresh(current.refreshToken)
                        store.save(refreshed)
                        state = state.copy(session = refreshed)
                        syncPushRegistration()
                        loadData()
                        syncPushRegistration()
                    } catch (refreshError: Exception) {
                        store.clear()
                        state = MobileState(
                            server = store.server(),
                            error = refreshError.message ?: "Session expired",
                        )
                    }
                } else {
                    state = state.copy(error = error.message)
                }
            } catch (error: Exception) {
                state = state.copy(error = error.message ?: "Unable to load DeviceMesh")
            } finally {
                state = state.copy(loading = false)
            }
        }
    }

    fun loadDeviceDetails(deviceId: String) {
        viewModelScope.launch {
            try {
                val health = async { api.deviceHealth(deviceId) }
                val metrics = async { api.latestMetrics(deviceId) }
                state = state.copy(
                    deviceHealth = state.deviceHealth + (deviceId to health.await()),
                    deviceMetrics = state.deviceMetrics + (deviceId to metrics.await()),
                    operationMessage = null,
                )
            } catch (error: Exception) {
                state = state.copy(error = error.message ?: "Unable to load device detail")
            }
        }
    }

    fun queueDeviceOperation(deviceId: String, operationType: String) {
        val role = state.session?.user?.role ?: return
        if (role == "viewer") {
            state = state.copy(operationMessage = "Viewer role cannot queue operations")
            return
        }
        viewModelScope.launch {
            try {
                val operation = api.queueRemoteOperation(deviceId, operationType)
                state = state.copy(
                    operationMessage = operation.operationType + " · " + operation.status,
                )
            } catch (error: Exception) {
                state = state.copy(
                    operationMessage = error.message ?: "Unable to queue operation",
                )
            }
        }
    }

    private suspend fun loadData() {
        val devices = viewModelScope.async { api.devices() }
        val incidents = viewModelScope.async { api.incidents() }
        val alerts = viewModelScope.async { api.alerts() }
        val monitors = viewModelScope.async { api.syntheticMonitors() }
        val probes = viewModelScope.async {
            runCatching { api.syntheticProbes() }.getOrDefault(emptyList())
        }
        state = state.copy(
            devices = devices.await(),
            incidents = incidents.await(),
            alerts = alerts.await(),
            monitors = monitors.await(),
            probes = probes.await(),
        )
    }

    private fun syncPushRegistration() {
        if (state.session == null) return
        if (FirebaseApp.getApps(getApplication()).isEmpty()) return

        fun register(token: String) {
            if (token.isBlank()) return
            store.savePushToken(token)
            viewModelScope.launch {
                runCatching {
                    api.registerPushToken(
                        provider = "fcm",
                        environment = "production",
                        installationId = store.installationId(),
                        token = token,
                    )
                }
            }
        }

        store.pushToken()?.let(::register)
        runCatching { FirebaseMessaging.getInstance() }
            .getOrNull()
            ?.token
            ?.addOnSuccessListener(::register)
    }

    fun logout() {
        viewModelScope.launch {
            runCatching { api.unregisterPushToken(store.installationId()) }
            runCatching { api.logout() }
            if (FirebaseApp.getApps(getApplication()).isNotEmpty()) {
                runCatching { FirebaseMessaging.getInstance().deleteToken() }
            }
            store.clear()
            state = MobileState(server = store.server())
        }
    }
}
