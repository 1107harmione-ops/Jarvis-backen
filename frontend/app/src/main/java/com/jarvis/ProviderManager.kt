package com.jarvis

import android.content.Context
import androidx.compose.runtime.mutableStateListOf
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken

object ProviderManager {
    private const val PREFS_KEY = "jarvis_providers"
    private lateinit var prefs: android.content.SharedPreferences
    private val gson = Gson()

    private val _providers = mutableStateListOf<AiProvider>()
    val providers: List<AiProvider> get() = _providers

    var activeProviderId: String? = null

    fun init(ctx: Context) {
        prefs = ctx.getSharedPreferences("jarvis_providers", Context.MODE_PRIVATE)
        load()
        if (_providers.isEmpty()) {
            // Initialize with local offline as default
            val local = ProviderDefaults.findById("free-local") ?: return
            _providers.add(local.copy(enabled = true))
            activeProviderId = local.id
            save()
        }
    }

    private fun load() {
        val json = prefs.getString(PREFS_KEY, null) ?: return
        try {
            val type = object : TypeToken<ProviderData>() {}.type
            val data: ProviderData = gson.fromJson(json, type) ?: return
            _providers.clear()
            _providers.addAll(data.providers)
            activeProviderId = data.activeId
        } catch (_: Exception) {}
    }

    private fun save() {
        val data = ProviderData(_providers.toList(), activeProviderId)
        prefs.edit().putString(PREFS_KEY, gson.toJson(data)).apply()
    }

    fun addProvider(provider: AiProvider) {
        _providers.removeAll { it.id == provider.id }
        _providers.add(provider)
        save()
    }

    fun removeProvider(id: String) {
        _providers.removeAll { it.id == id }
        if (activeProviderId == id) activeProviderId = null
        save()
    }

    fun toggleProvider(id: String) {
        val idx = _providers.indexOfFirst { it.id == id }
        if (idx >= 0) {
            val p = _providers[idx]
            val toggled = p.copy(enabled = !p.enabled)
            _providers[idx] = toggled
            if (toggled.enabled) activeProviderId = id
            else if (activeProviderId == id) {
                activeProviderId = _providers.firstOrNull { it.enabled }?.id
            }
            save()
        }
    }

    fun updateProviderKey(id: String, apiKey: String) {
        val idx = _providers.indexOfFirst { it.id == id }
        if (idx >= 0) {
            _providers[idx] = _providers[idx].copy(apiKey = apiKey)
            save()
        }
    }

    fun updateProviderModel(id: String, model: String) {
        val idx = _providers.indexOfFirst { it.id == id }
        if (idx >= 0) {
            _providers[idx] = _providers[idx].copy(defaultModel = model)
            save()
        }
    }

    fun getActiveProvider(): AiProvider? {
        return _providers.find { it.id == activeProviderId && it.enabled }
    }

    fun addPresetById(id: String) {
        val existing = _providers.find { it.id == id }
        if (existing != null) return
        val preset = ProviderDefaults.findById(id) ?: return
        _providers.add(preset)
        if (_providers.count { it.enabled } == 0) {
            val idx = _providers.size - 1
            _providers[idx] = _providers[idx].copy(enabled = true)
            activeProviderId = id
        }
        save()
    }

    /** Serialize config for sending to server */
    fun toServerConfig(): String {
        val configs = _providers.filter { it.enabled && it.apiKey.isNotEmpty() }.map { p ->
            mapOf(
                "id" to p.id,
                "name" to p.name,
                "api_format" to p.apiFormat.name.lowercase(),
                "base_url" to p.baseUrl,
                "api_key" to p.apiKey,
                "model" to p.defaultModel,
                "enabled" to p.enabled,
            )
        }
        return gson.toJson(mapOf(
            "type" to "provider_config",
            "active" to activeProviderId,
            "providers" to configs,
        ))
    }

    private data class ProviderData(
        val providers: List<AiProvider>,
        val activeId: String?,
    )
}
