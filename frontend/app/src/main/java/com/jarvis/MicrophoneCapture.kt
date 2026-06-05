package com.jarvis

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import android.util.Log
import java.io.File
import java.util.*

class MicrophoneCapture(private val context: Context) {
    private var recorder: MediaRecorder? = null
    private var isRecording = false
    private val outputDir = context.cacheDir

    data class AudioResult(val file: File, val durationMs: Long)

    fun startRecording(): Boolean {
        if (isRecording) return false
        val outputFile = File(outputDir, "jarvis_${UUID.randomUUID()}.m4a")
        return try {
            recorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                MediaRecorder(context)
            } else {
                @Suppress("DEPRECATION")
                MediaRecorder()
            }
            recorder?.apply {
                setAudioSource(MediaRecorder.AudioSource.VOICE_RECOGNITION)
                setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
                setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
                setAudioSamplingRate(16000)
                setAudioChannels(1)
                setAudioEncodingBitRate(64000)
                setOutputFile(outputFile.absolutePath)
                prepare()
                start()
            }
            isRecording = true
            Log.d(TAG, "Recording started: ${outputFile.absolutePath}")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start recording", e)
            false
        }
    }

    fun stopRecording(): AudioResult? {
        if (!isRecording) return null
        return try {
            recorder?.apply {
                stop()
                release()
            }
            isRecording = false
            val file = File(outputDir, "jarvis_last.wav")
            Log.d(TAG, "Recording stopped")
            AudioResult(file, 0L)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to stop recording", e)
            null
        } finally {
            recorder = null
        }
    }

    companion object {
        private const val TAG = "JarvisMic"
    }
}
