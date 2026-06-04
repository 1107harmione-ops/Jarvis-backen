package com.jarvis

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat

object PermissionsHelper {
    data class PermissionGroup(
        val name: String,
        val permissions: List<String>,
        val description: String,
        val icon: String = "⚙"
    )

    val ALL_GROUPS = listOf(
        PermissionGroup("Microphone", listOf(Manifest.permission.RECORD_AUDIO), "Voice commands", "🎤"),
        PermissionGroup("Camera", listOf(Manifest.permission.CAMERA), "Photos & QR scanning", "📷"),
        PermissionGroup("Location", listOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION
        ), "Location-aware commands", "📍"),
        PermissionGroup("Contacts", listOf(Manifest.permission.READ_CONTACTS), "Access contacts", "👤"),
        PermissionGroup("SMS", listOf(
            Manifest.permission.SEND_SMS,
            Manifest.permission.READ_SMS,
            Manifest.permission.RECEIVE_SMS
        ), "Send & read messages", "💬"),
        PermissionGroup("Calendar", listOf(
            Manifest.permission.READ_CALENDAR,
            Manifest.permission.WRITE_CALENDAR
        ), "Calendar events", "📅"),
        PermissionGroup("Notifications", listOf(Manifest.permission.POST_NOTIFICATIONS), "Show notifications", "🔔"),
        PermissionGroup("Storage", listOf(
            Manifest.permission.READ_EXTERNAL_STORAGE,
            Manifest.permission.WRITE_EXTERNAL_STORAGE
        ), "File access", "📁"),
    )

    fun isGranted(activity: Activity, permission: String): Boolean {
        return ContextCompat.checkSelfPermission(activity, permission) == PackageManager.PERMISSION_GRANTED
    }

    fun allGranted(activity: Activity, group: PermissionGroup): Boolean {
        return group.permissions.all { isGranted(activity, it) }
    }

    fun grantedPermissions(activity: Activity): Map<String, Boolean> {
        return ALL_GROUPS.associate { g -> g.name to allGranted(activity, g) }
    }
}
