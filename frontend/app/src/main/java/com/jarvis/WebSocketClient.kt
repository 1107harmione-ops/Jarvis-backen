package com.jarvis

import android.content.Intent
import android.net.Uri
import android.provider.MediaStore
import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import kotlinx.coroutines.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.*
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

class WebSocketClient {
    enum class ConnectionStatus { CONNECTING, CONNECTED, DISCONNECTED, ERROR }

    private lateinit var serverUrl: String
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.SECONDS)
        .pingInterval(30, TimeUnit.SECONDS)
        .build()
    private val chatClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()
    private val jsonMediaType = "application/json".toMediaType()

    private var ws: WebSocket? = null
    private val gson = Gson()
    private var reconnectAttempts = 0
    private val maxReconnectAttempts = 20
    private var shouldReconnect = true
    private var status = ConnectionStatus.DISCONNECTED
    var sessionId: String = "android-${System.currentTimeMillis()}"
    private var scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private fun log(msg: String, isError: Boolean = false) {
        if (isError) Log.e(TAG, msg) else Log.d(TAG, msg)
        ChatState.addLog(msg, isError)
    }

    fun getUrl(): String = if (::serverUrl.isInitialized) serverUrl else "not set"

    fun updateUrl(newUrl: String) {
        val wasConnected = status == ConnectionStatus.CONNECTED
        if (wasConnected) disconnect()
        serverUrl = newUrl
        reconnectAttempts = 0
        if (wasConnected) connect()
        log("Server URL updated: $newUrl")
    }

    fun connect(url: String? = null) {
        if (url != null) serverUrl = url

        if (!::serverUrl.isInitialized) {
            log("Server URL not configured", true)
            return
        }
        if (scope.coroutineContext[Job]?.isActive != true) {
            scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
        }
        if (status == ConnectionStatus.CONNECTED || status == ConnectionStatus.CONNECTING) return
        shouldReconnect = true
        updateStatus(ConnectionStatus.CONNECTING)
        log("Connecting to $serverUrl...")
        val request = Request.Builder().url(serverUrl).build()
        ws = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(ws: WebSocket, response: Response) {
                reconnectAttempts = 0
                updateStatus(ConnectionStatus.CONNECTED)
                log("Connected to server")
            }

            override fun onMessage(ws: WebSocket, text: String) {
                ChatState.isTyping = false
                try {
                    val json = gson.fromJson(text, JsonObject::class.java)
                    val action = json.get("action")?.asJsonObject
                    val message = json.get("message")?.asString
                    val intent = json.get("intent")?.asString
                    val msgStatus = json.get("status")?.asString
                    val msgType = json.get("type")?.asString

                    val displayText = when {
                        message != null -> message
                        action != null -> action.get("message")?.asString ?: text
                        else -> text
                    }
                    when (msgType) {
                        "system", "notification" -> {
                            ChatState.addSystemMessage(displayText)
                            Log.d(TAG, "SERVER RESPONSE = $displayText")
                        }
                        "error" -> {
                            ChatState.addErrorMessage(displayText)
                            Log.d(TAG, "SERVER ERROR = $displayText")
                        }
                        "device_action" -> {
                            ChatState.addBotMessage(displayText)
                            Log.d(TAG, "SERVER RESPONSE = $displayText")
                            AppState.mainActivity?.speak(displayText)
                            this@WebSocketClient.handleDeviceAction(json, action)
                        }
                        "data" -> this@WebSocketClient.handleDataMessage(json)
                        else -> {
                            ChatState.addBotMessage(displayText)
                            Log.d(TAG, "SERVER RESPONSE = $displayText")
                            AppState.mainActivity?.speak(displayText)
                        }
                    }
                    if (intent != null) log("Received: intent=$intent msg=$displayText")
                    else log("Received: $displayText")
                } catch (e: Exception) {
                    ChatState.addBotMessage(text)
                    Log.d(TAG, "RAW MESSAGE = $text")
                    log("Raw message: $text")
                }
            }


            override fun onClosing(ws: WebSocket, code: Int, reason: String) {
                ws.close(1000, null)
                log("Connection closing: $code $reason")
            }

            override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                updateStatus(ConnectionStatus.DISCONNECTED)
                log("Disconnected: $code $reason")
                scheduleReconnect()
            }

            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                updateStatus(ConnectionStatus.ERROR)
                val err = t.message ?: "Unknown error"
                log("Connection failed: $err", isError = true)
                scheduleReconnect()
            }
        })
    }

    fun disconnect() {
        shouldReconnect = false
        ws?.close(1000, "Client closing")
        ws = null
        updateStatus(ConnectionStatus.DISCONNECTED)
        scope.cancel()
        log("Disconnected by user")
    }

    fun reconnect() {
        disconnect()
        reconnectAttempts = 0
        shouldReconnect = true
        scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
        connect()
        log("Reconnecting...")
    }

    fun send(message: JsonObject) {
        ws?.send(gson.toJson(message))
    }

    fun sendText(text: String, intent: String = "UNKNOWN") {
        ChatState.addUserMessage(text)
        ChatState.isTyping = true
        val msg = JsonObject().apply {
            addProperty("message", text)
            addProperty("text", text)
            addProperty("intent", intent)
            addProperty("speaker", "user")
            addProperty("session_id", sessionId)
        }
        val sent = ws?.send(gson.toJson(msg)) == true
        if (sent) {
            Log.d(TAG, "SEND TEXT = $text")
            log("Sent via websocket: $text")
            return
        }
        log("WebSocket unavailable; posting chat over HTTP")
        scope.launch {
            postChatFallback(text, intent)
        }
    }

    /** HTTP fallback when WebSocket is unavailable */
    private suspend fun postChatFallback(text: String, intent: String) = kotlinx.coroutines.withContext(Dispatchers.IO) {
        try {
            val rawUrl = if (::serverUrl.isInitialized) {
                serverUrl
            } else {
                SettingsManager.getWsUrl()
            }
            // Convert WS scheme to HTTP and strip /ws suffix
            val url = rawUrl
                .replace("wss://", "https://").replace("ws://", "http://")
                .removeSuffix("/ws").removeSuffix("/")
            val endpoint = if (url.contains("://")) url else "$url:8000"
            val body = gson.toJson(mapOf("message" to text, "text" to text, "intent" to intent, "speaker" to "user", "session_id" to sessionId))
            val request = Request.Builder()
                .url("$endpoint/chat")
                .post(body.toRequestBody(jsonMediaType))
                .build()
            chatClient.newCall(request).execute().use { response ->
                val reply = response.body?.string() ?: "{}"
                val json = JsonParser.parseString(reply).asJsonObject
                val replyText = json.get("response")?.asString ?: json.get("reply")?.asString ?: json.get("message")?.asString ?: "No response"
                withContext(Dispatchers.Main) {
                    ChatState.addBotMessage(replyText)
                    ChatState.isTyping = false
                }
                log("HTTP fallback response received")
            }
        } catch (e: Exception) {
            withContext(Dispatchers.Main) {
                ChatState.addErrorMessage("Chat fallback failed: ${e.message}")
                ChatState.isTyping = false
            }
            log("HTTP fallback error: ${e.message}", isError = true)
        }
    }

    private fun handleDeviceAction(json: JsonObject, action: JsonObject?) {
        val actionType = action?.get("action")?.asString ?: json.get("action")?.asString ?: return
        val ctx = AppState.mainActivity ?: return
        log("Device action: $actionType")
        when (actionType) {
            "take_photo" -> {
                val intent = CameraManager.getLaunchIntent(ctx)
                ctx.startActivity(intent)
            }
            "scan_qr" -> {
                val intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
                ctx.startActivity(intent)
            }
            "send_sms" -> {
                val intent = Intent(Intent.ACTION_VIEW).apply {
                    type = "vnd.android-dir/mms-sms"
                }
                ctx.startActivity(intent)
            }
            "read_sms" -> {
                val msgs = SmsProvider.readLatest(ctx, 5)
                if (msgs.isEmpty()) {
                    ChatState.addSystemMessage("No messages found")
                } else {
                    msgs.forEach { msg ->
                        ChatState.addSystemMessage("📬 ${msg.address}: ${msg.body}")
                    }
                }
            }
            "get_events" -> {
                val events = CalendarProvider.getUpcoming(ctx, 7)
                if (events.isEmpty()) {
                    ChatState.addSystemMessage("No upcoming events")
                } else {
                    events.take(5).forEach { ev ->
                        ChatState.addSystemMessage("📅 ${ev.title} - ${ev.startTime}")
                    }
                }
            }
            "get_location" -> {
                val loc = LocationProvider.getLastKnownLocation(ctx)
                if (loc != null) {
                    ChatState.addBotMessage("📍 ${loc.latitude}, ${loc.longitude} (${loc.provider})")
                } else {
                    ChatState.addSystemMessage("Location unavailable. Enable GPS and try again.")
                }
            }
            "search_contacts" -> {
                val query = action?.get("query")?.asString ?: ""
                val results = ContactsProvider.search(ctx, query)
                if (results.isEmpty()) {
                    ChatState.addSystemMessage("No contacts found for \"$query\"")
                } else {
                    results.take(5).forEach { c ->
                        ChatState.addSystemMessage("👤 ${c.name}: ${c.phone}")
                    }
                }
            }
            "start_screen_record" -> {
                ChatState.addSystemMessage("Screen recording requires user consent via notification")
            }
            "stop_screen_record" -> {
                val file = ScreenRecorder.stopRecording()
                if (file != null) {
                    ChatState.addBotMessage("Recording saved: ${file.name}")
                } else {
                    ChatState.addSystemMessage("No active recording")
                }
            }
            "call_contact", "make_call" -> {
                val query = action?.get("query")?.asString
                    ?: action?.get("target")?.asString
                    ?: json.get("message")?.asString
                    ?: ""
                if (query.isBlank()) {
                    ChatState.addSystemMessage("Who should I call?")
                    return
                }
                val contacts = ContactsProvider.search(ctx, query)
                if (contacts.isEmpty()) {
                    ChatState.addSystemMessage("No contacts found for \"$query\"")
                } else {
                    val contact = contacts.first()
                    val phone = contact.phone.replace(Regex("[^\\d+]"), "")
                    if (phone.isNotEmpty()) {
                        try {
                            val callIntent = Intent(Intent.ACTION_CALL).apply {
                                data = android.net.Uri.parse("tel:$phone")
                                flags = Intent.FLAG_ACTIVITY_NEW_TASK
                            }
                            ctx.startActivity(callIntent)
                            ChatState.addBotMessage("📞 Calling ${contact.name} ($phone)")
                        } catch (e: Exception) {
                            ChatState.addErrorMessage("Cannot make call: ${e.message}")
                        }
                    } else {
                        ChatState.addSystemMessage("${contact.name} has no phone number")
                    }
                    if (contacts.size > 1) {
                        ChatState.addSystemMessage("Also found: ${contacts.drop(1).take(4).joinToString { "${it.name}: ${it.phone}" }}")
                    }
                }
            }
        }
    }

    private fun handleDataMessage(json: JsonObject) {
        val dataType = json.get("data_type")?.asString ?: return
        val data = json.get("data")?.asJsonObject
            ?: json.get("data")?.asJsonArray
            ?: return
        when (dataType) {
            "memory" -> {
                DashboardState.memoryLoading.value = false
                val items = mutableListOf<MemoryEntry>()
                if (data.isJsonArray) {
                    data.asJsonArray.forEach { el ->
                        val obj = el.asJsonObject
                        items.add(MemoryEntry(
                            speaker = obj.get("speaker")?.asString ?: "",
                            message = obj.get("message")?.asString ?: "",
                            intent = obj.get("intent")?.asString ?: "",
                            timestamp = obj.get("timestamp")?.asString ?: "",
                        ))
                    }
                }
                DashboardState.memoryEntries.value = items
            }
            "skills" -> {
                DashboardState.skillsLoading.value = false
                val items = mutableListOf<SkillEntry>()
                if (data.isJsonArray) {
                    data.asJsonArray.forEach { el ->
                        val obj = el.asJsonObject
                        items.add(SkillEntry(
                            name = obj.get("name")?.asString ?: "",
                            trigger = obj.get("trigger")?.asString ?: "",
                            stepsCount = obj.get("steps_count")?.asInt ?: 0,
                            successCount = obj.get("success_count")?.asInt ?: 0,
                            failCount = obj.get("fail_count")?.asInt ?: 0,
                            autoCreated = obj.get("auto_created")?.asBoolean ?: false,
                        ))
                    }
                }
                DashboardState.skillEntries.value = items
            }
            "dashboard" -> {
                DashboardState.dashboardLoading.value = false
                if (data !is JsonObject) return
                val perms = mutableMapOf<String, Boolean>()
                val permObj = data.getAsJsonObject("permissions")
                if (permObj != null) {
                    for (entry in permObj.entrySet()) {
                        val key = entry.key
                        val value = entry.value
                        perms[key] = value.asJsonObject?.get("granted")?.asBoolean ?: false
                    }
                }
                val riskSummary = mutableMapOf<String, Int>()
                val riskObj = data.getAsJsonObject("risk_summary")
                if (riskObj != null) {
                    for (entry in riskObj.entrySet()) {
                        riskSummary[entry.key] = entry.value.asInt
                    }
                }
                val pers = data.getAsJsonObject("personalization")
                val cpuElement = data.get("cpu")
                val cpu = cpuElement?.asDouble
                val mem = data.getAsJsonObject("memory")
                DashboardState.dashboardInfo.value = DashboardInfo(
                    version = data.get("version")?.asString ?: "",
                    battery = data.get("battery")?.asString ?: "",
                    cpu = if (cpu != null) "%.1f%%".format(cpu) else "",
                    memoryUsed = if (mem != null) "${mem.get("used")?.asLong?.div(1048576)}MB" else "",
                    memoryTotal = if (mem != null) "${mem.get("total")?.asLong?.div(1048576)}MB" else "",
                    personalizationScore = pers?.get("percentage")?.asDouble ?: 0.0,
                    personalizationLevel = pers?.get("level")?.asString ?: "",
                    permissions = perms,
                    riskSummary = riskSummary,
                )
            }
        }
    }

    /** Fetch dashboard data via HTTP REST */
    fun fetchDashboardHttp() {
        scope.launch {
            try {
                val url = getHttpBaseUrl()
                val request = Request.Builder().url("$url/api/dashboard").build()
                chatClient.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return@launch
                    val body = response.body?.string() ?: return@launch
                    val json = JsonParser.parseString(body).asJsonObject
                    withContext(Dispatchers.Main) {
                        // Reuse existing handleDataMessage logic
                        val wrapper = JsonObject().apply {
                            addProperty("data_type", "dashboard")
                            add("data", json)
                        }
                        handleDataMessage(wrapper)
                    }
                }
            } catch (e: Exception) {
                log("Dashboard HTTP fetch failed: ${e.message}", isError = true)
            }
        }
    }

    /** Fetch memory data via HTTP REST */
    fun fetchMemoryHttp(action: String = "history", limit: Int = 20, query: String = "") {
        scope.launch {
            try {
                val url = getHttpBaseUrl()
                val queryStr = buildString {
                    append("?action=$action&limit=$limit")
                    if (query.isNotEmpty()) append("&query=${java.net.URLEncoder.encode(query, "UTF-8")}")
                }
                val request = Request.Builder().url("$url/api/memory$queryStr").build()
                chatClient.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return@launch
                    val body = response.body?.string() ?: return@launch
                    val json = JsonParser.parseString(body).asJsonObject
                    withContext(Dispatchers.Main) {
                        handleDataMessage(json)
                    }
                }
            } catch (e: Exception) {
                log("Memory HTTP fetch failed: ${e.message}", isError = true)
            }
        }
    }

    /** Fetch skills data via HTTP REST */
    fun fetchSkillsHttp() {
        scope.launch {
            try {
                val url = getHttpBaseUrl()
                val request = Request.Builder().url("$url/api/skills").build()
                chatClient.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) return@launch
                    val body = response.body?.string() ?: return@launch
                    val json = JsonParser.parseString(body).asJsonObject
                    withContext(Dispatchers.Main) {
                        handleDataMessage(json)
                    }
                }
            } catch (e: Exception) {
                log("Skills HTTP fetch failed: ${e.message}", isError = true)
            }
        }
    }

    /** Build HTTP base URL from the configured WS URL */
    private fun getHttpBaseUrl(): String {
        val raw = if (::serverUrl.isInitialized) serverUrl else SettingsManager.getWsUrl()
        return raw
            .replace("wss://", "https://").replace("ws://", "http://")
            .removeSuffix("/ws").removeSuffix("/")
    }

    fun queryMemory(action: String = "history", limit: Int = 20, query: String = "") {
        if (status == ConnectionStatus.CONNECTED) {
            val msg = JsonObject().apply {
                addProperty("type", "memory_query")
                addProperty("memory_action", action)
                addProperty("limit", limit)
                addProperty("session", "default")
                if (query.isNotEmpty()) addProperty("query", query)
            }
            send(msg)
            log("Querying memory via WS: $action")
        } else {
            fetchMemoryHttp(action, limit, query)
            log("Querying memory via HTTP: $action")
        }
    }

    fun querySkills() {
        if (status == ConnectionStatus.CONNECTED) {
            val msg = JsonObject().apply {
                addProperty("type", "skills_list")
            }
            send(msg)
            log("Querying skills via WS")
        } else {
            fetchSkillsHttp()
            log("Querying skills via HTTP")
        }
    }

    fun queryDashboard() {
        if (status == ConnectionStatus.CONNECTED) {
            val msg = JsonObject().apply {
                addProperty("type", "system_dashboard")
            }
            send(msg)
            log("Querying dashboard via WS")
        } else {
            fetchDashboardHttp()
            log("Querying dashboard via HTTP")
        }
    }

    fun sendAudio(base64Audio: String) {
        val msg = JsonObject().apply {
            addProperty("audio", base64Audio)
            addProperty("intent", "UNKNOWN")
        }
        send(msg)
    }

    private fun updateStatus(s: ConnectionStatus) {
        status = s
        ChatState.connectionStatus = when (s) {
            ConnectionStatus.CONNECTED -> "Connected"
            ConnectionStatus.CONNECTING -> "Connecting..."
            ConnectionStatus.DISCONNECTED -> "Disconnected"
            ConnectionStatus.ERROR -> "Error"
        }
    }

    private fun scheduleReconnect() {
        if (!shouldReconnect || reconnectAttempts >= maxReconnectAttempts) return
        reconnectAttempts++
        val delayMs = (reconnectAttempts * 2000).coerceAtMost(30000).toLong()
        log("Reconnecting in ${delayMs / 1000}s (attempt $reconnectAttempts/$maxReconnectAttempts)")
        scope.launch {
            delay(delayMs)
            connect()
        }
    }

    fun getStatus(): ConnectionStatus = status

    companion object {
        private const val TAG = "JarvisWS"
    }
}
