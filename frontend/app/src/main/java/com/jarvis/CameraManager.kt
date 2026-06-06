package com.jarvis

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Environment
import android.provider.MediaStore
import android.util.Log
import androidx.activity.result.ActivityResultLauncher
import androidx.core.content.FileProvider
import java.io.File
import java.text.SimpleDateFormat
import java.util.*

object CameraManager {
    private const val TAG = "JarvisCamera"
    private var photoFile: File? = null

    data class PhotoResult(val file: File, val uri: Uri)

    fun createPhotoFile(context: Context): File {
        val timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())
        val dir = context.getExternalFilesDir(Environment.DIRECTORY_PICTURES)
        return File(dir, "JARVIS_$timeStamp.jpg").also { photoFile = it }
    }

    fun getPhotoUri(context: Context): Uri {
        val file = photoFile ?: throw IllegalStateException("Call createPhotoFile() before getPhotoUri()")
        return FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
    }

    fun getLaunchIntent(context: Context): Intent {
        val file = createPhotoFile(context)
        return Intent(MediaStore.ACTION_IMAGE_CAPTURE).apply {
            putExtra(MediaStore.EXTRA_OUTPUT, getPhotoUri(context))
            addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        }
    }

    fun handleResult(data: Intent?): PhotoResult? {
        val file = photoFile ?: return null
        return if (file.exists()) PhotoResult(file, Uri.fromFile(file)) else null
    }
}
