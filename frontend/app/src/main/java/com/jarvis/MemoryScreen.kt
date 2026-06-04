package com.jarvis

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MemoryScreen() {
    val wsClient = AppState.wsClient
    val entries = DashboardState.memoryEntries.value
    val isLoading = DashboardState.memoryLoading.value
    val activeTab = DashboardState.memoryTab.value
    val queryText = DashboardState.memoryQuery.value

    LaunchedEffect(Unit) {
        DashboardState.memoryLoading.value = true
        wsClient?.queryMemory("history", 50)
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Surface(
            modifier = Modifier.fillMaxWidth(),
            color = MaterialTheme.colorScheme.primaryContainer,
            tonalElevation = 4.dp
        ) {
            Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
                Text("Memory & History", fontSize = 20.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(4.dp))
                Text("${entries.size} entries", fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onPrimaryContainer)
            }
        }

        // Search bar
        OutlinedTextField(
            value = queryText,
            onValueChange = {
                DashboardState.memoryQuery.value = it
                wsClient?.queryMemory("facts", query = it)
            },
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
            placeholder = { Text("Search facts...") },
            leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
            singleLine = true,
            shape = RoundedCornerShape(24.dp)
        )

        // Tab selector
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            FilterChip(
                selected = activeTab == "history",
                onClick = {
                    DashboardState.memoryTab.value = "history"
                    DashboardState.memoryLoading.value = true
                    wsClient?.queryMemory("history", 50)
                },
                label = { Text("History") },
                leadingIcon = { Icon(Icons.Filled.History, contentDescription = null, modifier = Modifier.size(16.dp)) }
            )
            FilterChip(
                selected = activeTab == "facts",
                onClick = {
                    DashboardState.memoryTab.value = "facts"
                    wsClient?.queryMemory("facts")
                },
                label = { Text("Facts") },
                leadingIcon = { Icon(Icons.Filled.Info, contentDescription = null, modifier = Modifier.size(16.dp)) }
            )
        }

        Spacer(Modifier.height(8.dp))

        if (isLoading) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        } else if (entries.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("No memory entries yet.\nStart chatting to build memory.",
                    fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(horizontal = 12.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                items(entries) { entry ->
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(8.dp),
                        color = MaterialTheme.colorScheme.surfaceVariant,
                        tonalElevation = 1.dp
                    ) {
                        Column(modifier = Modifier.padding(10.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(entry.speaker, fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = MaterialTheme.colorScheme.primary)
                                Text(entry.timestamp.take(10), fontSize = 10.sp,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Spacer(Modifier.height(4.dp))
                            Text(entry.message, fontSize = 13.sp, maxLines = 3,
                                overflow = TextOverflow.Ellipsis)
                            if (entry.intent.isNotEmpty()) {
                                Text("intent: ${entry.intent}", fontSize = 10.sp,
                                    fontFamily = FontFamily.Monospace,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }
    }
}