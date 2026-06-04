# Default ProGuard rules
-keepattributes *Annotation*
-keepattributes JavascriptInterface
-keepclassmembers class com.jarvis.productivity.JarvisBridge {
    @android.webkit.JavascriptInterface <methods>;
}
