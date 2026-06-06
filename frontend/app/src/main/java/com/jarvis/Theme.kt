package com.jarvis

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

// ─── Flask Crystal UI Colors ────────────────────────────────
object CrystalColors {
    val background = Color(0xFF050201)       // deep black-orange
    val surface = Color(0xFF0A0808)          // near-black
    val surfaceLight = Color(0xFF1A0F0A)     // dark warm surface
    val flameOrange = Color(0xFFFF6B35)      // primary accent
    val cyan = Color(0xFF00E5FF)             // status / secondary
    val amber = Color(0xFFFFBF00)            // warm gold
    val warmWhite = Color(0xFFFFE4B5)        // text
    val redGlow = Color(0xFFFF4444)          // listening state
    val blueGlow = Color(0xFF00D4FF)         // processing state
    val dimText = Color(0xFF8A7A6A)          // muted text
    val orbIdle = Color(0xFF00E5FF)          // idle glow
    val orbListening = Color(0xFFFF4444)     // listening glow
    val orbProcessing = Color(0xFF00D4FF)    // processing glow
}

private val DarkColorScheme = darkColorScheme(
    primary = CrystalColors.flameOrange,
    onPrimary = CrystalColors.background,
    primaryContainer = Color(0xFF1A0A00),
    onPrimaryContainer = CrystalColors.warmWhite,
    secondary = CrystalColors.cyan,
    onSecondary = CrystalColors.background,
    secondaryContainer = Color(0xFF00333D),
    onSecondaryContainer = CrystalColors.cyan,
    tertiary = CrystalColors.amber,
    surface = CrystalColors.surface,
    onSurface = CrystalColors.warmWhite,
    surfaceVariant = CrystalColors.surfaceLight,
    onSurfaceVariant = CrystalColors.dimText,
    background = CrystalColors.background,
    onBackground = CrystalColors.warmWhite,
    error = CrystalColors.redGlow,
    onError = CrystalColors.background,
    errorContainer = Color(0xFF3D0000),
    outline = Color(0xFF3D2A1A),
    outlineVariant = Color(0xFF2D1A0A),
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
