package com.jarvis

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.provider.Telephony
import java.util.Date

object SmsProvider {
    data class SmsMessage(val address: String, val body: String, val date: Date, val isRead: Boolean)

    fun send(context: Context, phone: String, text: String): Boolean {
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
        val messages = mutableListOf<SmsMessage>()
        try {
            context.contentResolver.query(
                Telephony.Sms.Inbox.CONTENT_URI,
                null, null, null,
                "${Telephony.Sms.Inbox.DATE} DESC LIMIT $limit"
            )?.use { cursor ->
                while (cursor.moveToNext()) {
                    val addr = cursor.getString(cursor.getColumnIndexOrThrow(Telephony.Sms.Inbox.ADDRESS))
                    val body = cursor.getString(cursor.getColumnIndexOrThrow(Telephony.Sms.Inbox.BODY))
                    val date = Date(cursor.getLong(cursor.getColumnIndexOrThrow(Telephony.Sms.Inbox.DATE)))
                    val read = cursor.getInt(cursor.getColumnIndexOrThrow(Telephony.Sms.Inbox.READ)) == 1
                    messages.add(SmsMessage(addr, body, date, read))
                }
            }
        } catch (_: Exception) {}
        return messages
    }
}
