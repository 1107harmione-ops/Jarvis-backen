package com.jarvis

import android.content.Context
import android.location.Location
import android.location.LocationManager
import android.util.Log

object LocationProvider {
    private const val TAG = "JarvisLocation"

    data class LocationResult(
        val latitude: Double,
        val longitude: Double,
        val provider: String = "unknown"
    )

    fun getLastKnownLocation(context: Context): LocationResult? {
        try {
            val lm = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
            val gps = lm.getLastKnownLocation(LocationManager.GPS_PROVIDER)
            if (gps != null) return LocationResult(gps.latitude, gps.longitude, "gps")
            val network = lm.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
            if (network != null) return LocationResult(network.latitude, network.longitude, "network")
            return null
        } catch (e: Exception) {
            Log.e(TAG, "Location error", e)
            return null
        }
    }
}
