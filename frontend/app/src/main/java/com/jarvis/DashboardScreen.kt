package com.jarvis

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun DashboardScreen() {
    val wsClient = AppState.wsClient
    val info = DashboardState.dashboardInfo.value
    val isLoading = DashboardState.dashboardLoading.value
    val scrollState = rememberScrollState()

    LaunchedEffect(Unit) {
        DashboardState.dashboardLoading.value = true
        wsClient?.queryDashboard()
    }

    Column(
        modifier = Modifier.fillMaxSize()
            .verticalScroll(scrollState)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("System Dashboard", fontSize = 22.sp, fontWeight = FontWeight.Bold)
            IconButton(onClick = {
                DashboardState.dashboardLoading.value = true
                wsClient?.queryDashboard()
            }) {
                Icon(Icons.Filled.Refresh, contentDescription = "Refresh")
            }
        }

        if (isLoading && info.version.isEmpty()) {
            Box(modifier = Modifier.fillMaxWidth().height(200.dp), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        } else {
                DashboardCard("Personalization") {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Filled.Person, contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(32.dp))
                        Spacer(Modifier.width(12.dp))
                        Column {
                            Text("${info.personalizationScore}%", fontSize = 24.sp, fontWeight = FontWeight.Bold)
                            Text(info.personalizationLevel.replace("_", " "),
                                fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }

                DashboardCard("System") {
                    InfoRow("Version", info.version)
                    InfoRow("Battery", info.battery.ifEmpty { "—" })
                    InfoRow("CPU", info.cpu.ifEmpty { "—" })
                    if (info.memoryUsed.isNotEmpty()) {
                        InfoRow("Memory", "${info.memoryUsed} / ${info.memoryTotal}")
                    }
                }

                DashboardCard("Permissions") {
                    if (info.permissions.isEmpty()) {
                        Text("No permission data", fontSize = 13.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    } else {
                        info.permissions.forEach { (name, granted) ->
                            Row(
                                modifier = Modifier.fillMaxWidth().padding(vertical = 3.dp),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(name.replace("_", " "), fontSize = 13.sp)
                                Surface(
                                    modifier = Modifier.size(10.dp),
                                    shape = RoundedCornerShape(5.dp),
                                    color = if (granted) Color(0xFF4CAF50) else Color(0xFF9E9E9E)
                                ) {}
                            }
                        }
                    }
                    if (info.riskSummary.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Text("Risks:", fontSize = 11.sp, fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                        info.riskSummary.forEach { (level, count) ->
                            Text("  $level: $count", fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }

            Spacer(Modifier.height(16.dp))
            Text("JARVIS v${info.version.ifEmpty { "3.0" }} • Cloud Hosted",
                fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.fillMaxWidth(),
                textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        }
}

@Composable
fun DashboardCard(title: String, content: @Composable ColumnScope.() -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        tonalElevation = 2.dp
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Text(title, fontWeight = FontWeight.Bold, fontSize = 14.sp,
                color = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.height(8.dp))
            content()
        }
    }
}

@Composable
fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(label, fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, fontSize = 13.sp, fontWeight = FontWeight.Medium)
    }
}