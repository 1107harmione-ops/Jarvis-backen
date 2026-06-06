package com.jarvis

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationManager
import android.util.Log
import android.os.Looper
import androidx.core.content.ContextCompat
import android.location.LocationListener

object LocationProvider {
    private const val TAG = "JarvisLocation"

    data class LocationResult(
        val latitude: Double,
        val longitude: Double,
        val provider: String = "unknown"
    )

    private fun hasPermission(context: Context): Boolean {
        return ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
               ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
    }

    fun getLastKnownLocation(context: Context): LocationResult? {
        if (!hasPermission(context)) {
            Log.w(TAG, "Location permission not granted")
            return null
        }
        try {
            val lm = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager

            // Try GPS first
            val gps = lm.getLastKnownLocation(LocationManager.GPS_PROVIDER)
            if (gps != null && isFresh(gps)) {
                return LocationResult(gps.latitude, gps.longitude, "gps")
            }

            // Fall back to network
            val network = lm.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
            if (network != null && isFresh(network)) {
                return LocationResult(network.latitude, network.longitude, "network")
            }

            // Use best available even if stale (better than null)
            val allProviders = listOf(
                gps?.let { LocationResult(it.latitude, it.longitude, "gps") },
                network?.let { LocationResult(it.latitude, it.longitude, "network") }
            ).filterNotNull()

            return allProviders.firstOrNull()
        } catch (e: SecurityException) {
            Log.e(TAG, "Location permission denied at runtime", e)
            return null
        } catch (e: Exception) {
            Log.e(TAG, "Location error", e)
            return null
        }
    }

    private fun isFresh(location: Location, maxAgeMs: Long = 5 * 60 * 1000): Boolean {
        return (System.currentTimeMillis() - location.time) < maxAgeMs
    }
}
