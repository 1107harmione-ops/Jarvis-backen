package com.jarvis

import android.widget.Toast
import androidx.compose.animation.*
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProvidersScreen() {
    val ctx = LocalContext.current
    val wsClient = AppState.wsClient
    val providers = remember { ProviderManager.providers }
    var expandedId by remember { mutableStateOf<String?>(null) }
    var showAddDialog by remember { mutableStateOf(false) }
    var searchQuery by remember { mutableStateOf("") }

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
                Text("AI Providers", fontSize = 18.sp, fontWeight = FontWeight.Bold)
                Text("${providers.size} configured",
                    fontSize = 12.sp, color = MaterialTheme.colorScheme.onPrimaryContainer)
            }
        }

        if (providers.isEmpty()) {
            Box(modifier = Modifier.weight(1f), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("🤖", fontSize = 48.sp)
                    Spacer(Modifier.height(12.dp))
                    Text("No providers configured", fontSize = 16.sp, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(4.dp))
                    Text("Add a provider to use cloud AI models.\nDefault: Local (Offline)",
                        fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center)
                }
            }
        } else {
            LazyColumn(
                modifier = Modifier.weight(1f),
                contentPadding = PaddingValues(8.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                items(providers) { provider ->
                    ProviderCard(
                        provider = provider,
                        isExpanded = expandedId == provider.id,
                        onToggle = { ProviderManager.toggleProvider(provider.id) },
                        onExpand = { expandedId = if (expandedId == provider.id) null else provider.id },
                        onKeyChange = { key -> ProviderManager.updateProviderKey(provider.id, key) },
                        onModelChange = { model -> ProviderManager.updateProviderModel(provider.id, model) },
                        onRemove = { ProviderManager.removeProvider(provider.id) },
                    )
                }
            }
        }

        // Bottom bar
        Surface(modifier = Modifier.fillMaxWidth(), tonalElevation = 8.dp) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(
                    onClick = { showAddDialog = true },
                    modifier = Modifier.weight(1f)
                ) { Text("+ Add Provider") }
                Button(
                    onClick = {
                        wsClient?.sendText(ProviderManager.toServerConfig(), intent = "PROVIDER_CONFIG")
                        Toast.makeText(ctx, "Config sent to server", Toast.LENGTH_SHORT).show()
                    },
                    modifier = Modifier.weight(1f)
                ) { Text("Send Config") }
            }
        }
    }

    // Add Provider Dialog
    if (showAddDialog) {
        AddProviderDialog(
            searchQuery = searchQuery,
            onQueryChange = { searchQuery = it },
            onSelect = { id ->
                ProviderManager.addPresetById(id)
                showAddDialog = false
                searchQuery = ""
                Toast.makeText(ctx, "Provider added", Toast.LENGTH_SHORT).show()
            },
            onDismiss = {
                showAddDialog = false
                searchQuery = ""
            }
        )
    }
}

@Composable
fun ProviderCard(
    provider: AiProvider,
    isExpanded: Boolean,
    onToggle: () -> Unit,
    onExpand: () -> Unit,
    onKeyChange: (String) -> Unit,
    onModelChange: (String) -> Unit,
    onRemove: () -> Unit,
) {
    val activeProvider = ProviderManager.getActiveProvider()
    val isActive = activeProvider?.id == provider.id
    val formatIcon = when (provider.apiFormat) {
        ApiFormat.OPENAI_COMPAT -> "🔌"
        ApiFormat.ANTHROPIC -> "🟢"
        ApiFormat.GOOGLE -> "🔵"
        ApiFormat.LOCAL -> "💻"
        ApiFormat.COHERE -> "🟣"
        ApiFormat.REPLICATE -> "🔁"
        ApiFormat.HUGGINGFACE -> "🤗"
    }

    var apiKeyVisible by remember { mutableStateOf(false) }
    var apiKey by remember(provider.apiKey) { mutableStateOf(provider.apiKey) }
    var selectedModel by remember(provider.defaultModel) { mutableStateOf(provider.defaultModel) }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        color = if (isActive) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f)
                else MaterialTheme.colorScheme.surfaceVariant,
        tonalElevation = 2.dp
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            // Header row
            Row(
                modifier = Modifier.fillMaxWidth().clickable { onExpand() },
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(formatIcon, fontSize = 20.sp)
                    Spacer(Modifier.width(8.dp))
                    Column {
                        Text(provider.name, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                        Text(provider.defaultModel, fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (isActive) {
                        Surface(
                            shape = RoundedCornerShape(4.dp),
                            color = Color(0xFF4CAF50)
                        ) {
                            Text("ACTIVE", modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                fontSize = 9.sp, color = Color.White)
                        }
                        Spacer(Modifier.width(8.dp))
                    }
                    Switch(
                        checked = provider.enabled,
                        onCheckedChange = { onToggle() }
                    )
                }
            }

            // Expanded detail
            AnimatedVisibility(visible = isExpanded) {
                Column(modifier = Modifier.padding(top = 12.dp)) {
                    HorizontalDivider()
                    Spacer(Modifier.height(12.dp))

                    // API Key
                    Text("API Key", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(4.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        OutlinedTextField(
                            value = apiKey,
                            onValueChange = { apiKey = it; onKeyChange(it) },
                            modifier = Modifier.weight(1f),
                            placeholder = { Text("sk-...", fontSize = 13.sp) },
                            singleLine = true,
                            visualTransformation = if (apiKeyVisible) VisualTransformation.None
                                                    else PasswordVisualTransformation(),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                            textStyle = LocalTextStyle.current.copy(fontSize = 13.sp)
                        )
                        Spacer(Modifier.width(4.dp))
                        TextButton(onClick = { apiKeyVisible = !apiKeyVisible }) {
                            Text(if (apiKeyVisible) "Hide" else "Show", fontSize = 11.sp)
                        }
                    }

                    // Model selection
                    if (provider.models.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Text("Model", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(4.dp))
                        provider.models.forEach { model ->
                            Row(
                                modifier = Modifier.fillMaxWidth().clickable {
                                    selectedModel = model.id
                                    onModelChange(model.id)
                                }.padding(vertical = 4.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                RadioButton(
                                    selected = selectedModel == model.id,
                                    onClick = {
                                        selectedModel = model.id
                                        onModelChange(model.id)
                                    }
                                )
                                Spacer(Modifier.width(4.dp))
                                Column {
                                    Text(model.name, fontSize = 13.sp)
                                    if (model.description.isNotEmpty()) {
                                        Text(model.description, fontSize = 10.sp,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                }
                                Spacer(Modifier.weight(1f))
                                if (model.isFree) {
                                    Surface(
                                        shape = RoundedCornerShape(4.dp),
                                        color = Color(0xFF4CAF50).copy(alpha = 0.2f)
                                    ) {
                                        Text("FREE", modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                            fontSize = 9.sp, color = Color(0xFF4CAF50))
                                    }
                                }
                            }
                        }
                    }

                    // Remove
                    Spacer(Modifier.height(8.dp))
                    TextButton(
                        onClick = onRemove,
                        modifier = Modifier.align(Alignment.End)
                    ) {
                        Text("Remove Provider", color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddProviderDialog(
    searchQuery: String,
    onQueryChange: (String) -> Unit,
    onSelect: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    val presets = remember { ProviderDefaults.PRESETS }
    val filtered = remember(searchQuery) {
        if (searchQuery.isBlank()) presets
        else presets.filter {
            it.name.contains(searchQuery, ignoreCase = true) ||
            it.id.contains(searchQuery, ignoreCase = true)
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Add Provider", fontWeight = FontWeight.Bold) },
        text = {
            Column {
                OutlinedTextField(
                    value = searchQuery,
                    onValueChange = onQueryChange,
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("Search providers...") },
                    singleLine = true,
                    leadingIcon = { Text("🔍", fontSize = 16.sp) }
                )
                Spacer(Modifier.height(8.dp))
                Text("${filtered.size} of ${presets.size} providers",
                    fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(4.dp))

                LazyColumn(modifier = Modifier.heightIn(max = 400.dp)) {
                    items(filtered) { preset ->
                        Surface(
                            modifier = Modifier.fillMaxWidth().clickable { onSelect(preset.id) },
                            shape = RoundedCornerShape(8.dp),
                        ) {
                            Row(
                                modifier = Modifier.padding(vertical = 8.dp, horizontal = 8.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(preset.name, fontSize = 14.sp)
                                    Text(preset.apiFormat.label, fontSize = 11.sp,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                                val freeCount = preset.models.count { it.isFree }
                                if (freeCount > 0) {
                                    Text("$freeCount free", fontSize = 11.sp,
                                        color = Color(0xFF4CAF50))
                                }
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        }
    )
}
