package com.jarvis

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.lifecycle.lifecycleScope
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.google.gson.JsonParser
import kotlinx.coroutines.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream
import java.util.Base64
import java.text.SimpleDateFormat
import java.util.*
import java.util.concurrent.TimeUnit

class MainActivity : ComponentActivity() {
    private var wsClient: WebSocketClient? = null
    private val adminClient = AdminClient()
    private var autoListenEnabled = true
    private var healthCheckJob: Job? = null
    private var speechRecognizer: SpeechRecognizer? = null
    private var recognitionIntent: Intent? = null
    private val mainHandler = Handler(Looper.getMainLooper())
    private var isVoiceActive = false
    private var voiceSchedulePending = false
    private var audioPermissionRequested = false
    private var useAudioFallbackTranscription = false
    private var fallbackVoiceJob: Job? = null
    private var wakeWindowExpiresAt = 0L
    private val transcribeClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()
    private var requireWakeWord = false
    private lateinit var ttsManager: TTSManager

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { grants ->
        val audioGranted = grants[Manifest.permission.RECORD_AUDIO] == true || hasAudioPermission()
        val msg = if (audioGranted) "Microphone ready" else "Microphone permission required"
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
        if (audioGranted && autoListenEnabled) scheduleNextVoice(500L)
    }

    private val recognitionListener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {
            ChatState.isListening = true
        }

        override fun onBeginningOfSpeech() {
            ChatState.isListening = true
        }

        override fun onRmsChanged(rmsdB: Float) = Unit
        override fun onBufferReceived(buffer: ByteArray?) = Unit
        override fun onEndOfSpeech() = Unit

        override fun onError(error: Int) {
            isVoiceActive = false
            ChatState.isListening = false
            // Defer destroy/recreate to avoid use-after-free in SpeechRecognizer callback
            mainHandler.post {
                speechRecognizer?.destroy()
                speechRecognizer = null
                setupSpeechRecognizer()
            }
            val retryDelay = when (error) {
                SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> 1200L
                SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> 700L
                SpeechRecognizer.ERROR_AUDIO,
                SpeechRecognizer.ERROR_CLIENT,
                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS,
                SpeechRecognizer.ERROR_NETWORK,
                SpeechRecognizer.ERROR_NETWORK_TIMEOUT,
                SpeechRecognizer.ERROR_SERVER -> {
                    useAudioFallbackTranscription = true
                    400L
                }
                else -> 1500L
            }
            Log.d(TAG, "Speech recognizer error: $error — recreated, retry in ${retryDelay}ms")
            if (autoListenEnabled) scheduleNextVoice(retryDelay)
        }

        override fun onResults(results: Bundle?) {
            isVoiceActive = false
            ChatState.isListening = false
            val matches = results
                ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.filter { it.isNotBlank() }
                .orEmpty()

            if (matches.isNotEmpty()) {
                handleRecognizedSpeech(matches)
            }
            if (autoListenEnabled) scheduleNextVoice(if (ChatState.isAwake) 700L else 1400L)
        }

        override fun onPartialResults(partialResults: Bundle?) = Unit
        override fun onEvent(eventType: Int, params: Bundle?) = Unit
    }

    private fun handleAdminVoice(text: String): Boolean {
        val lower = text.lowercase().trim()

        // Exit admin mode
        if (lower.contains("exit admin") || lower.contains("close admin") || lower.contains("logout admin") || lower.contains("admin off")) {
            if (ChatState.adminMode) {
                ChatState.adminMode = false
                ChatState.activeTab = Screen.CHAT
                adminClient.logoutBlocking()
                Toast.makeText(this, "Admin mode off", Toast.LENGTH_SHORT).show()
            }
            return true
        }

        // If pending password auth
        if (ChatState.pendingAdminAuth) {
            ChatState.pendingAdminAuth = false
            val result = adminClient.authBlocking(text)
            result.onSuccess {
                ChatState.adminMode = true
                ChatState.activeTab = Screen.ADMIN
                Toast.makeText(this, "Admin access granted", Toast.LENGTH_SHORT).show()
            }.onFailure {
                Toast.makeText(this, "Access denied: ${it.message}", Toast.LENGTH_SHORT).show()
            }
            return true
        }

        // Admin mode voice commands
        if (ChatState.adminMode) {
            val tab = AdminTab.fromVoice(lower)
            if (tab != null) {
                ChatState.adminTabIndex = AdminTab.entries.indexOf(tab)
                Toast.makeText(this, "Admin: ${tab.title}", Toast.LENGTH_SHORT).show()
                return true
            }
            // Pass through to chat if not an admin command
            return false
        }

        // Trigger admin login
        if ((lower.contains("admin") && (lower.contains("access") || lower.contains("mode") || lower.contains("panel") || lower.contains("open"))) ||
            lower.startsWith("admin access")) {
            ChatState.pendingAdminAuth = true
            Toast.makeText(this, "Say the admin password to continue", Toast.LENGTH_SHORT).show()
            return true
        }

        return false
    }

    private fun setupSpeechRecognizer() {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            Log.w(TAG, "Speech recognition is not available on this device")
            useAudioFallbackTranscription = true
            return
        }
        speechRecognizer?.destroy()
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this).apply {
            setRecognitionListener(recognitionListener)
        }
        recognitionIntent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 5)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1200L)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1000L)
        }
    }

    private fun handleRecognizedSpeech(matches: List<String>) {
        val best = matches.firstOrNull()?.trim().orEmpty()
        if (best.isBlank()) return

        // If wake word not required, process all speech directly
        if (!requireWakeWord) {
            dispatchVoiceCommand(best)
            return
        }

        val wakeCommand = matches.asSequence()
            .mapNotNull { commandAfterWakeWord(it) }
            .firstOrNull()

        if (wakeCommand != null) {
            wakeForNextCommand()
            if (wakeCommand.isBlank()) {
                ChatState.addSystemMessage("Jarvis awake")
                Toast.makeText(this, "Listening", Toast.LENGTH_SHORT).show()
                return
            }
            dispatchVoiceCommand(wakeCommand)
            return
        }

        if (ChatState.pendingAdminAuth || ChatState.adminMode || isWakeWindowActive()) {
            dispatchVoiceCommand(best)
            return
        }

        Log.d(TAG, "Ignored speech before wake word: $best")
        ChatState.addLog("Ignored before wake word: $best")
    }

    private fun dispatchVoiceCommand(text: String) {
        val command = text.trim()
        if (command.isBlank()) return

        Log.d(TAG, "VOICE COMMAND = $command")

        if (handleAdminVoice(command)) {
            if (!ChatState.pendingAdminAuth) sleepWakeWindow()
            return
        }

        sleepWakeWindow()
        wsClient?.sendText(command)
    }

    private fun commandAfterWakeWord(text: String): String? {
        val match = WAKE_WORD_PATTERN.find(text) ?: return null
        return text.substring(match.range.last + 1).trim()
    }

    private fun wakeForNextCommand() {
        wakeWindowExpiresAt = System.currentTimeMillis() + WAKE_WINDOW_MS
        ChatState.isAwake = true
    }

    private fun sleepWakeWindow() {
        wakeWindowExpiresAt = 0L
        ChatState.isAwake = false
    }

    private fun isWakeWindowActive(): Boolean {
        val active = System.currentTimeMillis() < wakeWindowExpiresAt
        ChatState.isAwake = active
        return active
    }

    private fun hasAudioPermission(): Boolean {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
    }

    private fun ensureAudioPermission(): Boolean {
        if (hasAudioPermission()) return true
        if (!audioPermissionRequested) {
            audioPermissionRequested = true
            requestPermissionLauncher.launch(arrayOf(Manifest.permission.RECORD_AUDIO))
        } else {
            Toast.makeText(this, "Microphone permission required", Toast.LENGTH_SHORT).show()
        }
        return false
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SettingsManager.init(this)
        ProviderManager.init(this)
        ttsManager = TTSManager(this)
        wsClient = WebSocketClient()
        AppState.wsClient = wsClient
        AppState.mainActivity = this
        ChatState.isListening = false
        ChatState.isAwake = false
        setupSpeechRecognizer()
        setContent { JarvisTheme { JarvisApp(adminClient) } }
        ensureAudioPermission()
        // TASK 8 — TTS engine check
        checkTtsEngine()
    }

    private fun checkTtsEngine() {
        // TTSManager handles engine availability via onInit callback;
        // no shallow resolveActivity check needed (it gives false negatives).
        Log.i(TAG, "TTS will be verified when TextToSpeech engine initializes")
    }

    override fun onStart() {
        super.onStart()
        wsClient?.connect(SettingsManager.getWsUrl())
        checkBackendHealth()
    }

    override fun onResume() {
        super.onResume()
        autoListenEnabled = true
        if (speechRecognizer == null) setupSpeechRecognizer()
        scheduleNextVoice(600L)
    }

    override fun onPause() {
        super.onPause()
        autoListenEnabled = false
        voiceSchedulePending = false
        ChatState.isListening = false
        isVoiceActive = false
        sleepWakeWindow()
        speechRecognizer?.cancel()
        fallbackVoiceJob?.cancel()
        fallbackVoiceJob = null
    }

    override fun onDestroy() {
        super.onDestroy()
        ttsManager.shutdown()
        wsClient?.disconnect()
        healthCheckJob?.cancel()
        autoListenEnabled = false
        isVoiceActive = false
        fallbackVoiceJob?.cancel()
        fallbackVoiceJob = null
        speechRecognizer?.destroy()
        speechRecognizer = null
    }

    // ─── Backend Health Check ──────────────────────────────
    private fun checkBackendHealth() {
        healthCheckJob?.cancel()
        healthCheckJob = lifecycleScope.launch(Dispatchers.IO) {
            try {
                val client = OkHttpClient.Builder()
                    .connectTimeout(5, TimeUnit.SECONDS)
                    .readTimeout(5, TimeUnit.SECONDS)
                    .build()
                val host = SettingsManager.getServerHost()
                    .replace("wss://", "https://")
                    .replace("ws://", "http://")
                val port = SettingsManager.getServerPort()
                val healthUrl = if (port == "443" || port == "80") "$host/health" else "$host:$port/health"
                Log.d(TAG, "Health check: $healthUrl")
                val request = Request.Builder().url(healthUrl).build()
                client.newCall(request).execute().use { response ->
                    if (response.isSuccessful) {
                        Log.d(TAG, "Backend online")
                        withContext(Dispatchers.Main) {
                            ChatState.addSystemMessage("🔌 Crystal backend online")
                            if (autoListenEnabled) scheduleNextVoice(800L)
                        }
                    } else {
                        Log.w(TAG, "Backend health: HTTP ${response.code}")
                        withContext(Dispatchers.Main) {
                            ChatState.addSystemMessage("⚠️ Backend error: HTTP ${response.code}")
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Health check failed", e)
                withContext(Dispatchers.Main) {
                    ChatState.addSystemMessage("❌ Cannot reach backend")
                }
            }
        }
    }

    private fun scheduleNextVoice(delayMs: Long = 2500L) {
        if (voiceSchedulePending) return
        voiceSchedulePending = true
        mainHandler.postDelayed({
            voiceSchedulePending = false
            if (autoListenEnabled && !isVoiceActive) {
                doVoiceInput()
            }
        }, delayMs)
    }

    fun doStartService() {
        val i = Intent(this, JarvisService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(i) else startService(i)
    }

    fun doStopService() {
        stopService(Intent(this, JarvisService::class.java))
    }

    fun doPermissions() {
        requestPermissionLauncher.launch(arrayOf(Manifest.permission.RECORD_AUDIO))
    }

    fun doAccessibility() {
        startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
    }

    fun doNotifSettings() {
        startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
    }

    fun doVoiceInput() {
        if (isVoiceActive) return
        if (!ensureAudioPermission()) return

        if (useAudioFallbackTranscription) {
            startFallbackVoiceInput()
            return
        }

        val recognizer = speechRecognizer ?: run {
            setupSpeechRecognizer()
            speechRecognizer
        }
        val intent = recognitionIntent
        if (recognizer == null || intent == null) {
            useAudioFallbackTranscription = true
            startFallbackVoiceInput()
            return
        }

        try {
            isVoiceActive = true
            ChatState.isListening = true
            recognizer.startListening(intent)
        } catch (e: Exception) {
            isVoiceActive = false
            ChatState.isListening = false
            Log.e(TAG, "Voice start failed", e)
            useAudioFallbackTranscription = true
            startFallbackVoiceInput()
        }
    }

    private fun startFallbackVoiceInput() {
        if (isVoiceActive) return
        if (!ensureAudioPermission()) return
        if (fallbackVoiceJob?.isActive == true) return

        isVoiceActive = true
        ChatState.isListening = true
        fallbackVoiceJob = lifecycleScope.launch(Dispatchers.IO) {
            try {
                val pcmBytes = capturePcmAudio(4500L)
                if (pcmBytes == null || pcmBytes.isEmpty()) {
                    Log.w(TAG, "Fallback capture returned no audio")
                    return@launch
                }
                val wavBytes = pcmToWav(pcmBytes)
                val transcript = transcribeAudioBytes(wavBytes)
                withContext(Dispatchers.Main) {
                    handleFallbackTranscript(transcript)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Fallback voice capture failed", e)
                withContext(Dispatchers.Main) {
                    isVoiceActive = false
                    ChatState.isListening = false
                    if (autoListenEnabled) scheduleNextVoice(1500L)
                }
            } finally {
                withContext(Dispatchers.Main) {
                    fallbackVoiceJob = null
                    isVoiceActive = false
                    ChatState.isListening = false
                }
            }
        }
    }

    private fun handleFallbackTranscript(rawTranscript: String) {
        isVoiceActive = false
        ChatState.isListening = false
        val transcript = rawTranscript.trim()
        if (transcript.isBlank()) {
            if (autoListenEnabled) scheduleNextVoice(900L)
            return
        }

        val wakeCommand = commandAfterWakeWord(transcript)
        if (wakeCommand != null) {
            wakeForNextCommand()
            if (wakeCommand.isBlank()) {
                ChatState.addSystemMessage("Jarvis awake")
                Toast.makeText(this, "Listening", Toast.LENGTH_SHORT).show()
            } else {
                dispatchVoiceCommand(wakeCommand)
            }
        } else if (ChatState.pendingAdminAuth || ChatState.adminMode || isWakeWindowActive()) {
            dispatchVoiceCommand(transcript)
        } else {
            Log.d(TAG, "Ignored fallback speech before wake word: $transcript")
            ChatState.addLog("Ignored fallback before wake word: $transcript")
        }

        if (autoListenEnabled) scheduleNextVoice(if (ChatState.isAwake) 700L else 1400L)
    }

    private suspend fun capturePcmAudio(durationMs: Long): ByteArray? = withContext(Dispatchers.IO) {
        val sampleRate = 16000
        val channelConfig = AudioFormat.CHANNEL_IN_MONO
        val audioFormat = AudioFormat.ENCODING_PCM_16BIT
        val minBufferSize = AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioFormat)
        if (minBufferSize <= 0) return@withContext null

        val bufferSize = maxOf(minBufferSize, sampleRate * 2)
        val recorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            AudioRecord.Builder()
                .setAudioSource(MediaRecorder.AudioSource.VOICE_RECOGNITION)
                .setAudioFormat(
                    android.media.AudioFormat.Builder()
                        .setSampleRate(sampleRate)
                        .setEncoding(audioFormat)
                        .setChannelMask(channelConfig)
                        .build()
                )
                .setBufferSizeInBytes(bufferSize)
                .build()
        } else {
            @Suppress("DEPRECATION")
            AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                sampleRate,
                channelConfig,
                audioFormat,
                bufferSize
            )
        }

        if (recorder.state != AudioRecord.STATE_INITIALIZED) {
            recorder.release()
            return@withContext null
        }

        val output = ByteArrayOutputStream()
        val buffer = ByteArray(bufferSize)
        try {
            recorder.startRecording()
            val deadline = SystemClock.elapsedRealtime() + durationMs
            while (SystemClock.elapsedRealtime() < deadline && isVoiceActive) {
                val read = recorder.read(buffer, 0, buffer.size)
                if (read > 0) {
                    output.write(buffer, 0, read)
                } else if (read == AudioRecord.ERROR_INVALID_OPERATION || read == AudioRecord.ERROR_BAD_VALUE) {
                    break
                }
            }
            output.toByteArray()
        } finally {
            try { recorder.stop() } catch (_: Exception) {}
            recorder.release()
        }
    }

    private fun pcmToWav(pcmBytes: ByteArray, sampleRate: Int = 16000): ByteArray {
        val channels = 1
        val bitsPerSample = 16
        val byteRate = sampleRate * channels * bitsPerSample / 8
        val dataSize = pcmBytes.size
        val output = ByteArrayOutputStream(44 + dataSize)

        fun writeString(value: String) {
            output.write(value.toByteArray(Charsets.US_ASCII))
        }

        fun writeIntLE(value: Int) {
            output.write(value and 0xff)
            output.write(value shr 8 and 0xff)
            output.write(value shr 16 and 0xff)
            output.write(value shr 24 and 0xff)
        }

        fun writeShortLE(value: Int) {
            output.write(value and 0xff)
            output.write(value shr 8 and 0xff)
        }

        writeString("RIFF")
        writeIntLE(36 + dataSize)
        writeString("WAVE")
        writeString("fmt ")
        writeIntLE(16)
        writeShortLE(1)
        writeShortLE(channels)
        writeIntLE(sampleRate)
        writeIntLE(byteRate)
        writeShortLE(channels * bitsPerSample / 8)
        writeShortLE(bitsPerSample)
        writeString("data")
        writeIntLE(dataSize)
        output.write(pcmBytes)
        return output.toByteArray()
    }

    private suspend fun transcribeAudioBytes(wavBytes: ByteArray): String = withContext(Dispatchers.IO) {
        if (wavBytes.isEmpty()) return@withContext ""
        val payload = org.json.JSONObject().apply {
            put("audio", Base64.getEncoder().encodeToString(wavBytes))
        }.toString()
        val base = SettingsManager.getServerHost()
            .trim()
            .removeSuffix("/")
            .replace("wss://", "https://")
            .replace("ws://", "http://")
        val port = SettingsManager.getServerPort()
        val url = if (port == "443" || port == "80") "$base/transcribe/json" else "$base:$port/transcribe/json"
        val request = Request.Builder()
            .url(url)
            .post(payload.toRequestBody("application/json".toMediaType()))
            .build()

        transcribeClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw java.io.IOException("Transcribe HTTP ${response.code}")
            }
            val body = response.body?.string().orEmpty()
            if (body.isBlank()) return@withContext ""
            val parsed = JsonParser.parseString(body).asJsonObject
            parsed.get("text")?.asString.orEmpty()
        }
    }

    fun speak(text: String) {
        Log.d(TAG, "TTS SPEAK = $text")
        ttsManager.speak(text)
    }

    fun requestPermissions(perms: Array<String>) {
        requestPermissionLauncher.launch(perms)
    }

    companion object {
        private const val TAG = "JarvisMain"
        private const val WAKE_WINDOW_MS = 12_000L
        private val WAKE_WORD_PATTERN = Regex(
            "^\\s*(?:hey\\s+|ok\\s+|okay\\s+)?(?:jarvis|jervis|javis|jarves)\\b[\\s,!.?-]*",
            RegexOption.IGNORE_CASE
        )
    }
}

// ─── App Shell ────────────────────────────────────────────

@Composable
fun JarvisApp(adminClient: AdminClient = AdminClient()) {
    val activeTab = ChatState.activeTab
    val admin = ChatState.adminMode
    Scaffold(
        bottomBar = { JarvisBottomNav(activeTab, { ChatState.activeTab = it }, showAdmin = admin) }
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            AnimatedScreen(
                currentScreen = activeTab,
                chat = { ChatScreen() },
                memory = { MemoryScreen() },
                skills = { SkillsScreen() },
                settings = { AppSettingsScreen() },
                dashboard = { DashboardScreen() },
                admin = { AdminScreen(adminClient) }
            )
        }
    }
}

// ─── Chat Screen ──────────────────────────────────────────

@Composable
fun ChatScreen() {
    val ctx = LocalContext.current
    val activity = ctx as? MainActivity
    val wsClient = AppState.wsClient
    var inputText by remember { mutableStateOf("") }
    val listState = rememberLazyListState()
    val messages = ChatState.messages
    val connectionStatus = ChatState.connectionStatus
    val isTyping = ChatState.isTyping

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) listState.animateScrollToItem(messages.size - 1)
    }

    Column(modifier = Modifier.fillMaxSize()) {
        // Top bar
        Surface(
            modifier = Modifier.fillMaxWidth(),
            color = MaterialTheme.colorScheme.primaryContainer,
            tonalElevation = 4.dp
        ) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text("J.A.R.V.I.S.", fontSize = 22.sp, fontWeight = FontWeight.Bold)
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        // Connection indicator
                        Surface(
                            modifier = Modifier.size(8.dp),
                            shape = RoundedCornerShape(4.dp),
                            color = when {
                                connectionStatus == "Connected" -> Color(0xFF4CAF50)
                                connectionStatus.contains("rror", true) -> Color(0xFFF44336)
                                connectionStatus == "Connecting..." -> Color(0xFFFFC107)
                                else -> Color(0xFF9E9E9E)
                            }
                        ) {}
                        Spacer(Modifier.width(6.dp))
                        Text(connectionStatus, fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onPrimaryContainer)
                        // Listening indicator
                        if (ChatState.isListening) {
                            Spacer(Modifier.width(12.dp))
                            Surface(
                                modifier = Modifier.size(8.dp),
                                shape = RoundedCornerShape(4.dp),
                                color = Color(0xFF00E5FF)
                            ) {}
                            Spacer(Modifier.width(4.dp))
                            Text("LISTENING", fontSize = 10.sp,
                                color = Color(0xFF00E5FF),
                                fontWeight = FontWeight.Bold)
                        }
                        if (ChatState.isAwake) {
                            Spacer(Modifier.width(12.dp))
                            Surface(
                                modifier = Modifier.size(8.dp),
                                shape = RoundedCornerShape(4.dp),
                                color = Color(0xFF4CAF50)
                            ) {}
                            Spacer(Modifier.width(4.dp))
                            Text("AWAKE", fontSize = 10.sp,
                                color = Color(0xFF4CAF50),
                                fontWeight = FontWeight.Bold)
                        }
                    }
                }
                FilledTonalButton(onClick = { activity?.doVoiceInput() }, modifier = Modifier.size(40.dp)) {
                    Text("🎤", fontSize = 16.sp)
                }
            }
        }

        // Messages
        LazyColumn(
            modifier = Modifier.weight(1f).fillMaxWidth().padding(horizontal = 8.dp),
            state = listState,
            verticalArrangement = Arrangement.spacedBy(6.dp),
            contentPadding = PaddingValues(vertical = 8.dp)
        ) {
            if (messages.isEmpty()) {
                item {
                    Box(modifier = Modifier.fillMaxWidth().padding(48.dp), contentAlignment = Alignment.Center) {
                        Text(
                            "Ask me anything...\nTap 🎤 or type a command",
                            textAlign = TextAlign.Center,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            fontSize = 16.sp
                        )
                    }
                }
            }
            items(messages) { msg ->
                ChatBubble(msg)
            }
            // Typing indicator
            if (isTyping) {
                item {
                    Box(modifier = Modifier.fillMaxWidth().padding(start = 8.dp, top = 4.dp)) {
                        Surface(
                            shape = RoundedCornerShape(4.dp, 16.dp, 16.dp, 4.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text("JARVIS",
                                    fontSize = 11.sp, fontWeight = FontWeight.Bold,
                                    color = MaterialTheme.colorScheme.primary)
                                Spacer(Modifier.width(8.dp))
                                AnimatedDots()
                            }
                        }
                    }
                }
            }
        }

        // Input bar
        Surface(modifier = Modifier.fillMaxWidth(), tonalElevation = 8.dp, shadowElevation = 8.dp) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedTextField(
                    value = inputText, onValueChange = { inputText = it },
                    modifier = Modifier.weight(1f),
                    placeholder = { Text("Type a command...") },
                    singleLine = true, shape = RoundedCornerShape(24.dp)
                )
                Spacer(Modifier.width(8.dp))
                FilledIconButton(
                    onClick = {
                        val t = inputText.trim()
                        if (t.isNotEmpty()) {
                            wsClient?.sendText(t)
                            inputText = ""
                        }
                    },
                    modifier = Modifier.size(48.dp), shape = RoundedCornerShape(24.dp)
                ) {
                    Text("➤", fontSize = 22.sp)
                }
            }
        }
    }
}

@Composable
fun ChatBubble(msg: ChatMessage) {
    val isUser = msg.isUser
    val isSystem = msg.isSystem
    val isError = msg.isError
    val bubbleColor = when {
        isError -> MaterialTheme.colorScheme.errorContainer
        isSystem -> MaterialTheme.colorScheme.secondaryContainer
        isUser -> MaterialTheme.colorScheme.primary
        else -> MaterialTheme.colorScheme.surfaceVariant
    }
    val textColor = when {
        isError -> MaterialTheme.colorScheme.onErrorContainer
        isSystem -> MaterialTheme.colorScheme.onSecondaryContainer
        isUser -> MaterialTheme.colorScheme.onPrimary
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    val timeStr = remember(msg.timestamp) {
        val now = System.currentTimeMillis()
        val diff = now - msg.timestamp
        when {
            diff < 60_000 -> "just now"
            diff < 3600_000 -> "${diff / 60_000}m ago"
            diff < 86400_000 -> "${diff / 3600_000}h ago"
            else -> SimpleDateFormat("MMM d", Locale.getDefault()).format(Date(msg.timestamp))
        }
    }
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        Surface(
            shape = RoundedCornerShape(
                topStart = 16.dp, topEnd = 16.dp,
                bottomStart = if (isUser) 16.dp else 4.dp,
                bottomEnd = if (isUser) 4.dp else 16.dp
            ),
            color = bubbleColor,
            shadowElevation = 1.dp
        ) {
            Column(modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
                Text(msg.text, color = textColor, fontSize = 15.sp, textAlign = TextAlign.Start)
                Text(timeStr, color = textColor.copy(alpha = 0.5f), fontSize = 10.sp,
                    modifier = Modifier.padding(top = 2.dp))
            }
        }
    }
}

// ─── Settings Screen ──────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppSettingsScreen() {
    val ctx = LocalContext.current
    val activity = ctx as? MainActivity
    val wsClient = AppState.wsClient
    var serverHost by remember { mutableStateOf(SettingsManager.getServerHost()) }
    var serverPort by remember { mutableStateOf(SettingsManager.getServerPort()) }
    var themeMode by remember { mutableStateOf(SettingsManager.getThemeMode()) }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text("Settings", fontSize = 22.sp, fontWeight = FontWeight.Bold)

        // ── Server ──
        SettingsSection("Server") {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = serverHost, onValueChange = { serverHost = it },
                    modifier = Modifier.weight(3f),
                    label = { Text("Host") }, singleLine = true
                )
                OutlinedTextField(
                    value = serverPort, onValueChange = { serverPort = it },
                    modifier = Modifier.weight(1f),
                    label = { Text("Port") }, singleLine = true
                )
            }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = {
                    SettingsManager.saveServer(serverHost, serverPort)
                    wsClient?.updateUrl(SettingsManager.getWsUrl())
                    Toast.makeText(ctx, "Server URL updated", Toast.LENGTH_SHORT).show()
                }, modifier = Modifier.weight(1f)) { Text("Apply") }
                OutlinedButton(onClick = { wsClient?.reconnect() }, modifier = Modifier.weight(1f)) {
                    Text("Reconnect")
                }
            }
        }

        // ── Appearance ──
        SettingsSection("Appearance") {
            Text("Theme", fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
                listOf("system" to "Auto", "light" to "Light", "dark" to "Dark").forEach { (value, label) ->
                    SegmentedButton(
                        selected = themeMode == value,
                        onClick = { themeMode = value; SettingsManager.setThemeMode(value) },
                        shape = SegmentedButtonDefaults.itemShape(0, listOf("system", "light", "dark").indexOf(value))
                    ) { Text(label, fontSize = 12.sp) }
                }
            }
        }

        // ── Service ──
        SettingsSection("Service") {
            Button(onClick = {
                ChatState.isServiceRunning = !ChatState.isServiceRunning
                if (ChatState.isServiceRunning) activity?.doStartService() else activity?.doStopService()
            }, modifier = Modifier.fillMaxWidth()) {
                Text(if (ChatState.isServiceRunning) "Stop Service" else "Start Service")
            }
        }

        // ── Permissions ──
        SettingsSection("Permissions") {
            val perms: Map<String, Boolean> = remember(activity) {
                activity?.let { PermissionsHelper.grantedPermissions(it) } ?: emptyMap()
            }
            PermissionsHelper.ALL_GROUPS.forEach { group ->
                val granted = perms[group.name] ?: false
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(group.icon, fontSize = 16.sp)
                        Spacer(Modifier.width(8.dp))
                        Column {
                            Text(group.name, fontSize = 14.sp)
                            Text(group.description, fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    Surface(
                        modifier = Modifier.size(12.dp),
                        shape = RoundedCornerShape(6.dp),
                        color = if (granted) Color(0xFF4CAF50) else Color(0xFF9E9E9E)
                    ) {}
                }
            }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = { activity?.doPermissions() }, modifier = Modifier.fillMaxWidth()) {
                Text("Grant Permissions")
            }
        }

        // ── Accessibility ──
        SettingsSection("Access") {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { activity?.doAccessibility() }, modifier = Modifier.weight(1f)) {
                    Text("Accessibility")
                }
                OutlinedButton(onClick = { activity?.doNotifSettings() }, modifier = Modifier.weight(1f)) {
                    Text("Notif Access")
                }
            }
        }

        // ── Chat ──
        SettingsSection("Chat") {
            OutlinedButton(onClick = { ChatState.clearMessages() }, modifier = Modifier.fillMaxWidth()) {
                Text("Clear Chat History", color = MaterialTheme.colorScheme.error)
            }
        }

        Spacer(Modifier.height(16.dp))
        Text("JARVIS v1.0.0 • Fully Offline",
            fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center)
    }
}

@Composable
fun SettingsSection(title: String, content: @Composable ColumnScope.() -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        tonalElevation = 2.dp
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(title, fontWeight = FontWeight.Bold, fontSize = 14.sp,
                color = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.height(8.dp))
            content()
        }
    }
}

@Composable
fun AnimatedDots() {
    val infiniteTransition = rememberInfiniteTransition(label = "dots")
    val delays = listOf(0, 200, 400)
    Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        delays.forEach { delay ->
            val alpha by infiniteTransition.animateFloat(
                initialValue = 0.3f,
                targetValue = 1.0f,
                animationSpec = infiniteRepeatable(
                    animation = tween(600, delayMillis = delay),
                    repeatMode = RepeatMode.Reverse
                ),
                label = "dot_$delay"
            )
            Box(
                modifier = Modifier
                    .size(6.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.primary.copy(alpha = alpha))
            )
        }
    }
}

// ─── Debug Screen ─────────────────────────────────────────

@Composable
fun DebugScreen() {
    val logs = ChatState.logs
    val listState = rememberLazyListState()

    LaunchedEffect(logs.size) {
        if (logs.isNotEmpty()) listState.animateScrollToItem(logs.size - 1)
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Surface(
            modifier = Modifier.fillMaxWidth(),
            color = MaterialTheme.colorScheme.primaryContainer,
            tonalElevation = 4.dp
        ) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Debug Log", fontSize = 18.sp, fontWeight = FontWeight.Bold)
                TextButton(onClick = { ChatState.logs.clear() }) {
                    Text("Clear", color = MaterialTheme.colorScheme.error)
                }
            }
        }

        if (logs.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("No log entries yet",
                    fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(8.dp),
                state = listState,
                verticalArrangement = Arrangement.spacedBy(2.dp)
            ) {
                items(logs.toList()) { entry ->
                    Text(
                        entry.text,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        color = if (entry.isError) MaterialTheme.colorScheme.error
                                else MaterialTheme.colorScheme.onSurface
                    )
                }
            }
        }
    }
}
