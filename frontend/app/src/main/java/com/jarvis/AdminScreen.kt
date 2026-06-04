package com.jarvis

import android.widget.Toast
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import kotlinx.coroutines.launch

private val adminClient = AdminClient()

enum class AdminTab(val title: String, val icon: @Composable () -> Unit) {
    Files("Files", { Text("📁", fontSize = 16.sp) }),
    Config("Config", { Text("⚙", fontSize = 16.sp) }),
    ApiKeys("API Keys", { Text("🔑", fontSize = 16.sp) }),
    Providers("Providers", { Text("🔌", fontSize = 16.sp) }),
    Sessions("Sessions", { Text("💬", fontSize = 16.sp) }),
    Database("Database", { Text("🗄", fontSize = 16.sp) }),
    System("System", { Text("📊", fontSize = 16.sp) }),
    Audit("Audit", { Text("📋", fontSize = 16.sp) });

    companion object {
        fun fromVoice(text: String): AdminTab? {
            val lower = text.lowercase()
            return when {
                lower.contains("file") -> Files
                lower.contains("config") || lower.contains("setting") -> Config
                lower.contains("key") || lower.contains("api") -> ApiKeys
                lower.contains("provider") || lower.contains("model") -> Providers
                lower.contains("session") || lower.contains("chat") -> Sessions
                lower.contains("database") || lower.contains("db") || lower.contains("query") -> Database
                lower.contains("system") || lower.contains("cpu") || lower.contains("ram") || lower.contains("server") -> System
                lower.contains("audit") || lower.contains("log") -> Audit
                else -> null
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AdminScreen() {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var isAuthed by remember { mutableStateOf(false) }
    var showPasswordDialog by remember { mutableStateOf(true) }
    var password by remember { mutableStateOf("") }
    var authError by remember { mutableStateOf("") }
    var selectedTab by remember { mutableStateOf(AdminTab.entries.getOrElse(ChatState.adminTabIndex) { AdminTab.Files }) }
    val tabs = AdminTab.entries.toList()

    if (showPasswordDialog) {
        AlertDialog(
            onDismissRequest = {},
            title = { Text("🔐 Admin Access", fontWeight = FontWeight.Bold) },
            text = {
                Column {
                    if (authError.isNotEmpty()) {
                        Text(authError, color = MaterialTheme.colorScheme.error, fontSize = 13.sp)
                        Spacer(Modifier.height(8.dp))
                    }
                    OutlinedTextField(
                        value = password, onValueChange = { password = it },
                        label = { Text("Password") },
                        singleLine = true,
                        visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            },
            confirmButton = {
                Button(onClick = {
                    scope.launch {
                        val result = adminClient.auth(password)
                        result.onSuccess {
                            isAuthed = true
                            showPasswordDialog = false
                            Toast.makeText(ctx, "Admin access granted", Toast.LENGTH_SHORT).show()
                        }.onFailure {
                            authError = it.message ?: "Access denied"
                        }
                    }
                }) { Text("Authenticate") }
            },
            dismissButton = {}
        )
    }

    if (isAuthed) {
        // Sync tab from voice commands
        LaunchedEffect(ChatState.adminTabIndex) {
            if (ChatState.adminTabIndex in tabs.indices) {
                selectedTab = tabs[ChatState.adminTabIndex]
            }
        }
        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text("🛡 Admin Panel", fontSize = 18.sp, fontWeight = FontWeight.Bold) },
                    actions = {
                        IconButton(onClick = {
                            scope.launch { adminClient.logout() }
                            isAuthed = false
                            showPasswordDialog = true
                            Toast.makeText(ctx, "Admin logged out", Toast.LENGTH_SHORT).show()
                        }) {
                            Icon(Icons.Default.Logout, "Exit Admin", tint = MaterialTheme.colorScheme.error)
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
                )
            },
            bottomBar = {
                ScrollableTabRow(
                    selectedTabIndex = tabs.indexOf(selectedTab),
                    edgePadding = 0.dp,
                    divider = {},
                ) {
                    tabs.forEach { tab ->
                        Tab(
                            selected = selectedTab == tab,
                            onClick = { selectedTab = tab; ChatState.adminTabIndex = tabs.indexOf(tab) },
                            text = {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    tab.icon()
                                    Spacer(Modifier.width(4.dp))
                                    Text(tab.title, fontSize = 10.sp)
                                }
                            }
                        )
                    }
                }
            }
        ) { padding ->
            Box(Modifier.padding(padding).fillMaxSize()) {
                when (selectedTab) {
                    AdminTab.Files -> AdminFilesTab(scope)
                    AdminTab.Config -> AdminConfigTab(scope)
                    AdminTab.ApiKeys -> AdminApiKeysTab(scope)
                    AdminTab.Providers -> AdminProvidersTab(scope)
                    AdminTab.Sessions -> AdminSessionsTab(scope)
                    AdminTab.Database -> AdminDatabaseTab(scope)
                    AdminTab.System -> AdminSystemTab(scope)
                    AdminTab.Audit -> AdminAuditTab(scope)
                }
            }
        }
    }
}

@Composable
fun AdminFilesTab(scope: kotlinx.coroutines.CoroutineScope) {
    val ctx = LocalContext.current
    var currentPath by remember { mutableStateOf("") }
    var entries by remember { mutableStateOf<List<Map<String, Any>>>(emptyList()) }
    var fileContent by remember { mutableStateOf<String?>(null) }
    var editingFile by remember { mutableStateOf<String?>(null) }
    var editorText by remember { mutableStateOf("") }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(currentPath) {
        loading = true
        adminClient.getFiles(currentPath).onSuccess { json ->
            val arr = json.getAsJsonArray("entries")
            entries = arr?.map { it.asJsonObject.entrySet().associate { e -> e.key to (e.value.asString ?: e.value.toString()) } } ?: emptyList()
        }.onFailure { entries = emptyList() }
        loading = false
    }

    Column(Modifier.fillMaxSize().padding(8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(bottom = 4.dp)) {
            Text("~", fontSize = 12.sp, color = MaterialTheme.colorScheme.primary, modifier = Modifier.clickable { currentPath = "" })
            currentPath.split("/").filter { it.isNotEmpty() }.forEach { part ->
                Text(" › ", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(part, fontSize = 12.sp, color = MaterialTheme.colorScheme.primary, modifier = Modifier.clickable {
                    val idx = currentPath.split("/").indexOf(part)
                    currentPath = currentPath.split("/").take(idx + 1).joinToString("/")
                })
            }
        }
        if (loading) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("Loading...", color = MaterialTheme.colorScheme.onSurfaceVariant) }
        } else if (fileContent != null) {
            TextField(
                value = editorText, onValueChange = { editorText = it },
                modifier = Modifier.weight(1f).fillMaxWidth(),
                textStyle = LocalTextStyle.current.copy(fontFamily = FontFamily.Monospace, fontSize = 11.sp),
            )
            Row(Modifier.padding(top = 4.dp), horizontalArrangement = Arrangement.End) {
                OutlinedButton(onClick = { fileContent = null; editingFile = null }) { Text("Back", fontSize = 11.sp) }
                Spacer(Modifier.width(8.dp))
                Button(onClick = {
                    editingFile?.let { path ->
                        scope.launch {
                            adminClient.writeFile(path, editorText).onSuccess {
                                Toast.makeText(ctx, "Saved", Toast.LENGTH_SHORT).show()
                                fileContent = null; editingFile = null
                            }.onFailure {
                                Toast.makeText(ctx, "Save failed: ${it.message}", Toast.LENGTH_SHORT).show()
                            }
                        }
                    }
                }) { Text("Save", fontSize = 11.sp) }
            }
        } else {
            LazyColumn(modifier = Modifier.weight(1f)) {
                items(entries) { entry ->
                    val name = entry["name"] as? String ?: ""
                    val type = entry["type"] as? String ?: "file"
                    val icon = if (type == "dir") "📁" else "📄"
                    ListItem(
                        headlineContent = { Text(name, fontSize = 13.sp, fontFamily = FontFamily.Monospace) },
                        leadingContent = { Text(icon, fontSize = 16.sp) },
                        modifier = Modifier.clickable {
                            if (type == "dir") {
                                currentPath = if (currentPath.isEmpty()) name else "$currentPath/$name"
                            } else {
                                scope.launch {
                                    adminClient.readFile(if (currentPath.isEmpty()) name else "$currentPath/$name").onSuccess { json ->
                                        editingFile = if (currentPath.isEmpty()) name else "$currentPath/$name"
                                        editorText = json.get("content")?.asString ?: ""
                                        fileContent = ""
                                    }
                                }
                            }
                        }
                    )
                }
            }
        }
    }
}

@Composable
fun AdminConfigTab(scope: kotlinx.coroutines.CoroutineScope) {
    val ctx = LocalContext.current
    var config by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var loading by remember { mutableStateOf(true) }
    LaunchedEffect(Unit) {
        loading = true
        adminClient.getConfig().onSuccess { json ->
            val cfg = json.getAsJsonObject("config")
            config = cfg?.entrySet()?.associate { it.key to (it.value.asString ?: "") } ?: emptyMap()
        }
        loading = false
    }
    if (loading) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("Loading...") }
    } else {
        LazyColumn(Modifier.fillMaxSize().padding(8.dp)) {
            items(config.entries.toList()) { (key, value) ->
                val isSensitive = key.contains("KEY") || key.contains("SECRET")
                var editValue by remember { mutableStateOf(value) }
                Card(Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
                    Row(Modifier.padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(key, fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = MaterialTheme.colorScheme.primary)
                            OutlinedTextField(
                                value = editValue, onValueChange = { editValue = it },
                                singleLine = true, modifier = Modifier.fillMaxWidth(),
                                visualTransformation = if (isSensitive) androidx.compose.ui.text.input.PasswordVisualTransformation() else androidx.compose.ui.text.input.VisualTransformation.None,
                                textStyle = LocalTextStyle.current.copy(fontSize = 12.sp, fontFamily = FontFamily.Monospace)
                            )
                        }
                        Spacer(Modifier.width(8.dp))
                        IconButton(onClick = {
                            scope.launch {
                                adminClient.updateConfig(key, editValue).onSuccess {
                                    Toast.makeText(ctx, "$key updated", Toast.LENGTH_SHORT).show()
                                }.onFailure {
                                    Toast.makeText(ctx, "Failed: ${it.message}", Toast.LENGTH_SHORT).show()
                                }
                            }
                        }) { Icon(Icons.Default.Save, "Save", tint = MaterialTheme.colorScheme.primary) }
                    }
                }
            }
        }
    }
}

@Composable
fun AdminApiKeysTab(scope: kotlinx.coroutines.CoroutineScope) {
    val ctx = LocalContext.current
    var keys by remember { mutableStateOf<List<Map<String, Any>>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    LaunchedEffect(Unit) {
        loading = true
        adminClient.getApiKeys().onSuccess { json ->
            val arr = json.getAsJsonArray("keys")
            keys = arr?.map {
                val obj = it.asJsonObject
                obj.entrySet().associate { e -> e.key to (e.value.asString ?: e.value.toString()) }
            } ?: emptyList()
        }
        loading = false
    }
    if (loading) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("Loading...") }
    } else {
        LazyColumn(Modifier.fillMaxSize().padding(8.dp)) {
            items(keys) { k ->
                val provider = k["provider"] as? String ?: ""
                var keyVal by remember { mutableStateOf("") }
                Card(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                    Column(Modifier.padding(12.dp)) {
                        Text(provider.uppercase(), fontWeight = FontWeight.Bold, fontSize = 14.sp)
                        if (k.containsKey("key_env")) {
                            OutlinedTextField(
                                value = keyVal, onValueChange = { keyVal = it },
                                label = { Text(k["key_env"] as? String ?: "API Key") },
                                singleLine = true,
                                visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
                                modifier = Modifier.fillMaxWidth()
                            )
                        }
                        Spacer(Modifier.height(4.dp))
                        Button(onClick = {
                            scope.launch {
                                adminClient.updateApiKey(provider, keyVal).onSuccess {
                                    Toast.makeText(ctx, "Updated $provider", Toast.LENGTH_SHORT).show()
                                }.onFailure {
                                    Toast.makeText(ctx, "Failed: ${it.message}", Toast.LENGTH_SHORT).show()
                                }
                            }
                        }, modifier = Modifier.align(Alignment.End)) { Text("Update", fontSize = 11.sp) }
                    }
                }
            }
        }
    }
}

@Composable
fun AdminProvidersTab(scope: kotlinx.coroutines.CoroutineScope) {
    val ctx = LocalContext.current
    var providers by remember { mutableStateOf<List<Map<String, Any>>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    LaunchedEffect(Unit) {
        loading = true
        adminClient.getProviders().onSuccess { json ->
            val arr = json.getAsJsonArray("providers")
            providers = arr?.map { it.asJsonObject.entrySet().associate { e -> e.key to (it.asJsonObject.get(e.key)?.toString() ?: "") } } ?: emptyList()
        }
        loading = false
    }
    if (loading) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("Loading...") }
    } else {
        LazyColumn(Modifier.fillMaxSize().padding(8.dp)) {
            items(providers) { p ->
                Card(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                    Column(Modifier.padding(12.dp)) {
                        Text(p["name"] as? String ?: "", fontWeight = FontWeight.Bold, fontSize = 14.sp, color = MaterialTheme.colorScheme.primary)
                        Text(p["base_url"] as? String ?: "", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

@Composable
fun AdminSessionsTab(scope: kotlinx.coroutines.CoroutineScope) {
    val ctx = LocalContext.current
    var sessions by remember { mutableStateOf<List<Map<String, Any>>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var expandedId by remember { mutableStateOf<String?>(null) }
    var messages by remember { mutableStateOf<List<Map<String, Any>>>(emptyList()) }

    LaunchedEffect(Unit) {
        loading = true
        adminClient.getSessions().onSuccess { json ->
            val arr = json.getAsJsonArray("sessions")
            sessions = arr?.map {
                val obj = it.asJsonObject
                obj.entrySet().associate { e -> e.key to (obj.get(e.key)?.asString ?: obj.get(e.key)?.toString() ?: "") }
            } ?: emptyList()
        }
        loading = false
    }
    if (loading) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("Loading...") }
    } else {
        LazyColumn(Modifier.fillMaxSize().padding(8.dp)) {
            items(sessions) { s ->
                val sid = s["id"] as? String ?: ""
                Card(onClick = {
                    if (expandedId == sid) { expandedId = null } else {
                        expandedId = sid
                        scope.launch {
                            adminClient.getSessionMessages(sid).onSuccess { json ->
                                val arr = json.getAsJsonArray("messages")
                                messages = arr?.map {
                                    val obj = it.asJsonObject
                                    obj.entrySet().associate { e -> e.key to (obj.get(e.key)?.asString ?: "") }
                                } ?: emptyList()
                            }
                        }
                    }
                }, modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
                    Column(Modifier.padding(8.dp)) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("${s["message_count"] ?: "0"} msgs", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text((s["updated_at"] as? String)?.take(10) ?: "", fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Text((s["last_preview"] as? String)?.take(80) ?: "", fontSize = 12.sp, fontFamily = FontFamily.Monospace, maxLines = 1)
                        if (expandedId == sid) {
                            Divider(Modifier.padding(vertical = 4.dp))
                            messages.forEach { m ->
                                Text("[${m["role"]}] ${(m["content"] as? String)?.take(100)}", fontSize = 10.sp, fontFamily = FontFamily.Monospace, color = if (m["role"] == "user") Color(0xFF90CAF9) else MaterialTheme.colorScheme.primary)
                            }
                            Spacer(Modifier.height(4.dp))
                            OutlinedButton(onClick = {
                                scope.launch {
                                    adminClient.deleteSession(sid).onSuccess {
                                        Toast.makeText(ctx, "Session deleted", Toast.LENGTH_SHORT).show()
                                        expandedId = null
                                    }
                                }
                            }) { Text("Delete", fontSize = 10.sp, color = MaterialTheme.colorScheme.error) }
                        }
                    }
                }
            }
        }
    }
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
fun AdminDatabaseTab(scope: kotlinx.coroutines.CoroutineScope) {
    var result by remember { mutableStateOf("Select a collection") }
    var selectedCol by remember { mutableStateOf("queries") }
    val ctx = LocalContext.current
    Column(Modifier.fillMaxSize().padding(8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            var expanded by remember { mutableStateOf(false) }
            ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
                OutlinedTextField(
                    value = selectedCol, onValueChange = {},
                    readOnly = true, modifier = Modifier.menuAnchor().weight(1f),
                    label = { Text("Collection") }, trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) }
                )
                ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                    listOf("queries", "cache", "profile", "admin_audit").forEach { col ->
                        DropdownMenuItem(text = { Text(col) }, onClick = { selectedCol = col; expanded = false })
                    }
                }
            }
            Spacer(Modifier.width(8.dp))
            Button(onClick = {
                scope.launch {
                    adminClient.queryDb(selectedCol).onSuccess { json ->
                        result = Gson().toJson(json.get("results"))
                    }.onFailure {
                        result = "Error: ${it.message}"
                    }
                }
            }) { Text("Query") }
        }
        Spacer(Modifier.height(8.dp))
        Text(result, fontSize = 10.sp, fontFamily = FontFamily.Monospace, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun AdminSystemTab(scope: kotlinx.coroutines.CoroutineScope) {
    var info by remember { mutableStateOf<Map<String, Any>>(emptyMap()) }
    var loading by remember { mutableStateOf(true) }
    LaunchedEffect(Unit) {
        loading = true
        adminClient.getSystemInfo().onSuccess { json ->
            info = json.entrySet().associate { it.key to (it.value.asString ?: it.value.toString()) }
        }
        loading = false
    }
    if (loading) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("Loading...") }
    } else {
        LazyColumn(Modifier.fillMaxSize().padding(8.dp)) {
            items(info.entries.take(15).toList()) { (key, value) ->
                Card(Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
                    Row(Modifier.padding(8.dp)) {
                        Text("$key: ", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                        Text(value.toString(), fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

@Composable
fun AdminAuditTab(scope: kotlinx.coroutines.CoroutineScope) {
    var entries by remember { mutableStateOf<List<Map<String, Any>>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    LaunchedEffect(Unit) {
        loading = true
        adminClient.getAuditLog().onSuccess { json ->
            val arr = json.getAsJsonArray("log")
            entries = arr?.map {
                val obj = it.asJsonObject
                obj.entrySet().associate { e -> e.key to (obj.get(e.key)?.asString ?: obj.get(e.key)?.toString() ?: "") }
            } ?: emptyList()
        }
        loading = false
    }
    if (loading) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("Loading...") }
    } else {
        LazyColumn(Modifier.fillMaxSize().padding(8.dp)) {
            items(entries) { entry ->
                Card(Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
                    Column(Modifier.padding(8.dp)) {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(entry["action"] as? String ?: "", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                            Text(entry["ip"] as? String ?: "", fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Text(entry["details"] as? String ?: "", fontSize = 11.sp, fontFamily = FontFamily.Monospace)
                    }
                }
            }
        }
    }
}
