package io.github.davidegeacalatayud.devicemesh

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.le.ScanResult
import android.content.Context
import androidx.annotation.RequiresPermission
import com.espressif.provisioning.DeviceConnectionEvent
import com.espressif.provisioning.ESPConstants
import com.espressif.provisioning.ESPDevice
import com.espressif.provisioning.ESPProvisionManager
import com.espressif.provisioning.listeners.BleScanListener
import com.espressif.provisioning.listeners.ProvisionListener
import com.espressif.provisioning.listeners.ResponseListener
import java.nio.charset.StandardCharsets
import kotlinx.coroutines.suspendCancellableCoroutine
import org.greenrobot.eventbus.EventBus
import org.greenrobot.eventbus.Subscribe
import org.greenrobot.eventbus.ThreadMode
import org.json.JSONObject
import kotlin.coroutines.Continuation
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

data class ProvisioningDevice(
    val name: String,
    val address: String,
    val serviceUuid: String,
    internal val bluetoothDevice: BluetoothDevice,
)

class DeviceMeshBleProvisioner(context: Context) {
    private val manager = ESPProvisionManager.getInstance(context.applicationContext)
    private var activeDevice: ESPDevice? = null
    private var connectionContinuation: Continuation<Unit>? = null

    @SuppressLint("MissingPermission")
    fun scan(
        onDevice: (ProvisioningDevice) -> Unit,
        onComplete: () -> Unit,
        onFailure: (Throwable) -> Unit,
    ) {
        manager.searchBleEspDevices("DM-", object : BleScanListener {
            override fun scanStartFailed() {
                onFailure(IllegalStateException("Bluetooth scan could not start"))
            }

            override fun onPeripheralFound(device: BluetoothDevice, scanResult: ScanResult) {
                val serviceUuid = scanResult.scanRecord
                    ?.serviceUuids
                    ?.firstOrNull()
                    ?.uuid
                    ?.toString()
                    ?: return
                onDevice(
                    ProvisioningDevice(
                        name = device.name ?: "DeviceMesh",
                        address = device.address,
                        serviceUuid = serviceUuid,
                        bluetoothDevice = device,
                    ),
                )
            }

            override fun scanCompleted() = onComplete()
            override fun onFailure(e: Exception) = onFailure(e)
        })
    }

    @SuppressLint("MissingPermission")
    fun stopScan() {
        manager.stopBleScan()
    }

    @SuppressLint("MissingPermission")
    suspend fun provision(
        device: ProvisioningDevice,
        proofOfPossession: String,
        serverUrl: String,
        enrollmentToken: String,
        ssid: String,
        passphrase: String,
    ) {
        require(serverUrl.startsWith("https://")) { "Hardware provisioning requires HTTPS" }
        require(proofOfPossession.length >= 8) { "Proof of possession is too short" }
        require(enrollmentToken.length >= 20) { "Enrollment token is invalid" }
        require(ssid.isNotBlank()) { "Wi-Fi SSID is required" }

        stopScan()
        val espDevice = manager.createESPDevice(
            ESPConstants.TransportType.TRANSPORT_BLE,
            ESPConstants.SecurityType.SECURITY_1,
        )
        espDevice.setProofOfPossession(proofOfPossession)
        activeDevice = espDevice
        EventBus.getDefault().register(this)
        try {
            awaitConnection(espDevice, device)
            sendDeviceMeshConfig(espDevice, serverUrl, enrollmentToken)
            provisionWifi(espDevice, ssid, passphrase)
        } finally {
            if (EventBus.getDefault().isRegistered(this)) {
                EventBus.getDefault().unregister(this)
            }
            espDevice.disconnectDevice()
            activeDevice = null
            connectionContinuation = null
        }
    }

    @SuppressLint("MissingPermission")
    private suspend fun awaitConnection(
        espDevice: ESPDevice,
        device: ProvisioningDevice,
    ) = suspendCancellableCoroutine<Unit> { continuation ->
        connectionContinuation = continuation
        continuation.invokeOnCancellation {
            connectionContinuation = null
            runCatching { espDevice.disconnectDevice() }
        }
        espDevice.connectBLEDevice(device.bluetoothDevice, device.serviceUuid)
    }

    @Subscribe(threadMode = ThreadMode.MAIN)
    fun onDeviceConnectionEvent(event: DeviceConnectionEvent) {
        val continuation = connectionContinuation ?: return
        when (event.eventType) {
            ESPConstants.EVENT_DEVICE_CONNECTED -> {
                connectionContinuation = null
                continuation.resume(Unit)
            }
            ESPConstants.EVENT_DEVICE_CONNECTION_FAILED,
            ESPConstants.EVENT_DEVICE_DISCONNECTED,
            -> {
                connectionContinuation = null
                continuation.resumeWithException(
                    IllegalStateException("Unable to establish secure BLE provisioning session"),
                )
            }
        }
    }

    private suspend fun sendDeviceMeshConfig(
        espDevice: ESPDevice,
        serverUrl: String,
        enrollmentToken: String,
    ) = suspendCancellableCoroutine<Unit> { continuation ->
        val payload = JSONObject()
            .put("serverUrl", serverUrl.trimEnd('/'))
            .put("enrollmentToken", enrollmentToken)
            .toString()
            .toByteArray(StandardCharsets.UTF_8)
        espDevice.sendDataToCustomEndPoint(
            "devicemesh-config",
            payload,
            object : ResponseListener {
                override fun onSuccess(returnData: ByteArray) {
                    val response = runCatching {
                        JSONObject(String(returnData, StandardCharsets.UTF_8))
                    }.getOrNull()
                    if (response?.optString("status") == "ok") {
                        continuation.resume(Unit)
                    } else {
                        continuation.resumeWithException(
                            IllegalStateException("Device rejected DeviceMesh configuration"),
                        )
                    }
                }

                override fun onFailure(e: Exception) {
                    continuation.resumeWithException(e)
                }
            },
        )
    }

    private suspend fun provisionWifi(
        espDevice: ESPDevice,
        ssid: String,
        passphrase: String,
    ) = suspendCancellableCoroutine<Unit> { continuation ->
        var completed = false
        fun fail(error: Throwable) {
            if (!completed) {
                completed = true
                continuation.resumeWithException(error)
            }
        }
        espDevice.provision(ssid, passphrase, object : ProvisionListener {
            override fun createSessionFailed(e: Exception) = fail(e)
            override fun wifiConfigSent() = Unit
            override fun wifiConfigFailed(e: Exception) = fail(e)
            override fun wifiConfigApplied() = Unit
            override fun wifiConfigApplyFailed(e: Exception) = fail(e)
            override fun provisioningFailedFromDevice(
                failureReason: ESPConstants.ProvisionFailureReason,
            ) = fail(IllegalStateException("Device provisioning failed: $failureReason"))

            override fun deviceProvisioningSuccess() {
                if (!completed) {
                    completed = true
                    continuation.resume(Unit)
                }
            }

            override fun onProvisioningFailed(e: Exception) = fail(e)
        })
    }

    companion object {
        val runtimePermissions: Array<String> = arrayOf(
            Manifest.permission.BLUETOOTH_SCAN,
            Manifest.permission.BLUETOOTH_CONNECT,
        )
    }
}
