package com.jarvis

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.speech.RecognizerIntent
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
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
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

class MainActivity : ComponentActivity() {
    private var wsClient: WebSocketClient? = null

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) {
        val msg = if (it.values.all { v -> v }) "Permissions granted" else "Permissions required"
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
    }

    private val voiceLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == RESULT_OK) {
            val matches = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            if (!matches.isNullOrEmpty()) {
                wsClient?.sendText(matches[0])
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SettingsManager.init(this)
        ProviderManager.init(this)
        wsClient = WebSocketClient()
        AppState.wsClient = wsClient
        AppState.mainActivity = this
        setContent { JarvisTheme { JarvisApp() } }
    }

    override fun onStart() {
        super.onStart()
        wsClient?.connect(SettingsManager.getWsUrl())
    }

    override fun onDestroy() {
        super.onDestroy()
        wsClient?.disconnect()
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
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            Toast.makeText(this, "Audio permission required", Toast.LENGTH_SHORT).show(); return
        }
        try {
            voiceLauncher.launch(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak your command")
            })
        } catch (_: Exception) {
            Toast.makeText(this, "Voice not supported", Toast.LENGTH_SHORT).show()
        }
    }

    fun requestPermissions(perms: Array<String>) {
        requestPermissionLauncher.launch(perms)
    }
}

// ─── App Shell ────────────────────────────────────────────

@Composable
fun JarvisApp() {
    val activeTab = ChatState.activeTab
    Scaffold(
        bottomBar = { JarvisBottomNav(activeTab) { ChatState.activeTab = it } }
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            AnimatedScreen(
                currentScreen = activeTab,
                chat = { ChatScreen() },
                memory = { MemoryScreen() },
                skills = { SkillsScreen() },
                settings = { AppSettingsScreen() },
                dashboard = { DashboardScreen() }
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
            val perms = remember { PermissionsHelper.grantedPermissions(activity!!) }
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
