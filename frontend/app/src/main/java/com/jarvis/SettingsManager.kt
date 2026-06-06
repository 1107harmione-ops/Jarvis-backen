package com.jarvis

import android.content.Context
import android.content.SharedPreferences

object SettingsManager {
    private const val PREFS = "jarvis_settings"
    private const val KEY_URL = "server_host"
    private const val KEY_PORT = "server_port"
    private const val KEY_THEME = "theme_mode"
    private const val DEFAULT_URL = "wss://jarvis-backen-ouhz.onrender.com"
    private const val DEFAULT_PORT = "443"

    private lateinit var prefs: SharedPreferences

    fun init(ctx: Context) {
        if (!::prefs.isInitialized) {
            prefs = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        }
    }

    fun getServerHost(): String = prefs.getString(KEY_URL, DEFAULT_URL) ?: DEFAULT_URL
    fun getServerPort(): String = prefs.getString(KEY_PORT, DEFAULT_PORT) ?: DEFAULT_PORT

    fun getWsUrl(): String {
        val rawHost = getServerHost().removeSuffix("/").removeSuffix("/ws")
        val port = getServerPort()

        // Extract scheme and host without port
        val scheme = when {
            rawHost.startsWith("wss://") -> "wss://"
            rawHost.startsWith("ws://") -> "ws://"
            rawHost.startsWith("https://") -> "wss://"
            rawHost.startsWith("http://") -> "ws://"
            else -> "wss://"
        }
        val hostOnly = rawHost
            .removePrefix("wss://").removePrefix("ws://")
            .removePrefix("https://").removePrefix("http://")
            .split(":")[0]  // remove any port from host string

        // Use port from settings; if it's default, omit it
        return if (port == "443" || port == "80") {
            "$scheme$hostOnly/ws"
        } else {
            "$scheme$hostOnly:$port/ws"
        }
    }

    fun saveServer(host: String, port: String) {
        prefs.edit()
            .putString(KEY_URL, host.trim().removeSuffix("/"))
            .putString(KEY_PORT, port.trim())
            .apply()
    }

    fun getThemeMode(): String = prefs.getString(KEY_THEME, "system") ?: "system"

    fun setThemeMode(mode: String) {
        prefs.edit().putString(KEY_THEME, mode).apply()
    }
}
