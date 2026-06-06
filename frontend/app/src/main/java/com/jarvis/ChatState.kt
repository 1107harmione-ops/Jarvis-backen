package com.jarvis

import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf

enum class MessageType { USER, BOT, SYSTEM, ERROR }

data class ChatMessage(
    val text: String,
    val type: MessageType = MessageType.BOT,
    val timestamp: Long = System.currentTimeMillis()
) {
    val isUser get() = type == MessageType.USER
    val isSystem get() = type == MessageType.SYSTEM
    val isError get() = type == MessageType.ERROR
}

data class LogEntry(
    val text: String,
    val isError: Boolean = false,
    val timestamp: Long = System.currentTimeMillis()
)

object ChatState {
    val messages = mutableStateListOf<ChatMessage>()
    val logs = mutableStateListOf<LogEntry>()

    private val _connectionStatus = mutableStateOf("Disconnected")
    var connectionStatus: String
        get() = _connectionStatus.value
        set(v) { _connectionStatus.value = v }

    private val _isServiceRunning = mutableStateOf(false)
    var isServiceRunning: Boolean
        get() = _isServiceRunning.value
        set(v) { _isServiceRunning.value = v }

    private val _isTyping = mutableStateOf(false)
    var isTyping: Boolean
        get() = _isTyping.value
        set(v) { _isTyping.value = v }

    private val _activeTab = mutableStateOf(Screen.CHAT)
    var activeTab: Screen
        get() = _activeTab.value
        set(v) { _activeTab.value = v }

    // Admin mode state
    private val _adminMode = mutableStateOf(false)
    var adminMode: Boolean
        get() = _adminMode.value
        set(v) { _adminMode.value = v }

    private val _pendingAdminAuth = mutableStateOf(false)
    var pendingAdminAuth: Boolean
        get() = _pendingAdminAuth.value
        set(v) { _pendingAdminAuth.value = v }

    private val _adminTabIndex = mutableStateOf(0)
    var adminTabIndex: Int
        get() = _adminTabIndex.value
        set(v) { _adminTabIndex.value = v }

    // Continuous listening state
    private val _isListening = mutableStateOf(false)
    var isListening: Boolean
        get() = _isListening.value
        set(v) { _isListening.value = v }

    private val _isAwake = mutableStateOf(false)
    var isAwake: Boolean
        get() = _isAwake.value
        set(v) { _isAwake.value = v }

    private const val MAX_LOG = 200
    private const val MAX_MSG = 200

    // Transcript overlay for crystal orb UI
    private val _lastHeard = mutableStateOf("")
    private val _lastSaid = mutableStateOf("")
    var lastHeard: String
        get() = _lastHeard.value
        set(v) { _lastHeard.value = v }
    var lastSaid: String
        get() = _lastSaid.value
        set(v) { _lastSaid.value = v }

    fun addUserMessage(text: String) {
        messages.add(ChatMessage(text, type = MessageType.USER))
        lastHeard = text
        trim()
    }

    fun addBotMessage(text: String) {
        messages.add(ChatMessage(text, type = MessageType.BOT))
        lastSaid = text
        trim()
    }

    fun addSystemMessage(text: String) {
        messages.add(ChatMessage(text, type = MessageType.SYSTEM))
        trim()
    }

    fun addErrorMessage(text: String) {
        messages.add(ChatMessage(text, type = MessageType.ERROR))
        trim()
    }

    fun addLog(text: String, isError: Boolean = false) {
        logs.add(LogEntry(text, isError))
        if (logs.size > MAX_LOG) logs.removeAt(0)
    }

    fun clearMessages() {
        messages.clear()
    }

    private fun trim() {
        while (messages.size > MAX_MSG) messages.removeAt(0)
    }
}
