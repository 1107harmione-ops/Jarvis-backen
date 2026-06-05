package com.jarvis

import android.content.Context
import android.speech.tts.TextToSpeech
import android.util.Log
import java.util.Locale

/**
 * Manages Text-to-Speech (TTS) for the app.
 * Initialises lazily and provides a simple speak() interface.
 */
class TTSManager(
    private val context: Context
) : TextToSpeech.OnInitListener {

    private var tts: TextToSpeech? = null
    private var ready = false

    init {
        tts = TextToSpeech(context, this)
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            ready = true
            tts?.language = Locale.US
            Log.d(TAG, "TTS engine ready")
        } else {
            Log.w(TAG, "TTS engine init failed: $status")
        }
    }

    fun speak(text: String) {
        if (!ready) {
            Log.d(TAG, "TTS not ready yet — skipping speak")
            return
        }
        Log.d(TAG, "TTS speak: $text")
        tts?.speak(
            text,
            TextToSpeech.QUEUE_FLUSH,
            null,
            "jarvis_response"
        )
    }

    fun shutdown() {
        ready = false
        tts?.stop()
        tts?.shutdown()
        tts = null
        Log.d(TAG, "TTS shutdown")
    }

    companion object {
        private const val TAG = "JarvisTTS"
    }
}
