package io.github.davidegeacalatayud.devicemesh.core.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class DeviceMeshApiTest {
    @Test
    fun serverUrlRequiresHttpsAndRejectsEmbeddedCredentials() {
        assertEquals("https://mesh.example.com", validateBaseUrl(" https://mesh.example.com/ "))
        assertThrows(IllegalArgumentException::class.java) {
            validateBaseUrl("http://mesh.example.com")
        }
        assertThrows(IllegalArgumentException::class.java) {
            validateBaseUrl("https://user:password@mesh.example.com")
        }
    }

    @Test
    fun remoteOperationsAreStrictlyAllowlisted() {
        validateRemoteOperationType("telemetry.collect")
        validateRemoteOperationType("network.route_snapshot")
        assertThrows(IllegalArgumentException::class.java) {
            validateRemoteOperationType("shell")
        }
        assertThrows(IllegalArgumentException::class.java) {
            validateRemoteOperationType("powershell.exec")
        }
    }
}
