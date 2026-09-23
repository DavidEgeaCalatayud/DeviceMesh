package io.github.davidegeacalatayud.devicemesh.core.model

data class Device(val id: String, val hostname: String?, val status: DeviceStatus, val ipAddresses: List<String>)
enum class DeviceStatus { ONLINE, OFFLINE, UNKNOWN }
