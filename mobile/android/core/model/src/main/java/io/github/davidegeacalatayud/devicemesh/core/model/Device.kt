package io.github.davidegeacalatayud.devicemesh.core.model

data class Device(
    val id: String,
    val hostname: String?,
    val status: DeviceStatus,
    val ipAddresses: List<String>,
    val operatingSystem: String? = null,
    val manufacturer: String? = null,
    val lastSeen: String? = null,
)

enum class DeviceStatus { ONLINE, OFFLINE, UNKNOWN }

data class HumanUser(val id: String, val username: String, val role: String, val mfaEnabled: Boolean)
data class SessionTokens(val accessToken: String, val refreshToken: String, val expiresAt: String, val user: HumanUser)
data class Incident(val id: String, val title: String, val severity: String, val status: String, val assignedTo: String?)
data class Alert(val id: String, val deviceId: String, val openedAt: String?, val closedAt: String?)
data class SyntheticMonitor(val id: String, val name: String, val kind: String, val target: String, val enabled: Boolean)
data class SyntheticProbe(val id: String, val name: String, val location: String, val online: Boolean, val lastSeenAt: String?)


data class RemoteOperation(
    val id: String,
    val deviceId: String,
    val operationType: String,
    val status: String,
    val createdAt: String,
    val completedAt: String?,
    val result: Map<String, String>,
    val error: String?,
)
