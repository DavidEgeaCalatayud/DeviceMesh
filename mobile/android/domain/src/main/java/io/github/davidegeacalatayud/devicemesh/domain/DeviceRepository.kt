package io.github.davidegeacalatayud.devicemesh.domain

import io.github.davidegeacalatayud.devicemesh.core.model.Device

interface DeviceRepository { suspend fun devices(): List<Device> }
