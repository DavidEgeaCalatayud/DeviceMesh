package io.github.davidegeacalatayud.devicemesh.data

import io.github.davidegeacalatayud.devicemesh.core.model.Device
import io.github.davidegeacalatayud.devicemesh.domain.DeviceRepository

class RemoteDeviceRepository : DeviceRepository { override suspend fun devices(): List<Device> = emptyList() }
