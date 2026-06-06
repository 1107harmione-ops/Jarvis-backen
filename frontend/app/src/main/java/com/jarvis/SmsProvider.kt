package com.jarvis

import android.Manifest
import android.content.ContentValues
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Telephony
import androidx.core.content.ContextCompat
import java.util.Date

object SmsProvider {
    data class SmsMessage(val address: String, val body: String, val date: Date, val isRead: Boolean)

    private fun hasSmsPermission(context: Context): Boolean {
        return ContextCompat.checkSelfPermission(context, Manifest.permission.READ_SMS) == PackageManager.PERMISSION_GRANTED &&
               ContextCompat.checkSelfPermission(context, Manifest.permission.SEND_SMS) == PackageManager.PERMISSION_GRANTED
    }

    private fun hasReadSmsPermission(context: Context): Boolean {
        return ContextCompat.checkSelfPermission(context, Manifest.permission.READ_SMS) == PackageManager.PERMISSION_GRANTED
    }

    fun send(context: Context, phone: String, text: String): Boolean {
        if (!hasSmsPermission(context)) return false
        try {
            val values = ContentValues().apply {
                put(Telephony.Sms.Sent.ADDRESS, phone)
                put(Telephony.Sms.Sent.BODY, text)
            }
            context.contentResolver.insert(Telephony.Sms.Sent.CONTENT_URI, values)
            return true
        } catch (_: Exception) {
            return false
        }
    }

    fun readLatest(context: Context, limit: Int = 5): List<SmsMessage> {
        if (!hasReadSmsPermission(context)) return emptyList()
        val messages = mutableListOf<SmsMessage>()
        try {
            val sortOrder = "${Telephony.Sms.Inbox.DATE} DESC"
            context.contentResolver.query(
                Telephony.Sms.Inbox.CONTENT_URI,
                null, null, null,
                sortOrder
            )?.use { cursor ->
                var count = 0
                while (cursor.moveToNext() && count < limit) {
                    val addr = cursor.getString(cursor.getColumnIndexOrThrow(Telephony.Sms.Inbox.ADDRESS))
                    val body = cursor.getString(cursor.getColumnIndexOrThrow(Telephony.Sms.Inbox.BODY))
                    val date = Date(cursor.getLong(cursor.getColumnIndexOrThrow(Telephony.Sms.Inbox.DATE)))
                    val read = cursor.getInt(cursor.getColumnIndexOrThrow(Telephony.Sms.Inbox.READ)) == 1
                    messages.add(SmsMessage(addr, body, date, read))
                    count++
                }
            }
        } catch (_: Exception) {}
        return messages
    }
}
