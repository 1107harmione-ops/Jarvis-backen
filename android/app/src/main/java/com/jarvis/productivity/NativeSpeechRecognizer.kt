package com.jarvis.productivity

import android.content.Context
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioTimestamp
import android.media.MediaRecorder
import android.media.audiofx.NoiseSuppressor
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.webkit.WebView
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.zip.ZipInputStream

class NativeSpeechRecognizer(
    private val context: Context,
    private val webView: WebView
) {
    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private var voskModel: Any? = null
    private var voskRecognizer: Any? = null
    private var audioRecord: AudioRecord? = null
    private var recordingThread: Thread? = null
    private var isListening = false
    private var modelReady = false
    private val mainHandler = Handler(Looper.getMainLooper())

    private val voskModelDir: File
        get() = File(context.filesDir, "vosk-model")

    fun isBluetoothConnected(): Boolean {
        return audioManager.isBluetoothScoOn || audioManager.isBluetoothA2dpOn
    }

    fun connectBluetoothSco(): Boolean {
        return try {
            if (!audioManager.isBluetoothScoAvailableOffCall) return false
            audioManager.startBluetoothSco()
            audioManager.isBluetoothScoOn = true
            true
        } catch (_: Exception) { false }
    }

    fun disconnectBluetoothSco() {
        try {
            audioManager.isBluetoothScoOn = false
            audioManager.stopBluetoothSco()
        } catch (_: Exception) {}
    }

    fun isModelDownloaded(): Boolean {
        return voskModelDir.exists() && voskModelDir.listFiles()?.isNotEmpty() == true
    }

    fun downloadModelIfNeeded(callback: (Boolean, String) -> Unit) {
        if (isModelDownloaded()) {
            callback(true, "Model ready")
            return
        }
        Thread {
            try {
                val url = URL("https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip")
                val conn = url.openConnection() as HttpURLConnection
                conn.connectTimeout = 15000
                conn.readTimeout = 30000
                conn.connect()
                val totalBytes = conn.contentLength
                val input = BufferedInputStream(conn.inputStream)
                val zis = ZipInputStream(input)
                var entry = zis.nextEntry
                val tempDir = File(context.cacheDir, "vosk_download")
                tempDir.mkdirs()
                while (entry != null) {
                    if (!entry.isDirectory) {
                        val file = File(tempDir, entry.name)
                        file.parentFile?.mkdirs()
                        FileOutputStream(file).use { fos ->
                            zis.copyTo(fos)
                        }
                    }
                    zis.closeEntry()
                    entry = zis.nextEntry
                }
                zis.close()
                input.close()
                voskModelDir.mkdirs()
                voskModelDir.deleteRecursively()
                tempDir.renameTo(voskModelDir)
                tempDir.deleteRecursively()
                modelReady = true
                mainHandler.post { callback(true, "Model ready") }
            } catch (e: Exception) {
                mainHandler.post { callback(false, "Download failed: ${e.message}") }
            }
        }.start()
    }

    @Suppress("UNCHECKED_CAST")
    fun initVosk() {
        if (!isModelDownloaded() || modelReady) return
        try {
            val modelClass = Class.forName("org.vosk.Model")
            voskModel = modelClass.getConstructor(String::class.java).newInstance(voskModelDir.absolutePath)
            modelReady = true
        } catch (_: Exception) {}
    }

    fun startNativeListening(voskPreferred: Boolean = false) {
        if (isListening) return
        isListening = true

        val useBt = isBluetoothConnected()
        if (useBt) connectBluetoothSco()

        if (voskPreferred && modelReady) {
            startVoskRecognition()
        } else {
            startAndroidRecognition(useBt)
        }
    }

    fun stopListening() {
        isListening = false
        recordingThread?.interrupt()
        recordingThread = null
        try { audioRecord?.stop() } catch (_: Exception) {}
        try { audioRecord?.release() } catch (_: Exception) {}
        audioRecord = null
        disconnectBluetoothSco()
    }

    private fun startAndroidRecognition(useBt: Boolean) {
        val recognizer = SpeechRecognizer.createSpeechRecognizer(context)
        val intent = android.content.Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 2000)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1500)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 500)
            if (useBt) {
                putExtra("android.speech.extra.EXTRA_USE_BLUETOOTH_SCO", true)
            }
        }
        recognizer.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: android.os.Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onError(error: Int) {
                val msg = when (error) {
                    SpeechRecognizer.ERROR_NO_MATCH -> "No speech detected"
                    SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "Speech timeout"
                    SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Recognizer busy"
                    else -> "Error $error"
                }
                sendToJS(JSONObject().apply {
                    put("type", "error")
                    put("message", msg)
                }.toString())
                recognizer.destroy()
                if (isListening) {
                    mainHandler.postDelayed({ startAndroidRecognition(isBluetoothConnected()) }, 200)
                }
            }
            override fun onResults(results: android.os.Bundle?) {
                val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull() ?: ""
                if (text.isNotBlank()) {
                    sendToJS(JSONObject().apply {
                        put("type", "result")
                        put("text", text)
                    }.toString())
                }
                recognizer.destroy()
                if (isListening) {
                    mainHandler.postDelayed({ startAndroidRecognition(isBluetoothConnected()) }, 100)
                }
            }
            override fun onPartialResults(partialResults: android.os.Bundle?) {
                val text = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull() ?: ""
                if (text.isNotBlank()) {
                    sendToJS(JSONObject().apply {
                        put("type", "partial")
                        put("text", text)
                    }.toString())
                }
            }
            override fun onEvent(eventType: Int, params: android.os.Bundle?) {}
        })
        recognizer.startListening(intent)
    }

    @Suppress("UNCHECKED_CAST")
    private fun startVoskRecognition() {
        try {
            val samplerate = 16000f
            val recClass = Class.forName("org.vosk.Recognizer")
            voskRecognizer = recClass.getConstructor(Class.forName("org.vosk.Model"), Float::class.java)
                .newInstance(voskModel, samplerate)

            val bufferSize = AudioRecord.getMinBufferSize(
                samplerate.toInt(),
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT
            )
            val source = if (isBluetoothConnected())
                MediaRecorder.AudioSource.VOICE_COMMUNICATION
            else
                MediaRecorder.AudioSource.VOICE_RECOGNITION

            audioRecord = AudioRecord(source, samplerate.toInt(), AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT, bufferSize * 4)

            if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                sendToJS(JSONObject().apply {
                    put("type", "error")
                    put("message", "Audio init failed")
                }.toString())
                return
            }

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN && NoiseSuppressor.isAvailable()) {
                try {
                    val ns = NoiseSuppressor.create(audioRecord!!.audioSessionId)
                    ns?.enabled = true
                } catch (_: Exception) {}
            }

            audioRecord?.startRecording()
            val buffer = ByteArray(bufferSize)
            val acceptMethod = recClass.getMethod("acceptWaveform", ByteArray::class.java, Int::class.java)
            val getResultMethod = recClass.getMethod("getResult")
            val getPartialMethod = recClass.getMethod("getPartialResult")

            recordingThread = Thread {
                while (isListening && audioRecord?.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    try {
                        val read = audioRecord?.read(buffer, 0, buffer.size) ?: 0
                        if (read > 0) {
                            acceptMethod.invoke(voskRecognizer, buffer, read)
                        }
                    } catch (_: Exception) { break }
                }
            }.also { it.start() }

            mainHandler.post(object : Runnable {
                override fun run() {
                    if (!isListening) return
                    try {
                        val partialStr = getPartialMethod.invoke(voskRecognizer) as String
                        val partialJson = JSONObject(partialStr)
                        val partial = partialJson.optString("partial", "")
                        if (partial.isNotBlank()) {
                            sendToJS(JSONObject().apply {
                                put("type", "partial")
                                put("text", partial)
                            }.toString())
                        }
                        val resultStr = getResultMethod.invoke(voskRecognizer) as String
                        val resultJson = JSONObject(resultStr)
                        val text = resultJson.optString("text", "")
                        if (text.isNotBlank()) {
                            sendToJS(JSONObject().apply {
                                put("type", "result")
                                put("text", text)
                            }.toString())
                            stopListening()
                            return
                        }
                    } catch (_: Exception) {}
                    mainHandler.postDelayed(this, 500)
                }
            })

        } catch (e: Exception) {
            sendToJS(JSONObject().apply {
                put("type", "error")
                put("message", "Vosk error: ${e.message}")
            }.toString())
        }
    }

    private fun sendToJS(json: String) {
        mainHandler.post {
            try {
                webView.evaluateJavascript(
                    "window.__nativeSpeechResult && window.__nativeSpeechResult('${json.replace("'", "\\'").replace("\n", " ")}')",
                    null
                )
            } catch (_: Exception) {}
        }
    }
}
