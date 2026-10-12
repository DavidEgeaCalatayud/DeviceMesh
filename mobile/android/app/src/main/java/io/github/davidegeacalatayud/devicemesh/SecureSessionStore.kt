package io.github.davidegeacalatayud.devicemesh

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import io.github.davidegeacalatayud.devicemesh.core.model.HumanUser
import io.github.davidegeacalatayud.devicemesh.core.model.SessionTokens
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import java.util.UUID
import org.json.JSONObject

class SecureSessionStore(context: Context) {
    private val preferences = context.getSharedPreferences("secure_session", Context.MODE_PRIVATE)

    fun save(session: SessionTokens) {
        val payload = JSONObject()
            .put("accessToken", session.accessToken)
            .put("refreshToken", session.refreshToken)
            .put("expiresAt", session.expiresAt)
            .put("user", JSONObject()
                .put("id", session.user.id)
                .put("username", session.user.username)
                .put("role", session.user.role)
                .put("mfaEnabled", session.user.mfaEnabled))
            .toString().toByteArray(Charsets.UTF_8)
        preferences.edit().putString("session", encrypt(payload)).apply()
    }

    fun load(): SessionTokens? {
        val encrypted = preferences.getString("session", null) ?: return null
        return runCatching {
            val body = JSONObject(decrypt(encrypted).toString(Charsets.UTF_8))
            val user = body.getJSONObject("user")
            SessionTokens(
                body.getString("accessToken"),
                body.getString("refreshToken"),
                body.getString("expiresAt"),
                HumanUser(
                    user.getString("id"),
                    user.getString("username"),
                    user.getString("role"),
                    user.optBoolean("mfaEnabled"),
                ),
            )
        }.getOrElse { clear(); null }
    }

    fun clear() { preferences.edit().remove("session").apply() }
    fun saveServer(server: String) { preferences.edit().putString("server", server).apply() }
    fun server(): String = preferences.getString("server", null) ?: "https://mesh.example.com"

    fun installationId(): String {
        preferences.getString("installation_id", null)?.let { return it }
        val created = UUID.randomUUID().toString()
        preferences.edit().putString("installation_id", created).apply()
        return created
    }

    fun savePushToken(token: String) {
        preferences.edit()
            .putString("push_token", encrypt(token.toByteArray(Charsets.UTF_8)))
            .apply()
    }

    fun pushToken(): String? {
        val encrypted = preferences.getString("push_token", null) ?: return null
        return runCatching { decrypt(encrypted).toString(Charsets.UTF_8) }.getOrNull()
    }

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
            ).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build())
            generateKey()
        }
    }

    private fun encrypt(plaintext: ByteArray): String {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        return Base64.encodeToString(cipher.iv + cipher.doFinal(plaintext), Base64.NO_WRAP)
    }

    private fun decrypt(encoded: String): ByteArray {
        val blob = Base64.decode(encoded, Base64.NO_WRAP)
        require(blob.size > IV_SIZE)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(
            Cipher.DECRYPT_MODE,
            key(),
            GCMParameterSpec(128, blob.copyOfRange(0, IV_SIZE)),
        )
        return cipher.doFinal(blob.copyOfRange(IV_SIZE, blob.size))
    }

    private companion object {
        const val KEY_ALIAS = "devicemesh.mobile.session.v1"
        const val IV_SIZE = 12
    }
}
