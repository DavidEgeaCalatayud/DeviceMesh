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
}
