package com.jarvis

import androidx.compose.animation.*
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

enum class Screen(
    val title: String,
    val selectedIcon: ImageVector,
    val unselectedIcon: ImageVector
) {
    CHAT("Voice", Icons.Filled.Mic, Icons.Outlined.Mic),
    MEMORY("Memory", Icons.Filled.History, Icons.Outlined.History),
    SKILLS("Skills", Icons.Filled.Extension, Icons.Outlined.Extension),
    SETTINGS("Settings", Icons.Filled.Settings, Icons.Outlined.Settings),
    DASHBOARD("Dashboard", Icons.Filled.Dashboard, Icons.Outlined.Dashboard),
    ADMIN("Admin", Icons.Filled.Security, Icons.Outlined.Security),
}

object AppState {
    var wsClient: WebSocketClient? = null
    var mainActivity: MainActivity? = null
}

@Composable
fun JarvisBottomNav(
    currentScreen: Screen,
    onScreenSelected: (Screen) -> Unit,
    showAdmin: Boolean = false
) {
    val entries = if (showAdmin) Screen.entries else Screen.entries.filter { it != Screen.ADMIN }
    NavigationBar(
        tonalElevation = 8.dp,
        containerColor = MaterialTheme.colorScheme.surface
    ) {
        entries.forEach { screen ->
            NavigationBarItem(
                icon = {
                    Icon(
                        imageVector = if (currentScreen == screen) screen.selectedIcon else screen.unselectedIcon,
                        contentDescription = screen.title
                    )
                },
                label = { Text(screen.title, fontSize = 11.sp) },
                selected = currentScreen == screen,
                onClick = { onScreenSelected(screen) },
                colors = NavigationBarItemDefaults.colors(
                    selectedIconColor = MaterialTheme.colorScheme.primary,
                    selectedTextColor = MaterialTheme.colorScheme.primary,
                    indicatorColor = MaterialTheme.colorScheme.primaryContainer
                )
            )
        }
    }
}

@Composable
fun AnimatedScreen(
    currentScreen: Screen,
    chat: @Composable () -> Unit,
    memory: @Composable () -> Unit,
    skills: @Composable () -> Unit,
    settings: @Composable () -> Unit,
    dashboard: @Composable () -> Unit,
    admin: @Composable () -> Unit = {}
) {
    AnimatedContent(
        targetState = currentScreen,
        transitionSpec = {
            fadeIn(animationSpec = tween(300)) togetherWith
                fadeOut(animationSpec = tween(300))
        },
        label = "screen_transition"
    ) { screen ->
        when (screen) {
            Screen.CHAT -> chat()
            Screen.MEMORY -> memory()
            Screen.SKILLS -> skills()
            Screen.SETTINGS -> settings()
            Screen.DASHBOARD -> dashboard()
            Screen.ADMIN -> admin()
        }
    }
}
