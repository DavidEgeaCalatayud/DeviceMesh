package io.github.davidegeacalatayud.devicemesh

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import io.github.davidegeacalatayud.devicemesh.core.network.HttpDeviceMeshApi
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class DeviceMeshFirebaseService : FirebaseMessagingService() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onNewToken(token: String) {
        val store = SecureSessionStore(this)
        store.savePushToken(token)
        val session = store.load() ?: return
        scope.launch {
            runCatching {
                HttpDeviceMeshApi(store.server()) { session.accessToken }.registerPushToken(
                    provider = "fcm",
                    environment = "production",
                    installationId = store.installationId(),
                    token = token,
                )
            }
        }
    }

    @SuppressLint("MissingPermission")
    override fun onMessageReceived(message: RemoteMessage) {
        createNotificationChannel()
        if (
            Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            return
        }

        val title = message.notification?.title
            ?: message.data["title"]
            ?: "DeviceMesh alert"
        val body = message.notification?.body
            ?: message.data["body"]
            ?: buildString {
                append(message.data["deviceId"] ?: "DeviceMesh")
                message.data["metricName"]?.let { append(" · ").append(it) }
                message.data["value"]?.let { append("=").append(it) }
            }

        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra("deviceId", message.data["deviceId"])
            putExtra("alertId", message.data["alertId"])
        }
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_error)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .build()

        NotificationManagerCompat.from(this).notify(
            (System.currentTimeMillis() and 0x7FFFFFFF).toInt(),
            notification,
        )
    }

    private fun createNotificationChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                "DeviceMesh alerts",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply {
                description = "Operational alerts and recoveries from DeviceMesh"
            },
        )
    }

    private companion object {
        const val CHANNEL_ID = "devicemesh-alerts"
    }
}
