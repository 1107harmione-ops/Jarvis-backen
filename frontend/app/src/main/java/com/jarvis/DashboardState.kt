package com.jarvis

import androidx.compose.runtime.mutableStateOf

data class MemoryEntry(
    val speaker: String = "",
    val message: String = "",
    val intent: String = "",
    val timestamp: String = "",
)

data class SkillEntry(
    val name: String = "",
    val trigger: String = "",
    val stepsCount: Int = 0,
    val successCount: Int = 0,
    val failCount: Int = 0,
    val autoCreated: Boolean = false,
)

data class SystemPermission(
    val name: String,
    val granted: Boolean,
    val risk: String,
    val description: String,
)

data class DashboardInfo(
    val version: String = "",
    val battery: String = "",
    val cpu: String = "",
    val memoryUsed: String = "",
    val memoryTotal: String = "",
    val personalizationScore: Double = 0.0,
    val personalizationLevel: String = "",
    val permissions: Map<String, Boolean> = emptyMap(),
    val riskSummary: Map<String, Int> = emptyMap(),
)

object DashboardState {
    val memoryEntries = mutableStateOf<List<MemoryEntry>>(emptyList())
    val memoryQuery = mutableStateOf("")
    val memoryLoading = mutableStateOf(false)
    val memoryTab = mutableStateOf("history")

    val skillEntries = mutableStateOf<List<SkillEntry>>(emptyList())
    val skillsLoading = mutableStateOf(false)

    val dashboardInfo = mutableStateOf(DashboardInfo())
    val dashboardLoading = mutableStateOf(false)
}