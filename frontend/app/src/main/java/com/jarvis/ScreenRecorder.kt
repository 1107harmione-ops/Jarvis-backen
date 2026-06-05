package com.jarvis

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.media.MediaRecorder
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Environment
import android.util.Log
import android.widget.Toast
import java.io.File
import java.text.SimpleDateFormat
import java.util.*

object ScreenRecorder {
    private const val TAG = "JarvisScreenRec"
    private var mediaRecorder: MediaRecorder? = null
    private var isRecording = false
    private var outputFile: File? = null

    fun isRecording() = isRecording

    fun createOutputFile(context: Context): File {
        val timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())
        val dir = context.getExternalFilesDir(Environment.DIRECTORY_MOVIES)
        return File(dir, "JARVIS_Screen_$timeStamp.mp4")
    }

    fun startRecording(context: Context, projectionIntent: Intent): Boolean {
        if (isRecording) return false
        return try {
            val file = createOutputFile(context)
            outputFile = file
            val mpm = context.getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
            mediaRecorder = MediaRecorder().apply {
                setAudioSource(MediaRecorder.AudioSource.VOICE_RECOGNITION)
                setVideoSource(MediaRecorder.VideoSource.SURFACE)
                setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
                setOutputFile(file.absolutePath)
                setVideoSize(1080, 1920)
                setVideoEncoder(MediaRecorder.VideoEncoder.H264)
                setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
                setVideoEncodingBitRate(5_000_000)
                setVideoFrameRate(30)
                prepare()
            }
            isRecording = true
            Log.d(TAG, "Recording started: ${file.absolutePath}")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start recording", e)
            false
        }
    }

    fun stopRecording(): File? {
        if (!isRecording) return null
        return try {
            mediaRecorder?.apply { stop(); release() }
            isRecording = false
            outputFile?.also { Log.d(TAG, "Recording saved: ${it.absolutePath}") }
        } catch (e: Exception) {
            Log.e(TAG, "Stop recording error", e)
            null
        } finally {
            mediaRecorder = null
        }
    }
}
