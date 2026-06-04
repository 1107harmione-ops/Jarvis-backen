package com.jarvis

import android.content.ContentValues
import android.content.Context
import android.provider.CalendarContract
import java.util.Date
import java.util.TimeZone

object CalendarProvider {
    data class CalendarEvent(
        val title: String,
        val startTime: Date,
        val location: String = "",
        val description: String = ""
    )

    fun getUpcoming(context: Context, days: Int = 7): List<CalendarEvent> {
        val events = mutableListOf<CalendarEvent>()
        val now = System.currentTimeMillis()
        val end = now + days * 24L * 60 * 60 * 1000
        try {
            context.contentResolver.query(
                CalendarContract.Events.CONTENT_URI,
                arrayOf(
                    CalendarContract.Events.TITLE,
                    CalendarContract.Events.DTSTART,
                    CalendarContract.Events.EVENT_LOCATION,
                    CalendarContract.Events.DESCRIPTION,
                ),
                "${CalendarContract.Events.DTSTART} >= ? AND ${CalendarContract.Events.DTSTART} <= ?",
                arrayOf(now.toString(), end.toString()),
                "${CalendarContract.Events.DTSTART} ASC"
            )?.use { cursor ->
                while (cursor.moveToNext()) {
                    val title = cursor.getString(0) ?: continue
                    val start = cursor.getLong(1)
                    val loc = cursor.getString(2) ?: ""
                    val desc = cursor.getString(3) ?: ""
                    events.add(CalendarEvent(title, Date(start), loc, desc))
                }
            }
        } catch (_: Exception) {}
        return events
    }

    fun createEvent(context: Context, title: String, startMs: Long, endMs: Long, location: String = ""): Boolean {
        try {
            val calId = _getPrimaryCalendarId(context) ?: return false
            val values = ContentValues().apply {
                put(CalendarContract.Events.DTSTART, startMs)
                put(CalendarContract.Events.DTEND, endMs)
                put(CalendarContract.Events.TITLE, title)
                put(CalendarContract.Events.EVENT_LOCATION, location)
                put(CalendarContract.Events.CALENDAR_ID, calId)
                put(CalendarContract.Events.EVENT_TIMEZONE, TimeZone.getDefault().id)
            }
            context.contentResolver.insert(CalendarContract.Events.CONTENT_URI, values)
            return true
        } catch (_: Exception) {
            return false
        }
    }

    private fun _getPrimaryCalendarId(context: Context): Long? {
        try {
            context.contentResolver.query(
                CalendarContract.Calendars.CONTENT_URI,
                arrayOf(CalendarContract.Calendars._ID),
                null, null, null
            )?.use { cursor ->
                if (cursor.moveToFirst()) return cursor.getLong(0)
            }
        } catch (_: Exception) {}
        return null
    }
}
