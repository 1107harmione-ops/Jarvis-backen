package com.jarvis.productivity

import android.app.admin.DevicePolicyManager
import android.bluetooth.BluetoothAdapter
import android.content.ComponentName
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.Build
import android.os.PowerManager
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.provider.Settings
import android.speech.tts.TextToSpeech
import android.telephony.TelephonyManager
import android.widget.Toast
import android.webkit.WebView
import org.json.JSONObject
import java.util.Locale

class JarvisBridge(
    private val context: Context,
    private val webView: WebView
) {
    private var tts: TextToSpeech? = null
    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager

    init {
        tts = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts?.language = Locale.US
            }
        }
    }

    @android.webkit.JavascriptInterface
    fun speak(text: String) {
        if (text.isBlank()) return
        stopTts()
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, null)
    }

    @android.webkit.JavascriptInterface
    fun stopTts() {
        tts?.stop()
    }

    @android.webkit.JavascriptInterface
    fun toast(message: String) {
        Toast.makeText(context, message, Toast.LENGTH_SHORT).show()
    }

    @android.webkit.JavascriptInterface
    fun vibrate(ms: Int) {
        val vib = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val vm = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
            vm.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vib.vibrate(VibrationEffect.createOneShot(ms.toLong(), VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            @Suppress("DEPRECATION")
            vib.vibrate(ms.toLong())
        }
    }

    @android.webkit.JavascriptInterface
    fun openApp(pkg: String) {
        try {
            val intent = context.packageManager.getLaunchIntentForPackage(pkg)
            if (intent != null) {
                context.startActivity(intent)
            } else {
                val storeIntent = Intent(Intent.ACTION_VIEW).apply {
                    data = Uri.parse("market://details?id=$pkg")
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(storeIntent)
            }
        } catch (_: Exception) {}
    }

    @android.webkit.JavascriptInterface
    fun closeApp(pkg: String) {
        try {
            val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                data = Uri.parse("package:$pkg")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (_: Exception) {}
    }

    @android.webkit.JavascriptInterface
    fun openUrl(url: String) {
        try {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (_: Exception) {}
    }

    @android.webkit.JavascriptInterface
    fun wifi(on: Boolean) {
        try {
            val wifiManager = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            wifiManager.isWifiEnabled = on
        } catch (_: Exception) {}
    }

    @android.webkit.JavascriptInterface
    fun bluetooth(on: Boolean) {
        try {
            val btAdapter = BluetoothAdapter.getDefaultAdapter()
            if (btAdapter != null) {
                if (on) btAdapter.enable() else btAdapter.disable()
            }
        } catch (_: Exception) {}
    }

    @android.webkit.JavascriptInterface
    fun flashlight(on: Boolean) {
        try {
            context.packageManager?.let { pm ->
                val camera = android.hardware.camera2.CameraManager::class.java
                    .getDeclaredMethod("from", Context::class.java)
                    .invoke(null, context) as android.hardware.camera2.CameraManager
                val cameraId = camera.cameraIdList[0]
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    camera.setTorchMode(cameraId, on)
                }
            }
        } catch (_: Exception) {}
    }

    @android.webkit.JavascriptInterface
    fun brightness(level: Int) {
        try {
            val clamped = level.coerceIn(0, 255)
            if (Settings.System.canWrite(context)) {
                Settings.System.putInt(context.contentResolver, Settings.System.SCREEN_BRIGHTNESS, clamped)
            } else {
                val intent = Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS).apply {
                    data = Uri.parse("package:${context.packageName}")
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(intent)
            }
        } catch (_: Exception) {}
    }

    @android.webkit.JavascriptInterface
    fun ringerMode(mode: String) {
        try {
            val ringer = when (mode.lowercase()) {
                "silent", "silence" -> AudioManager.RINGER_MODE_SILENT
                "vibrate" -> AudioManager.RINGER_MODE_VIBRATE
                else -> AudioManager.RINGER_MODE_NORMAL
            }
            audioManager.ringerMode = ringer
        } catch (_: Exception) {}
    }

    @android.webkit.JavascriptInterface
    fun dnd(on: Boolean) {
        try {
            val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                if (notificationManager.isNotificationPolicyAccessGranted) {
                    if (on) {
                        notificationManager.setInterruptionFilter(android.app.NotificationManager.INTERRUPTION_FILTER_NONE)
                    } else {
                        notificationManager.setInterruptionFilter(android.app.NotificationManager.INTERRUPTION_FILTER_ALL)
                    }
                } else {
                    val intent = Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS).apply {
                        flags = Intent.FLAG_ACTIVITY_NEW_TASK
                    }
                    context.startActivity(intent)
                }
            }
        } catch (_: Exception) {}
    }

    @android.webkit.JavascriptInterface
    fun airplane(on: Boolean) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN_MR1) {
                Settings.Global.putInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON, if (on) 1 else 0)
                val intent = Intent(Intent.ACTION_AIRPLANE_MODE_CHANGED).apply {
                    putExtra("state", on)
                }
                context.sendBroadcast(intent)
            }
        } catch (_: Exception) {}
    }

    @android.webkit.JavascriptInterface
    fun clipboard(text: String) {
        try {
            val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
            val clip = android.content.ClipData.newPlainText("JARVIS", text)
            clipboard.setPrimaryClip(clip)
        } catch (_: Exception) {}
    }

    @android.webkit.JavascriptInterface
    fun clipboardRead(): String {
        return try {
            val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
            if (clipboard.hasPrimaryClip()) {
                clipboard.primaryClip?.getItemAt(0)?.text?.toString() ?: ""
            } else ""
        } catch (_: Exception) { "" }
    }

    @android.webkit.JavascriptInterface
    fun share(text: String) {
        try {
            val intent = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_TEXT, text)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(Intent.createChooser(intent, "Share via"))
        } catch (_: Exception) {}
    }

    @android.webkit.JavascriptInterface
    fun mediaPlay() {
        try {
            val intent = Intent("com.android.music.musicservicecommand").apply {
                putExtra("command", "play")
            }
            context.sendBroadcast(intent)
            val downIntent = Intent(Intent.ACTION_MEDIA_BUTTON).apply {
                putExtra(Intent.EXTRA_KEY_EVENT, android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN, android.view.KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE))
            }
            context.sendOrderedBroadcast(downIntent, null)
        } catch (_: Exception) {}
    }

    @android.webkit.JavascriptInterface
    fun mediaNext() {
        try {
            val downIntent = Intent(Intent.ACTION_MEDIA_BUTTON).apply {
                putExtra(Intent.EXTRA_KEY_EVENT, android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN, android.view.KeyEvent.KEYCODE_MEDIA_NEXT))
            }
            context.sendOrderedBroadcast(downIntent, null)
        } catch (_: Exception) {}
    }

    @android.webkit.JavascriptInterface
    fun mediaPrev() {
        try {
            val downIntent = Intent(Intent.ACTION_MEDIA_BUTTON).apply {
                putExtra(Intent.EXTRA_KEY_EVENT, android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN, android.view.KeyEvent.KEYCODE_MEDIA_PREVIOUS))
            }
            context.sendOrderedBroadcast(downIntent, null)
        } catch (_: Exception) {}
    }

    @android.webkit.JavascriptInterface
    fun mediaVolume(direction: Int) {
        try {
            val maxVol = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
            var current = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC)
            current = when {
                direction > 0 -> (current + 1).coerceAtMost(maxVol)
                direction < -50 -> 0
                direction < 0 -> (current - 1).coerceAtLeast(0)
                else -> current
            }
            audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, current, 0)
        } catch (_: Exception) {}
    }

    @android.webkit.JavascriptInterface
    fun sendSms(number: String, message: String) {
        try {
            val intent = Intent(Intent.ACTION_SENDTO).apply {
                data = Uri.parse("smsto:$number")
                putExtra("sms_body", message)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (_: Exception) {}
    }

    @android.webkit.JavascriptInterface
    fun screenOn(): Boolean {
        return try {
            val pm = context.getSystemService(Context.POWER_SERVICE) as PowerManager
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT_WATCH) {
                pm.isInteractive
            } else {
                @Suppress("DEPRECATION")
                pm.isScreenOn
            }
        } catch (_: Exception) { false }
    }

    @android.webkit.JavascriptInterface
    fun deviceInfo(): String {
        return try {
            JSONObject().apply {
                put("manufacturer", Build.MANUFACTURER)
                put("model", Build.MODEL)
                put("brand", Build.BRAND)
                put("device", Build.DEVICE)
                put("product", Build.PRODUCT)
                put("version", Build.VERSION.RELEASE)
                put("sdk", Build.VERSION.SDK_INT)
                put("board", Build.BOARD)
                put("hardware", Build.HARDWARE)
                put("fingerprint", Build.FINGERPRINT)
                put("display", Build.DISPLAY)
            }.toString()
        } catch (_: Exception) { "{}" }
    }
}
