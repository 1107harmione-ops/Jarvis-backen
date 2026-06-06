package com.jarvis

import android.os.Handler
import android.os.Looper
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log

class NotificationListener : NotificationListenerService() {
    private val mainHandler = Handler(Looper.getMainLooper())

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        val packageName = sbn.packageName
        val extras = sbn.notification.extras
        val title = extras.getString(android.app.Notification.EXTRA_TITLE, "")
        val text = extras.getString(android.app.Notification.EXTRA_TEXT, "")
        Log.d(TAG, "Notification from $packageName: $title - $text")

        val appName = packageName.split(".").lastOrNull()?.replaceFirstChar { it.uppercase() } ?: packageName
        val display = buildString {
            append("📬 ")
            if (title.isNotEmpty()) append("[$title] ")
            if (text.isNotEmpty()) append(text)
            if (isEmpty()) append("Notification from $appName")
        }

        // Post state mutations to main thread for thread safety
        mainHandler.post {
            ChatState.addSystemMessage(display)
            ChatState.addLog("Notification: $packageName - $title")

            // Forward to server if connected
            val ws = AppState.wsClient
            if (ws != null) {
                val msg = com.google.gson.JsonObject().apply {
                    addProperty("type", "notification")
                    addProperty("package", packageName)
                    addProperty("title", title)
                    addProperty("text", text)
                    addProperty("speaker", "system")
                }
                ws.send(msg)
            }
        }
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification?) {}

    override fun onListenerConnected() {
        Log.d(TAG, "Notification listener connected")
    }

    companion object {
        private const val TAG = "JarvisNotif"
    }
}
