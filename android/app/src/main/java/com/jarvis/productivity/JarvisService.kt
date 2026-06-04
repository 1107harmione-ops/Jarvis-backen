package com.jarvis.productivity

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.webkit.WebView
import androidx.core.app.NotificationCompat

class JarvisService : Service() {

    companion object {
        const val CHANNEL_ID = "jarvis_foreground"
        const val NOTIFICATION_ID = 1001
        const val KEEPALIVE_INTERVAL = 30000L
    }

    private val handler = Handler(Looper.getMainLooper())
    private var webViewRef: WebView? = null

    private val keepaliveRunnable = object : Runnable {
        override fun run() {
            val wv = webViewRef
            if (wv != null) {
                try {
                    wv.evaluateJavascript("javascript:(function(){})()", null)
                } catch (_: Exception) {}
            }
            handler.postDelayed(this, KEEPALIVE_INTERVAL)
        }
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = buildNotification()
        startForeground(NOTIFICATION_ID, notification)
        handler.postDelayed(keepaliveRunnable, KEEPALIVE_INTERVAL)
        return START_STICKY
    }

    fun setWebView(wv: WebView) {
        webViewRef = wv
    }

    override fun onDestroy() {
        handler.removeCallbacks(keepaliveRunnable)
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onTaskRemoved(rootIntent: Intent?) {
        val restartIntent = Intent(this, JarvisService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(restartIntent)
        } else {
            startService(restartIntent)
        }
        super.onTaskRemoved(rootIntent)
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "JARVIS Assistant",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "JARVIS is running in the background"
                setShowBadge(false)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(): Notification {
        val openIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val openPend = PendingIntent.getActivity(this, 0, openIntent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("JARVIS")
            .setContentText("Always listening. Say \"Jarvis\" to wake me.")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .setContentIntent(openPend)
            .build()
    }
}
