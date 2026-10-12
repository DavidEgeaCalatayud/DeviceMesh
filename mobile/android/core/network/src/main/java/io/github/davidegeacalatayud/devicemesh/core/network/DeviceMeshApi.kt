package io.github.davidegeacalatayud.devicemesh.core.network

import io.github.davidegeacalatayud.devicemesh.core.model.Alert
import io.github.davidegeacalatayud.devicemesh.core.model.Device
import io.github.davidegeacalatayud.devicemesh.core.model.DeviceStatus
import io.github.davidegeacalatayud.devicemesh.core.model.HumanUser
import io.github.davidegeacalatayud.devicemesh.core.model.Incident
import io.github.davidegeacalatayud.devicemesh.core.model.SessionTokens
import io.github.davidegeacalatayud.devicemesh.core.model.SyntheticMonitor
import io.github.davidegeacalatayud.devicemesh.core.model.SyntheticProbe
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

class ApiException(val statusCode: Int, message: String) : RuntimeException(message)

interface DeviceMeshApi {
    suspend fun health(): Boolean
    suspend fun login(username: String, password: String, mfaCode: String? = null): SessionTokens
    suspend fun refresh(refreshToken: String): SessionTokens
    suspend fun logout()
    suspend fun devices(): List<Device>
    suspend fun incidents(): List<Incident>
    suspend fun alerts(): List<Alert>
    suspend fun syntheticMonitors(): List<SyntheticMonitor>
    suspend fun syntheticProbes(): List<SyntheticProbe>
    suspend fun registerPushToken(
        provider: String,
        environment: String,
        installationId: String,
        token: String,
    )
    suspend fun unregisterPushToken(installationId: String)
}

fun validateBaseUrl(raw: String): String {
    val value = raw.trim().trimEnd('/')
    val uri = URI(value)
    require(uri.scheme == "https") { "DeviceMesh mobile requires HTTPS" }
    require(!uri.host.isNullOrBlank()) { "DeviceMesh server must include a hostname" }
    require(uri.userInfo == null) { "Credentials are not allowed in the server URL" }
    return value
}

class HttpDeviceMeshApi(
    server: String,
    private val accessToken: () -> String?,
) : DeviceMeshApi {
    private val baseUrl = validateBaseUrl(server)

    override suspend fun health(): Boolean = withContext(Dispatchers.IO) {
        runCatching { request("GET", "/health", authenticated = false).first in 200..299 }
            .getOrDefault(false)
    }

    override suspend fun login(
        username: String,
        password: String,
        mfaCode: String?,
    ): SessionTokens = withContext(Dispatchers.IO) {
        val body = JSONObject().put("username", username.trim()).put("password", password)
        if (!mfaCode.isNullOrBlank()) body.put("mfaCode", mfaCode.trim())
        parseSession(requestJson("POST", "/api/v1/auth/login", body, authenticated = false))
    }

    override suspend fun refresh(refreshToken: String): SessionTokens = withContext(Dispatchers.IO) {
        parseSession(
            requestJson(
                "POST",
                "/api/v1/auth/refresh",
                JSONObject().put("refreshToken", refreshToken),
                authenticated = false,
            ),
        )
    }

    override suspend fun logout() = withContext(Dispatchers.IO) {
        request("POST", "/api/v1/auth/logout")
        Unit
    }

    override suspend fun devices(): List<Device> = withContext(Dispatchers.IO) {
        val rows = requestArray("GET", "/api/v1/devices")
        buildList {
            for (index in 0 until rows.length()) {
                val row = rows.getJSONObject(index)
                val ips = row.optJSONArray("ipAddresses") ?: JSONArray()
                add(
                    Device(
                        id = row.getString("id"),
                        hostname = row.optNullableString("hostname"),
                        status = when (row.optString("status").lowercase()) {
                            "online" -> DeviceStatus.ONLINE
                            "offline" -> DeviceStatus.OFFLINE
                            else -> DeviceStatus.UNKNOWN
                        },
                        ipAddresses = buildList {
                            for (i in 0 until ips.length()) add(ips.getString(i))
                        },
                        operatingSystem = row.optNullableString("operatingSystem"),
                        manufacturer = row.optNullableString("manufacturer"),
                        lastSeen = row.optNullableString("lastSeen"),
                    ),
                )
            }
        }
    }

    override suspend fun incidents(): List<Incident> = withContext(Dispatchers.IO) {
        val rows = requestArray("GET", "/api/v1/incidents?limit=100&activeOnly=false")
        buildList {
            for (index in 0 until rows.length()) {
                val row = rows.getJSONObject(index)
                val id = row.getString("id")
                add(
                    Incident(
                        id = id,
                        title = row.optString("title").ifBlank { "Incident " + id.take(8) },
                        severity = row.optString("severity", "SEV2"),
                        status = row.optString("status", "open"),
                        assignedTo = row.optNullableString("assignedTo"),
                    ),
                )
            }
        }
    }

    override suspend fun alerts(): List<Alert> = withContext(Dispatchers.IO) {
        val rows = requestArray("GET", "/api/v1/alerts?activeOnly=false&limit=100")
        buildList {
            for (index in 0 until rows.length()) {
                val row = rows.getJSONObject(index)
                add(
                    Alert(
                        id = row.opt("id")?.toString() ?: "unknown",
                        deviceId = row.optString("deviceId", "unknown"),
                        openedAt = row.optNullableString("openedAt"),
                        closedAt = row.optNullableString("closedAt"),
                    ),
                )
            }
        }
    }

    override suspend fun syntheticMonitors(): List<SyntheticMonitor> = withContext(Dispatchers.IO) {
        val rows = requestArray("GET", "/api/v1/synthetic-monitors")
        buildList {
            for (index in 0 until rows.length()) {
                val row = rows.getJSONObject(index)
                add(
                    SyntheticMonitor(
                        id = row.getString("id"),
                        name = row.getString("name"),
                        kind = row.getString("kind"),
                        target = row.getString("target"),
                        enabled = row.optBoolean("enabled", true),
                    ),
                )
            }
        }
    }

    override suspend fun syntheticProbes(): List<SyntheticProbe> = withContext(Dispatchers.IO) {
        val rows = requestArray("GET", "/api/v1/operator/synthetic-probes")
        buildList {
            for (index in 0 until rows.length()) {
                val row = rows.getJSONObject(index)
                add(
                    SyntheticProbe(
                        id = row.getString("id"),
                        name = row.getString("name"),
                        location = row.optString("location"),
                        online = row.optBoolean("online"),
                        lastSeenAt = row.optNullableString("lastSeenAt"),
                    ),
                )
            }
        }
    }

    override suspend fun registerPushToken(
        provider: String,
        environment: String,
        installationId: String,
        token: String,
    ) = withContext(Dispatchers.IO) {
        requestJson(
            "POST",
            "/api/v1/mobile/push-subscriptions",
            JSONObject()
                .put("provider", provider)
                .put("environment", environment)
                .put("installationId", installationId)
                .put("token", token),
        )
        Unit
    }

    override suspend fun unregisterPushToken(installationId: String) =
        withContext(Dispatchers.IO) {
            val safeId = java.net.URLEncoder.encode(installationId, Charsets.UTF_8.name())
            request("DELETE", "/api/v1/mobile/push-subscriptions/" + safeId)
            Unit
        }

    private fun parseSession(body: JSONObject): SessionTokens {
        val user = body.getJSONObject("user")
        return SessionTokens(
            accessToken = body.getString("accessToken"),
            refreshToken = body.getString("refreshToken"),
            expiresAt = body.getString("expiresAt"),
            user = HumanUser(
                id = user.getString("id"),
                username = user.getString("username"),
                role = user.getString("role"),
                mfaEnabled = user.optBoolean("mfaEnabled"),
            ),
        )
    }

    private fun requestArray(method: String, path: String): JSONArray {
        val (_, text) = request(method, path)
        return JSONArray(text)
    }

    private fun requestJson(
        method: String,
        path: String,
        body: JSONObject,
        authenticated: Boolean = true,
    ): JSONObject {
        val (_, text) = request(method, path, body.toString(), authenticated)
        return JSONObject(text)
    }

    private fun request(
        method: String,
        path: String,
        body: String? = null,
        authenticated: Boolean = true,
    ): Pair<Int, String> {
        val connection = URL(baseUrl + path).openConnection() as HttpURLConnection
        connection.requestMethod = method
        connection.connectTimeout = 10_000
        connection.readTimeout = 20_000
        connection.instanceFollowRedirects = false
        connection.setRequestProperty("Accept", "application/json")
        connection.setRequestProperty("User-Agent", "DeviceMesh-Android/0.2")
        if (authenticated) {
            val token = accessToken() ?: throw ApiException(401, "No active session")
            connection.setRequestProperty("Authorization", "Bearer " + token)
        }
        if (body != null) {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.outputStream.bufferedWriter(Charsets.UTF_8).use { it.write(body) }
        }
        val status = connection.responseCode
        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
        connection.disconnect()
        if (status !in 200..299) {
            val detail = runCatching { JSONObject(text).optString("detail") }.getOrNull()
            throw ApiException(status, detail?.takeIf { it.isNotBlank() } ?: "DeviceMesh request failed")
        }
        return status to text
    }
}

private fun JSONObject.optNullableString(name: String): String? {
    if (!has(name) || isNull(name)) return null
    return optString(name).takeIf { it.isNotBlank() }
}
