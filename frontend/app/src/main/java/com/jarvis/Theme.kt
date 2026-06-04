package com.jarvis

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val DarkColorScheme = darkColorScheme(
    primary = Color(0xFF90CAF9),
    onPrimary = Color(0xFF003258),
    primaryContainer = Color(0xFF00497D),
    onPrimaryContainer = Color(0xFFD1E4FF),
    secondary = Color(0xFF80DEEA),
    onSecondary = Color(0xFF00363A),
    secondaryContainer = Color(0xFF00505C),
    onSecondaryContainer = Color(0xFFB2EBF2),
    tertiary = Color(0xFFCE93D8),
    surface = Color(0xFF1A1A2E),
    onSurface = Color(0xFFE3E2E6),
    surfaceVariant = Color(0xFF2D2D44),
    onSurfaceVariant = Color(0xFFCAC4D0),
    background = Color(0xFF121218),
    onBackground = Color(0xFFE3E2E6),
    error = Color(0xFFFF5252),
    onError = Color(0xFF601410),
    errorContainer = Color(0xFF8C1D18),
    outline = Color(0xFF49454F),
    outlineVariant = Color(0xFF2D2D44),
)

private val LightColorScheme = lightColorScheme(
    primary = Color(0xFF1565C0),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD1E4FF),
    onPrimaryContainer = Color(0xFF001D36),
    secondary = Color(0xFF00838F),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFB2EBF2),
    onSecondaryContainer = Color(0xFF002022),
    tertiary = Color(0xFF7B1FA2),
    surface = Color(0xFFFAFAFE),
    onSurface = Color(0xFF1A1A2E),
    surfaceVariant = Color(0xFFE8E8F0),
    onSurfaceVariant = Color(0xFF49454F),
    background = Color(0xFFF5F5FA),
    onBackground = Color(0xFF1A1A2E),
    error = Color(0xFFD32F2F),
    onError = Color.White,
    errorContainer = Color(0xFFF9DEDC),
    outline = Color(0xFF79747E),
    outlineVariant = Color(0xFFCAC4D0),
)

@Composable
fun JarvisTheme(
    darkTheme: Boolean = when (SettingsManager.getThemeMode()) {
        "dark" -> true
        "light" -> false
        else -> isSystemInDarkTheme()
    },
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
        }
    }
    MaterialTheme(colorScheme = colorScheme, content = content)
}
