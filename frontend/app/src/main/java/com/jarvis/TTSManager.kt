package com.jarvis

import android.content.Context
import android.speech.tts.TextToSpeech
import android.util.Log
import java.util.Locale

/**
 * Manages Text-to-Speech (TTS) for the app.
 * Initialises lazily and provides a simple speak() interface.
 * Queues speech requests that arrive before the engine is ready.
 */
class TTSManager(
    private val context: Context
) : TextToSpeech.OnInitListener {

    private var tts: TextToSpeech? = null
    private var ready = false
    private val pendingTexts = java.util.Collections.synchronizedList(mutableListOf<String>())

    init {
        tts = TextToSpeech(context, this)
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            ready = true
            val result = tts?.isLanguageAvailable(Locale.US) ?: TextToSpeech.LANG_NOT_SUPPORTED
            if (result >= TextToSpeech.LANG_AVAILABLE) {
                tts?.language = Locale.US
            } else {
                Log.w(TAG, "Locale.US not available (result=$result), using default")
            }
            // Flush any texts that were queued before init completed
            synchronized(pendingTexts) {
                pendingTexts.forEach { tts?.speak(it, TextToSpeech.QUEUE_ADD, null, "jarvis_${System.nanoTime()}") }
                pendingTexts.clear()
            }
            Log.d(TAG, "TTS engine ready — flushed pending queue")
        } else {
            Log.w(TAG, "TTS engine init failed: $status")
        }
    }

    fun speak(text: String) {
        if (!ready) {
            Log.d(TAG, "TTS not ready yet — queueing")
            pendingTexts.add(text)
            return
        }
        speakNow(text)
    }

    private fun speakNow(text: String) {
        Log.d(TAG, "TTS speak: $text")
        tts?.speak(
            text,
            TextToSpeech.QUEUE_ADD,
            null,
            "jarvis_${System.nanoTime()}"
        )
    }

    fun shutdown() {
        ready = false
        synchronized(pendingTexts) { pendingTexts.clear() }
        tts?.stop()
        tts?.shutdown()
        tts = null
        Log.d(TAG, "TTS shutdown")
    }

    companion object {
        private const val TAG = "JarvisTTS"
    }
}
