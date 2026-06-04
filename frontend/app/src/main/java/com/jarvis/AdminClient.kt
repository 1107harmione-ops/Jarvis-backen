package com.jarvis

import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.MediaType.Companion.toMediaType
import java.util.concurrent.TimeUnit

class AdminClient {
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()
    private val gson = Gson()
    private val JSON = "application/json".toMediaType()

    var token: String? = null
        private set
    var isAuthenticated = false
        private set

    private fun baseUrl(): String {
        val host = SettingsManager.getServerHost().replace("wss://", "https://").replace("ws://", "http://")
        return host
    }

    fun authBlocking(password: String): Result<String> = runBlocking { auth(password) }

    fun logoutBlocking(): Result<JsonObject> = runBlocking { logout() }

    suspend fun auth(password: String): Result<String> = withContext(Dispatchers.IO) {
        try {
            val body = gson.toJson(mapOf("password" to password))
            val request = Request.Builder()
                .url("${baseUrl()}/admin/auth")
                .post(body.toRequestBody(JSON))
                .build()
            val response = client.newCall(request).execute()
            val json = JsonParser.parseString(response.body?.string() ?: "{}").asJsonObject
            val status = json.get("status")?.asString ?: "denied"
            if (status == "granted" && json.has("token")) {
                token = json.get("token").asString
                isAuthenticated = true
                Result.success(json.get("message")?.asString ?: "Admin access granted")
            } else {
                Result.failure(Exception(json.get("message")?.asString ?: "Access denied"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun authRequestBuilder(): Request.Builder {
        return Request.Builder().addHeader("X-Admin-Token", token ?: "")
    }

    suspend fun getFiles(path: String = ""): Result<JsonObject> = apiGet("/admin/files?path=${java.net.URLEncoder.encode(path, "UTF-8")}")
    suspend fun readFile(path: String): Result<JsonObject> = apiGet("/admin/files/read?path=${java.net.URLEncoder.encode(path, "UTF-8")}")
    suspend fun writeFile(path: String, content: String): Result<JsonObject> = apiPost("/admin/files/write", mapOf("path" to path, "content" to content))
    suspend fun getConfig(): Result<JsonObject> = apiGet("/admin/config")
    suspend fun updateConfig(key: String, value: String): Result<JsonObject> = apiPost("/admin/config/update", mapOf("key" to key, "value" to value))
    suspend fun getApiKeys(): Result<JsonObject> = apiGet("/admin/api-keys")
    suspend fun updateApiKey(provider: String, key: String = "", model: String = ""): Result<JsonObject> {
        val body = mutableMapOf("provider" to provider)
        if (key.isNotEmpty()) body["key"] = key
        if (model.isNotEmpty()) body["model"] = model
        return apiPost("/admin/api-keys/update", body)
    }
    suspend fun getProviders(): Result<JsonObject> = apiGet("/admin/providers")
    suspend fun addProvider(name: String, baseUrl: String = "", apiKeyEnv: String = ""): Result<JsonObject> =
        apiPost("/admin/providers/add", mapOf("name" to name, "base_url" to baseUrl, "api_key_env" to apiKeyEnv, "models" to emptyList<String>(), "enabled" to true))
    suspend fun removeProvider(name: String): Result<JsonObject> = apiPost("/admin/providers/remove", mapOf("name" to name))
    suspend fun addModel(provider: String, model: String): Result<JsonObject> = apiPost("/admin/providers/models/add", mapOf("provider" to provider, "model" to model))
    suspend fun removeModel(provider: String, model: String): Result<JsonObject> = apiPost("/admin/providers/models/remove", mapOf("provider" to provider, "model" to model))
    suspend fun getSessions(limit: Int = 50): Result<JsonObject> = apiGet("/admin/sessions?limit=$limit")
    suspend fun getSessionMessages(sessionId: String): Result<JsonObject> = apiGet("/admin/sessions/${java.net.URLEncoder.encode(sessionId, "UTF-8")}")
    suspend fun deleteSession(sessionId: String): Result<JsonObject> = apiPost("/admin/sessions/delete", mapOf("session_id" to sessionId))
    suspend fun getSystemInfo(): Result<JsonObject> = apiGet("/admin/system")
    suspend fun getAuditLog(limit: Int = 50): Result<JsonObject> = apiGet("/admin/audit?limit=$limit")
    suspend fun getDbStats(): Result<JsonObject> = apiGet("/admin/db/stats")
    suspend fun queryDb(collection: String, filter: Map<String, Any> = emptyMap(), limit: Int = 20): Result<JsonObject> =
        apiPost("/admin/db/query", mapOf("collection" to collection, "filter" to filter, "limit" to limit))
    suspend fun restartSystem(): Result<JsonObject> = apiPost("/admin/system/restart", emptyMap<String, Any>())
    suspend fun clearCache(): Result<JsonObject> = apiPost("/admin/cache/clear", emptyMap<String, Any>())
    suspend fun logout(): Result<JsonObject> = apiPost("/admin/logout", emptyMap<String, Any>())

    private suspend fun apiGet(path: String): Result<JsonObject> = withContext(Dispatchers.IO) {
        try {
            val request = authRequestBuilder().url("${baseUrl()}$path").get().build()
            val response = client.newCall(request).execute()
            val json = JsonParser.parseString(response.body?.string() ?: "{}").asJsonObject
            if (response.isSuccessful) Result.success(json) else Result.failure(Exception(json.get("error")?.asString ?: "API error"))
        } catch (e: Exception) { Result.failure(e) }
    }

    private suspend fun apiPost(path: String, body: Map<String, Any>): Result<JsonObject> = withContext(Dispatchers.IO) {
        try {
            val jsonBody = gson.toJson(body)
            val request = authRequestBuilder().url("${baseUrl()}$path").post(jsonBody.toRequestBody(JSON)).build()
            val response = client.newCall(request).execute()
            val json = JsonParser.parseString(response.body?.string() ?: "{}").asJsonObject
            if (response.isSuccessful) Result.success(json) else Result.failure(Exception(json.get("error")?.asString ?: "API error"))
        } catch (e: Exception) { Result.failure(e) }
    }

    companion object {
        private const val TAG = "JarvisAdmin"
    }
}
