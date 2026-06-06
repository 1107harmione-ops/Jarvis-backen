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
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
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
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.google.gson.JsonParser
import kotlinx.coroutines.*
import kotlinx.coroutines.isActive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream
import java.util.Base64
import java.text.SimpleDateFormat
import java.util.*
import java.util.concurrent.TimeUnit
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.PI
import kotlin.random.Random

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

// ─── Chat Screen — Crystal Orb Voice UI ────────────────────

private data class OrbParticle(
    var x: Float, var y: Float,
    var vx: Float, var vy: Float,
    val size: Float,
    val opacity: Float,
    var pulse: Float,
    val pulseSpeed: Float
)

@Composable
fun ChatScreen() {
    val ctx = LocalContext.current
    val activity = ctx as? MainActivity
    val wsClient = AppState.wsClient
    val isListening = ChatState.isListening
    val isTyping = ChatState.isTyping
    val lastHeard = ChatState.lastHeard
    val lastSaid = ChatState.lastSaid
    var showTextInput by remember { mutableStateOf(false) }
    var inputText by remember { mutableStateOf("") }
    var isChatMode by remember { mutableStateOf(false) }
    val listState = rememberLazyListState()

    // Determine orb state color
    val orbColor = when {
        isTyping -> CrystalColors.orbProcessing
        isListening -> CrystalColors.orbListening
        else -> CrystalColors.orbIdle
    }
    val statusText = when {
        isTyping -> "WORKING..."
        isListening -> "LISTENING..."
        else -> "SYSTEM IDLE"
    }

    // ── Particle state ──
    val particles = remember { mutableStateListOf<OrbParticle>() }
    val orbSizeDp = 240.dp
    val ring1Angle = remember { mutableFloatStateOf(0f) }
    val ring2Angle = remember { mutableFloatStateOf(0f) }
    val orbGlowScale = remember { mutableFloatStateOf(1f) }
    val density = LocalDensity.current

    // Initialize particles
    LaunchedEffect(Unit) {
        val sizePx = with(density) { orbSizeDp.toPx() }
        val count = 50
        repeat(count) {
            val angle = Random.nextFloat() * 2f * kotlin.math.PI.toFloat()
            val dist = Random.nextFloat() * sizePx * 0.35f
            val c = kotlin.math.cos(angle.toDouble()).toFloat()
            val s = kotlin.math.sin(angle.toDouble()).toFloat()
            particles.add(OrbParticle(
                x = sizePx / 2f + c * dist,
                y = sizePx / 2f + s * dist,
                vx = (Random.nextFloat() - 0.5f) * 0.3f,
                vy = -0.1f - Random.nextFloat() * 0.2f,
                size = 1.5f + Random.nextFloat() * 2.5f,
                opacity = 0.3f + Random.nextFloat() * 0.4f,
                pulse = Random.nextFloat() * 2f * kotlin.math.PI.toFloat(),
                pulseSpeed = 0.01f + Random.nextFloat() * 0.02f
            ))
        }
    }

    // ── Animation loop ──
    LaunchedEffect(Unit) {
        while (isActive) {
            delay(16) // ~60fps
            val sizePx = with(density) { orbSizeDp.toPx() }
            val cx = sizePx / 2f
            val cy = sizePx / 2f
            ring1Angle.floatValue = (ring1Angle.floatValue + 0.3f) % 360f
            ring2Angle.floatValue = (ring2Angle.floatValue - 0.18f) % 360f
            orbGlowScale.floatValue = 1f + 0.03f * kotlin.math.sin((System.currentTimeMillis() * 0.001f).toDouble()).toFloat()

            for (p in particles) {
                p.x += p.vx
                p.y += p.vy
                p.pulse += p.pulseSpeed
                // Wrap around within orb
                if (p.y < cy - sizePx * 0.45f) { p.y = cy + sizePx * 0.4f; p.x = cx + (Random.nextFloat() - 0.5f) * sizePx * 0.5f }
                if (p.x < cx - sizePx * 0.45f) p.x = cx + sizePx * 0.45f
                if (p.x > cx + sizePx * 0.45f) p.x = cx - sizePx * 0.45f
                p.vx += (Random.nextFloat() - 0.5f) * 0.02f
                p.vx = p.vx.coerceIn(-0.5f, 0.5f)
            }
        }
    }

    // Auto-scroll to latest message in chat mode
    LaunchedEffect(ChatState.messages.size) {
        if (isChatMode && ChatState.messages.isNotEmpty()) {
            listState.animateScrollToItem(ChatState.messages.size - 1)
        }
    }

    Box(modifier = Modifier.fillMaxSize().background(CrystalColors.background)) {
        Column(
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Spacer(Modifier.height(48.dp))

            // ── Top bar: status + chat/voice toggle ──
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Spacer for centering
                Spacer(Modifier.weight(1f))
                Text(
                    text = statusText,
                    color = CrystalColors.cyan,
                    fontSize = 14.sp,
                    fontFamily = FontFamily.Monospace,
                    letterSpacing = 5.sp,
                    style = MaterialTheme.typography.labelLarge,
                    modifier = Modifier.weight(1f, fill = false)
                )
                Spacer(Modifier.weight(1f))
                // Mode toggle button
                FilledIconButton(
                    onClick = { isChatMode = !isChatMode },
                    modifier = Modifier.size(36.dp),
                    shape = RoundedCornerShape(18.dp),
                    colors = IconButtonDefaults.filledIconButtonColors(
                        containerColor = if (isChatMode) CrystalColors.cyan.copy(alpha = 0.2f)
                            else CrystalColors.flameOrange.copy(alpha = 0.2f)
                    )
                ) {
                    Text(
                        if (isChatMode) "🎤" else "💬",
                        fontSize = 16.sp
                    )
                }
            }

            if (isChatMode) {
                // ═══════════════════════════════════════════════════
                // CHAT MODE — scrollable message list + text input
                // ═══════════════════════════════════════════════════
                LazyColumn(
                    modifier = Modifier.weight(1f).fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
                    state = listState,
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                    contentPadding = PaddingValues(bottom = 4.dp)
                ) {
                    items(ChatState.messages, key = { it.timestamp }) { msg ->
                        ChatBubble(msg)
                    }
                    if (isTyping) {
                        item {
                            Text(
                                text = "JARVIS is thinking...",
                                color = CrystalColors.cyan.copy(alpha = 0.5f),
                                fontSize = 12.sp,
                                fontFamily = FontFamily.Monospace,
                                modifier = Modifier.padding(start = 8.dp, top = 4.dp)
                            )
                        }
                    }
                }

                // ── Chat text input bar ──
                Surface(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
                    color = CrystalColors.surfaceLight,
                    shape = RoundedCornerShape(24.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        OutlinedTextField(
                            value = inputText, onValueChange = { inputText = it },
                            modifier = Modifier.weight(1f),
                            placeholder = { Text("Type a message...", color = CrystalColors.dimText) },
                            singleLine = true,
                            shape = RoundedCornerShape(24.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = CrystalColors.cyan,
                                unfocusedBorderColor = CrystalColors.dimText,
                                cursorColor = CrystalColors.cyan,
                                focusedTextColor = CrystalColors.textPrimary,
                                unfocusedTextColor = CrystalColors.textPrimary,
                            )
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
                            modifier = Modifier.size(44.dp),
                            shape = RoundedCornerShape(22.dp),
                            colors = IconButtonDefaults.filledIconButtonColors(
                                containerColor = CrystalColors.flameOrange
                            )
                        ) {
                            Text("➤", fontSize = 20.sp, color = CrystalColors.background)
                        }
                    }
                }
            } else {
                // ═══════════════════════════════════════════════════
                // VOICE MODE — crystal orb
                // ═══════════════════════════════════════════════════

                Spacer(Modifier.weight(0.5f))

                // ── Crystal Orb ──
                Box(
                    modifier = Modifier
                        .size(orbSizeDp)
                        .pointerInput(Unit) {
                            detectTapGestures(
                                onTap = { activity?.doVoiceInput() },
                                onLongPress = { showTextInput = !showTextInput }
                            )
                        },
                    contentAlignment = Alignment.Center
                ) {
                    Canvas(modifier = Modifier.fillMaxSize()) {
                        val cx: Float = size.width / 2f
                        val cy: Float = size.height / 2f
                        val baseR: Float = minOf(cx, cy) * 0.85f
                        val glowR: Float = baseR * orbGlowScale.floatValue

                        // ── Rotating Ring 1 (dashed) ──
                        drawCircle(
                            color = CrystalColors.flameOrange.copy(alpha = 0.3f),
                            radius = baseR * 1.25f,
                            center = Offset(cx, cy),
                            style = Stroke(width = 2f, pathEffect = androidx.compose.ui.graphics.PathEffect.dashPathEffect(
                                floatArrayOf(8f, 12f), ring1Angle.floatValue
                            ))
                        )

                        // ── Rotating Ring 2 (double, counter-rotating) ──
                        drawCircle(
                            color = CrystalColors.flameOrange.copy(alpha = 0.15f),
                            radius = baseR * 1.4f,
                            center = Offset(cx, cy),
                            style = Stroke(width = 3f, pathEffect = androidx.compose.ui.graphics.PathEffect.dashPathEffect(
                                floatArrayOf(4f, 16f), ring2Angle.floatValue
                            ))
                        )

                        // ── Crystal Orb Glow ──
                        drawCircle(
                            color = orbColor.copy(alpha = 0.08f),
                            radius = glowR * 1.5f,
                            center = Offset(cx, cy)
                        )

                        // ── Crystal Orb Body ──
                        drawCircle(
                            color = orbColor.copy(alpha = 0.20f),
                            radius = glowR,
                            center = Offset(cx, cy)
                        )
                        drawCircle(
                            color = orbColor.copy(alpha = 0.10f),
                            radius = glowR * 0.85f,
                            center = Offset(cx - glowR * 0.1f, cy - glowR * 0.08f)
                        )

                        // ── Orb Core ──
                        drawCircle(
                            color = orbColor.copy(alpha = 0.3f),
                            radius = baseR * 0.4f,
                            center = Offset(cx, cy)
                        )

                        // ── Highlight ──
                        drawCircle(
                            color = Color.White.copy(alpha = 0.10f),
                            radius = baseR * 0.25f,
                            center = Offset(cx - baseR * 0.15f, cy - baseR * 0.15f)
                        )
                        drawCircle(
                            color = Color.White.copy(alpha = 0.05f),
                            radius = baseR * 0.15f,
                            center = Offset(cx - baseR * 0.2f, cy - baseR * 0.2f)
                        )
                    }
                }

                Spacer(Modifier.weight(0.3f))

                // ── Hint Text ──
                Text(
                    text = if (isListening) "LISTENING..." else "TAP THE CRYSTAL",
                    color = CrystalColors.cyan.copy(alpha = 0.6f),
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                    letterSpacing = 3.sp
                )

                Spacer(Modifier.weight(0.3f))

                // ── Transcript Overlay ──
                if (lastHeard.isNotEmpty() || lastSaid.isNotEmpty()) {
                    Surface(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 32.dp),
                        color = CrystalColors.surface.copy(alpha = 0.7f),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Column(
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            if (lastHeard.isNotEmpty()) {
                                Text(
                                    text = "[YOU] $lastHeard",
                                    color = CrystalColors.flameOrange.copy(alpha = 0.85f),
                                    fontSize = 13.sp,
                                    fontFamily = FontFamily.Monospace,
                                    textAlign = TextAlign.Center
                                )
                            }
                            if (lastSaid.isNotEmpty()) {
                                Spacer(Modifier.height(4.dp))
                                Text(
                                    text = "[JARVIS] $lastSaid",
                                    color = CrystalColors.cyan.copy(alpha = 0.85f),
                                    fontSize = 13.sp,
                                    fontFamily = FontFamily.Monospace,
                                    textAlign = TextAlign.Center
                                )
                            }
                        }
                    }
                }

                Spacer(Modifier.height(16.dp))

                // ── Text Input (hidden, toggle with long-press) ──
                AnimatedVisibility(visible = showTextInput, enter = fadeIn() + slideInVertically(),
                    exit = fadeOut() + slideOutVertically()) {
                    Surface(
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                        color = CrystalColors.surfaceLight,
                        shape = RoundedCornerShape(24.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            OutlinedTextField(
                                value = inputText, onValueChange = { inputText = it },
                                modifier = Modifier.weight(1f),
                                placeholder = { Text("Type a command...", color = CrystalColors.dimText) },
                                singleLine = true,
                                shape = RoundedCornerShape(24.dp),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedBorderColor = CrystalColors.cyan,
                                    unfocusedBorderColor = CrystalColors.dimText,
                                    cursorColor = CrystalColors.cyan,
                                    focusedTextColor = CrystalColors.textPrimary,
                                    unfocusedTextColor = CrystalColors.textPrimary,
                                )
                            )
                            Spacer(Modifier.width(8.dp))
                            FilledIconButton(
                                onClick = {
                                    val t = inputText.trim()
                                    if (t.isNotEmpty()) {
                                        wsClient?.sendText(t)
                                        inputText = ""
                                        showTextInput = false
                                    }
                                },
                                modifier = Modifier.size(44.dp),
                                shape = RoundedCornerShape(22.dp),
                                colors = IconButtonDefaults.filledIconButtonColors(
                                    containerColor = CrystalColors.flameOrange
                                )
                            ) {
                                Text("➤", fontSize = 20.sp, color = CrystalColors.background)
                            }
                        }
                    }
                }

                Spacer(Modifier.height(8.dp))
            }
        }

        // ── Connection indicator (corner) ──
        Surface(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(16.dp)
                .size(8.dp),
            shape = RoundedCornerShape(4.dp),
            color = when {
                ChatState.connectionStatus.contains("rror", true) -> CrystalColors.redGlow
                ChatState.connectionStatus == "Connected" -> CrystalColors.cyan
                else -> CrystalColors.dimText
            }
        ) {}
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
