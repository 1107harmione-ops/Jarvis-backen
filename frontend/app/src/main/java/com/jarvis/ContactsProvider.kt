package com.jarvis

import android.Manifest
import android.content.ContentResolver
import android.content.Context
import android.content.pm.PackageManager
import android.database.Cursor
import android.net.Uri
import android.provider.ContactsContract
import androidx.core.content.ContextCompat

object ContactsProvider {
    data class Contact(val name: String, val phone: String, val email: String = "")

    private fun hasPermission(context: Context): Boolean {
        return ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED
    }

    fun search(context: Context, query: String): List<Contact> {
        if (!hasPermission(context)) return emptyList()
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
