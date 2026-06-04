package com.jarvis

import android.content.ContentResolver
import android.content.Context
import android.database.Cursor
import android.net.Uri
import android.provider.ContactsContract

object ContactsProvider {
    data class Contact(val name: String, val phone: String, val email: String = "")

    fun search(context: Context, query: String): List<Contact> {
        val results = mutableListOf<Contact>()
        val cr: ContentResolver = context.contentResolver
        val uri: Uri = ContactsContract.CommonDataKinds.Phone.CONTENT_URI
        val projection = arrayOf(
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
            ContactsContract.CommonDataKinds.Phone.NUMBER,
        )
        val selection = "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} LIKE ?"
        val args = arrayOf("%$query%")
        try {
            cr.query(uri, projection, selection, args, null)?.use { cursor ->
                while (cursor.moveToNext()) {
                    val name = cursor.getString(0) ?: continue
                    val phone = cursor.getString(1) ?: ""
                    results.add(Contact(name, phone))
                }
            }
        } catch (_: Exception) {}
        return results
    }
}
