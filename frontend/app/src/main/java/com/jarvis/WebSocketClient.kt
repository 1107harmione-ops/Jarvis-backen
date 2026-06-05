package com.jarvis

import android.content.Intent
import android.net.Uri
import android.provider.MediaStore
import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonObject
import kotlinx.coroutines.*
import okhttp3.*
import java.util.concurrent.TimeUnit

class WebSocketClient {
    enum class ConnectionStatus { CONNECTING, CONNECTED, DISCONNECTED, ERROR }

    private lateinit var serverUrl: String
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.SECONDS)
        .pingInterval(30, TimeUnit.SECONDS)
        .build()

    private var ws: WebSocket? = null
    private val gson = Gson()
    private var reconnectAttempts = 0
    private val maxReconnectAttempts = 20
    private var shouldReconnect = true
    private var status = ConnectionStatus.DISCONNECTED
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
                        "system", "notification" -> ChatState.addSystemMessage(displayText)
                        "error" -> ChatState.addErrorMessage(displayText)
                        "device_action" -> {
                            ChatState.addBotMessage(displayText)
                            handleDeviceAction(json, action)
                        }
                        "data" -> handleDataMessage(json)
                        else -> ChatState.addBotMessage(displayText)
                    }
                    if (intent != null) log("Received: intent=$intent msg=$displayText")
                    else log("Received: $displayText")
                } catch (e: Exception) {
                    ChatState.addBotMessage(text)
                    log("Raw message: $text")
                }
            }

            fun handleDeviceAction(json: com.google.gson.JsonObject, action: com.google.gson.JsonObject?) {
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
                            return@handleDeviceAction
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

            fun handleDataMessage(json: com.google.gson.JsonObject) {
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
                        if (data !is com.google.gson.JsonObject) return@handleDataMessage
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
            addProperty("text", text)
            addProperty("intent", intent)
            addProperty("speaker", "user")
        }
        send(msg)
        log("Sent: $text")
    }

    fun queryMemory(action: String = "history", limit: Int = 20, query: String = "") {
        val msg = JsonObject().apply {
            addProperty("type", "memory_query")
            addProperty("memory_action", action)
            addProperty("limit", limit)
            addProperty("session", "default")
            if (query.isNotEmpty()) addProperty("query", query)
        }
        send(msg)
        log("Querying memory: $action")
    }

    fun querySkills() {
        val msg = JsonObject().apply {
            addProperty("type", "skills_list")
        }
        send(msg)
        log("Querying skills")
    }

    fun queryDashboard() {
        val msg = JsonObject().apply {
            addProperty("type", "system_dashboard")
        }
        send(msg)
        log("Querying dashboard")
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
