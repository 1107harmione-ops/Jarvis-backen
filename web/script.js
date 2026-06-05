const canvas = document.getElementById("waterParticles");
const statusText = document.getElementById("statusText");
const hintText = document.getElementById("hintText");
const voiceTrigger = document.getElementById("voiceTrigger");

function setupCanvas(canvasElement) {
    const rect = canvasElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvasElement.width = rect.width * dpr;
    canvasElement.height = rect.height * dpr;
    const ctx = canvasElement.getContext("2d");
    ctx.scale(dpr, dpr);
    return { ctx, width: rect.width, height: rect.height };
}

const { ctx, width, height } = setupCanvas(canvas);
const centerX = width / 2;
const centerY = height / 2;

// ─── Crystal Water Particles ───
const waterParticlesCount = 60;
const waterParticles = [];

for (let i = 0; i < waterParticlesCount; i++) {
  waterParticles.push({
    x: Math.random() * width,
    y: Math.random() * height,
    vx: (Math.random() - 0.5) * 0.3,
    vy: -0.1 - Math.random() * 0.2,
    size: 1.5 + Math.random() * 2.5,
    opacity: 0.3 + Math.random() * 0.4,
    pulse: Math.random() * Math.PI * 2,
    pulseSpeed: 0.01 + Math.random() * 0.02
  });
}

function animate() {
  ctx.clearRect(0, 0, width, height);
  waterParticles.forEach(p => {
    p.x += p.vx;
    p.y += p.vy;
    p.pulse += p.pulseSpeed;
    // Wrap around
    if (p.y < -10) { p.y = height + 10; p.x = Math.random() * width; }
    if (p.x < -10) p.x = width + 10;
    if (p.x > width + 10) p.x = -10;
    // Slight horizontal drift
    p.vx += (Math.random() - 0.5) * 0.02;
    p.vx = Math.max(-0.5, Math.min(0.5, p.vx));
    // Draw bubble
    const pulseOpacity = p.opacity * (0.7 + 0.3 * Math.sin(p.pulse));
    ctx.fillStyle = `rgba(0, 229, 255, ${pulseOpacity * 0.3})`;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
    ctx.fill();
    // Bubble highlight
    ctx.fillStyle = `rgba(255, 255, 255, ${pulseOpacity * 0.2})`;
    ctx.beginPath();
    ctx.arc(p.x - p.size * 0.3, p.y - p.size * 0.3, p.size * 0.4, 0, Math.PI * 2);
    ctx.fill();
    // Connection lines to nearby particles
    waterParticles.forEach(p2 => {
      const dx = p.x - p2.x;
      const dy = p.y - p2.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 60 && dist > 0) {
        const alpha = (1 - dist / 60) * 0.08;
        ctx.strokeStyle = `rgba(0, 229, 255, ${alpha})`;
        ctx.lineWidth = 0.5;
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.stroke();
      }
    });
  });
  requestAnimationFrame(animate);
}

let isListening = false;
let isSpeaking = false;
let recognition = null;
let nativeRecognition = false;
let btConnected = false;
let sessionId = 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
let sessionMsgCount = 0;
let sessionLastPreview = "";

// Callback for native Android speech recognition results
window.__nativeSpeechResult = function(json) {
    try {
        var data = JSON.parse(json);
        if (data.type === 'result' && data.text) {
            var transcript = data.text;
            console.log("Native transcript:", transcript);
            if (routeAdminVoice(transcript)) return;
            sendToJarvis(transcript);
        } else if (data.type === 'partial' && data.text) {
            if (statusText) statusText.textContent = 'HEARD: ' + data.text;
        }
    } catch(e) {
        console.error("Native speech parse error:", e);
    }
};

window.__voskReady = function() {
    console.log("Vosk model downloaded and ready");
};

window.__voskDownloadCallback = function(success, message) {
    console.log("Vosk download:", success, message);
};

const STOP_WORDS = ["stop", "pause", "wait", "ruko", "shut up", "be quiet", "enough", "that's enough", "chup", "bas karo", "stop talking", "hold on", "quiet", "silence", "that's it", "ruka"];

function isStopCommand(text) {
    const t = text.toLowerCase().trim();
    return STOP_WORDS.some(w => t === w || t.startsWith(w + " ") || t.startsWith(w + ".") || t.startsWith(w + "!"));
}

function cancelTts() {
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    if (typeof Android !== 'undefined' && Android.stopTts) Android.stopTts();
    isSpeaking = false;
    if (nativeRecognition && typeof Android !== 'undefined') {
        Android.stopNativeListening();
    }
    if (recognition) {
        try { recognition.abort(); } catch(e) { try { recognition.stop(); } catch(e2) {} }
    }
}

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';
    recognition.onstart = function() {
        console.log("Web Speech started");
        updateUI('listening', 'LISTENING...');
    };
    recognition.onresult = function(event) {
        var transcript = '';
        for (var i = event.resultIndex; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
                transcript = event.results[i][0].transcript;
                break;
            }
        }
        if (!transcript && event.results.length > 0) {
            transcript = event.results[event.results.length - 1][0].transcript;
            if (statusText) statusText.textContent = 'HEARD: ' + transcript;
            return;
        }
        console.log("Transcript:", transcript);
        if (!transcript) return;
        if (routeAdminVoice(transcript)) return;
        sendToJarvis(transcript);
    };
    recognition.onerror = function(event) {
        console.error("Speech Error:", event.error);
        if (event.error === 'not-allowed') {
            alert("Microphone access denied. Please allow it in browser settings.");
            isListening = false;
        } else if (event.error === 'aborted') {
            resumeListening(200);
        } else {
            setTimeout(function() { if (isListening) startListening(); }, 200);
        }
    };
    recognition.onend = function() {
        // Don't restart if speaking or processing
        if (isListening && !isSpeaking) {
            setTimeout(function() {
                if (isListening && !isSpeaking) {
                    try { recognition.start(); } catch(e) {}
                }
            }, 300);
        }
    };
    setInterval(function() {
        if (isListening && !isSpeaking && recognition) {
            try {
                if (recognition.state === 'inactive') { recognition.start(); }
            } catch(e) {}
        }
    }, 3000);
}

function appendChat(label, text) {
    const log = document.getElementById('chatLog');
    const msgs = document.getElementById('chatMessages');
    if (!msgs) return;
    const div = document.createElement('div');
    div.className = 'chat-msg ' + label;
    div.innerHTML = '<div class="label">' + label + '</div><div class="text">' + escapeHtml(text) + '</div>';
    msgs.appendChild(div);
    log.style.display = 'block';
    log.scrollTop = log.scrollHeight;
}

function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

const hamburgerBtn = document.getElementById("hamburgerBtn");
const sidebarPanel = document.getElementById("sidebarPanel");
const sidebarOverlay = document.getElementById("sidebarOverlay");
const sidebarClose = document.getElementById("sidebarClose");

function toggleSidebar() {
    const open = sidebarPanel.classList.toggle("open");
    sidebarOverlay.classList.toggle("active", open);
}

function closeSidebar() {
    sidebarPanel.classList.remove("open");
    sidebarOverlay.classList.remove("active");
}

if (hamburgerBtn) hamburgerBtn.addEventListener("click", toggleSidebar);
if (sidebarClose) sidebarClose.addEventListener("click", closeSidebar);
if (sidebarOverlay) sidebarOverlay.addEventListener("click", closeSidebar);

function updateSidebarHistory(text, label) {
    const list = document.getElementById("sidebarLastWorks");
    if (!list) return;
    const empty = list.querySelector(".sidebar-empty");
    if (empty) empty.remove();
    const item = document.createElement("div");
    item.className = "sidebar-item";
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    item.innerHTML = `<div class="item-label">${label}</div><div>${escapeHtml(text.slice(0, 60))}</div><div class="item-time">${time}</div>`;
    list.insertBefore(item, list.firstChild);
    if (list.children.length > 10) list.lastChild.remove();
}

function updateSidebarSessions(text) {
    const list = document.getElementById("sidebarSessions");
    if (!list) return;
    const empty = list.querySelector(".sidebar-empty");
    if (empty) empty.remove();
    const item = document.createElement("div");
    item.className = "sidebar-item";
    const time = new Date().toLocaleDateString([], { month: 'short', day: 'numeric' }) + " " + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    item.innerHTML = `<div class="item-label">session</div><div>${escapeHtml(text.slice(0, 80))}</div><div class="item-time">${time}</div>`;
    list.insertBefore(item, list.firstChild);
    if (list.children.length > 20) list.lastChild.remove();
}

async function sendToJarvis(message) {
    if (isStopCommand(message)) {
        cancelTts();
        appendChat('user', message);
        appendChat('assistant', 'Stopped.');
        updateUI('', 'SYSTEM ONLINE');
        if (isListening) startListening();
        return;
    }
    appendChat('user', message);
    updateSidebarHistory(message, 'user');
    updateSidebarSessions('You: ' + message);
    sessionLastPreview = 'You: ' + message;
    sessionMsgCount++;
    saveMemory();
    updateUI('processing', 'WORKING...');
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, session_id: sessionId }),
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        const data = await response.json();
        if (data.reply) {
            appendChat('assistant', data.reply);
            updateSidebarHistory(data.reply, 'jarvis');
            sessionLastPreview = 'Jarvis: ' + data.reply;
            sessionMsgCount++;
            updateUI('', 'SYSTEM ONLINE');
            speak(data.reply);
            executeAndroidTask(data);
        }
        if (data.image_url) {
            const display = document.getElementById("imageDisplay");
            const img = document.getElementById("generatedImg");
            const path = document.getElementById("imagePath");
            img.src = data.image_url;
            if (data.filepath) path.textContent = data.filepath;
            display.style.display = 'flex';
        } else if (data.error) {
            appendChat('assistant', 'Error: ' + data.error);
            updateUI('', 'NEURAL ERROR');
            speak("I encountered a neural link error.");
        }
    } catch (error) {
        clearTimeout(timeoutId);
        console.error("API Error:", error);
        if (error.name === 'AbortError') {
            appendChat('assistant', 'Request timed out.');
            updateUI('', 'TIMEOUT');
            speak("The cognitive link timed out.");
        } else {
            appendChat('assistant', 'Connection error: ' + error.message);
            updateUI('', 'OFFLINE');
            speak("Connection to core server lost.");
        }
    }
}

const PKG_MAP = {
    // ── Social & Messaging ──
    "whatsapp": "com.whatsapp", "telegram": "org.telegram.messenger",
    "telegram x": "org.thunderdog.challegram",
    "instagram": "com.instagram.android", "facebook": "com.facebook.katana",
    "messenger": "com.facebook.orca",
    "twitter": "com.twitter.android", "x": "com.twitter.android",
    "snapchat": "com.snapchat.android", "snapchat stories": "com.snapchat.android",
    "discord": "com.discord", "linkedin": "com.linkedin.android",
    "reddit": "com.reddit.frontpage",

    // ── Browsers & Search ──
    "chrome": "com.android.chrome", "brave": "com.brave.browser",
    "browser": "com.android.browser",
    "google": "com.google.android.googlequicksearchbox",
    "translate": "com.google.android.apps.translate",

    // ── Google Apps ──
    "gmail": "com.google.android.gm", "maps": "com.google.android.apps.maps",
    "drive": "com.google.android.apps.docs", "photos": "com.google.android.apps.photos",
    "gallery": "com.google.android.apps.photos", "files": "com.google.android.documentsui",
    "clock": "com.google.android.deskclock", "contacts": "com.google.android.contacts",
    "phone": "com.google.android.dialer", "settings": "com.android.settings",
    "play store": "com.android.vending", "youtube": "com.google.android.youtube",
    "keep notes": "com.google.android.keep", "gemini": "com.google.android.apps.bard",
    "find my device": "com.google.android.apps.adm",
    "messages": "com.google.android.apps.messaging",

    // ── Payment / Fintech ──
    "phonepe": "com.phonepe.app",
    "gpay": "com.google.android.apps.nbu.paisa.user",
    "google pay": "com.google.android.apps.nbu.paisa.user",
    "paytm": "net.one97.paytm", "amazon pay": "in.amazon.mShop.android.shopping",
    "fampay": "in.fampay.app", "kotak811": "com.kotak811.app",
    "home credit": "com.homecredit.mobileapp", "greenstash": "com.greenstash.app",

    // ── Shopping ──
    "amazon": "in.amazon.mShop.android.shopping",
    "flipkart": "com.flipkart.android",
    "mi store": "com.mi.android.shop",

    // ── Video / Streaming / Music ──
    "netflix": "com.netflix.mediaclient",
    "prime video": "com.amazon.avod.thirdpartyclient",
    "hotstar": "in.startv.hotstar", "jio cinema": "com.jio.media.jiobeats",
    "sony liv": "com.sonyliv", "zee5": "com.graymatrix.did",
    "mx player": "com.mxtech.videoplayer.ad",
    "vmusic": "com.vmusic.app",
    "tiktok": "com.zhiliaoapp.musically",
    "shazam": "com.shazam.android",
    "spotify": "com.spotify.music",

    // ── Games ──
    "pubg": "com.pubg.imobile", "bgmi": "com.pubg.imobile",
    "battleground": "com.pubg.imobile", "battlegrounds": "com.pubg.imobile",
    "pubg mobile": "com.pubg.imobile", "pubg mobile india": "com.pubg.imobile",
    "bgmi mobile": "com.pubg.imobile",
    "cod": "com.activision.callofduty.shooter",
    "call of duty": "com.activision.callofduty.shooter",
    "free fire": "com.dts.freefireth", "freefire": "com.dts.freefireth",
    "clash of clans": "com.supercell.clashofclans", "coc": "com.supercell.clashofclans",
    "minecraft": "com.mojang.minecraftpe",
    "subway surfers": "com.kiloo.subwaysurf",
    "temple run": "com.imangi.templerun",

    // ── Productivity & Tools ──
    "calculator": "com.android.calculator2", "notepad": "com.socialnmobile.dictapps.notepad.color.note",
    "notes": "com.mi.notes", "recorder": "com.android.recorder",
    "termux": "com.termux",
    "github": "com.github.android",
    "microsoft 365": "com.microsoft.office.officehubrow",
    "file manager": "com.android.filemanager",

    // ── Telecom / Operator ──
    "airtel": "com.myairtel.app", "myjio": "com.jio.myjio",
    "vi app": "com.myvodafone.app",
    "jiocloud": "com.jio.jiocloud",

    // ── Device / System ──
    "camera": "com.android.camera", "compass": "com.google.android.compass",
    "video": "com.android.video", "feedback": "com.android.feedback",
    "mi remote": "com.duokan.phone.remotecontroller",

    // ── vivo Apps ──
    "vivo cloud": "com.bbk.cloud", "vivo store": "com.vivo.appstore",
    "easy share": "com.vivo.easyshare", "easyshare": "com.vivo.easyshare",

    // ── Other ──
    "digilocker": "com.digilocker.android",
    "character ai": "ai.character.app",
    "truecaller": "com.truecaller",
    "mediafire": "com.mediafire.android",
    "pyroid 3": "com.pyroid.app",
    "one health": "com.onehealth.app",
    "jarvis": "com.jarvis",
    "feeling": "com.feeling.app",
    "open": "com.open.app",

    // ── Uber / Ola / Food ──
    "swiggy": "in.swiggy.android", "zomato": "com.application.zomato",
    "uber": "com.ubercab", "ola": "com.olacabs.customer",

    // ── MyUZONE (catch-all) ──
    "myuzone": "com.myuzone.app",

    // ── Aliases / common variations ──
    "brave browser": "com.brave.browser",
    "google maps": "com.google.android.apps.maps",
    "google drive": "com.google.android.apps.docs",
    "google photos": "com.google.android.apps.photos",
    "google keep": "com.google.android.keep",
    "google messages": "com.google.android.apps.messaging",
    "text messages": "com.google.android.apps.messaging",
    "file manager": "com.android.filemanager",
    "character dot ai": "ai.character.app",
    "character ai": "ai.character.app",
    "google gemini": "com.google.android.apps.bard",
    "youtube music": "com.google.android.apps.youtube.music",
    "google translate": "com.google.android.apps.translate",
    "google settings": "com.android.settings",
    "system settings": "com.android.settings",
    "app settings": "com.android.settings",
};

const ANDROID_TASK_MAP = {
    "open_app": "openApp", "close_app": "closeApp", "play_yt": "openUrl", "open_website": "openUrl", "search": null,
    "control_volume": "mediaVolume", "control_brightness": "brightness", "toggle_wifi": "wifi", "toggle_bluetooth": "bluetooth",
    "take_shot": null, "take_photo": null, "open_gallery": null, "access_storage": null, "write_note": null,
    "get_battery_status": null, "get_system_info": null, "get_news": null, "call_contact": "openUrl",
    "read_notifications": null, "get_realtime_data": null, "get_time": null, "lock_screen": null, "shutdown": null,
    "restart": null, "cancel_shutdown": null, "send_sms": null, "read_sms": null, "get_contacts": null,
    "media_control": "mediaPlay", "share_content": "share", "get_wifi_info": null, "set_wallpaper": null,
    "get_call_log": null, "get_location": null, "send_whatsapp": "openUrl", "make_call": "callByName",
    "call_contact": "callByName",
};

function executeAndroidTask(data) {
    if (typeof Android === 'undefined') return;

    // Handle compound execution (multiple tasks chained)
    if (data.compound_execution && Array.isArray(data.compound_execution)) {
        console.log("[Android] Compound execution:", data.compound_execution);
        data.compound_execution.forEach(function(item) {
            executeSingleAndroidTask(item.task, item.target);
        });
        return;
    }

    executeSingleAndroidTask(data.task, data.target);
}

function executeSingleAndroidTask(task, target) {
    if (!task || !ANDROID_TASK_MAP[task]) return;
    const bridgeFn = ANDROID_TASK_MAP[task];
    if (!bridgeFn) return;
    try {
        if (task === "open_app" || task === "close_app") {
            const key = (target || "").toLowerCase().trim();
            let pkg = PKG_MAP[key];
            if (!pkg) pkg = target;
            if (pkg && Android[bridgeFn]) {
                console.log(`[Android] ${bridgeFn}: ${pkg}`);
                Android[bridgeFn](pkg);
            }
        } else if (task === "toggle_wifi") {
            if (Android[bridgeFn]) Android[bridgeFn](target === "on" || target === "enable");
        } else if (task === "toggle_bluetooth") {
            if (Android[bridgeFn]) Android[bridgeFn](target === "on" || target === "enable");
        } else if (task === "control_brightness") {
            if (Android[bridgeFn]) Android[bridgeFn](target === "up" ? 255 : 50);
        } else if (task === "control_volume") {
            if (Android[bridgeFn]) Android[bridgeFn](target === "up" ? 1 : target === "down" ? -1 : target === "mute" ? -100 : 0);
        } else if (task === "play_yt") {
            const url = `https://www.youtube.com/results?search_query=${encodeURIComponent(target || "")}`;
            if (Android && Android.openUrl) Android.openUrl(url);
        } else if (task === "media_control") {
            const cmd = (target || "play").toLowerCase();
            if (cmd === "next" && Android.mediaNext) Android.mediaNext();
            else if (cmd === "previous" && Android.mediaPrev) Android.mediaPrev();
            else if (Android.mediaPlay) Android.mediaPlay();
        } else if (task === "share_content") {
            if (Android.share) Android.share(target || "");
        } else if (task === "call_contact" || task === "make_call") {
            var name = (target || "").trim();
            if (!name) return;
            // Try contact-aware dialer (needs APK bridge: Android.callByName)
            if (Android.callByName) {
                console.log("[Android] callByName: " + name);
                Android.callByName(name);
            } else {
                // Fallback: open dialer with name as search
                var url = "tel:" + encodeURIComponent(name);
                if (Android.openUrl) Android.openUrl(url);
            }
        } else if (task === "open_website") {
            if (target && Android.openUrl) Android.openUrl(target);
        } else if (task === "send_whatsapp") {
            const msg = encodeURIComponent(target || "");
            const url = `https://wa.me/?text=${msg}`;
            if (Android.openUrl) Android.openUrl(url);
        }
    } catch (e) {
        console.error("[Android bridge error]", e);
    }
}

function speak(text) {
    // Guard: if already speaking, cancel previous speech cleanly
    if (isSpeaking) {
        if (window.speechSynthesis) window.speechSynthesis.cancel();
        if (typeof Android !== 'undefined' && Android.stopTts) Android.stopTts();
        // Let the previous cleanup complete
    }
    isSpeaking = true;
    // Stop any active recognition before speaking
    if (recognition) {
        try { recognition.abort(); } catch(e) { try { recognition.stop(); } catch(e2) {} }
    }
    let cleaned = text.replace(/https?:\/\/\S+|www\.\S+/gi, '');
    cleaned = cleaned.replace(/[!@#$%^&*()_+{}[\]:";?'<>,.~`|\\/]/g, '');
    cleaned = cleaned.replace(/\s+/g, ' ').trim();
    if (!cleaned) { isSpeaking = false; return; }
    
    // Estimate TTS duration: ~80ms per character at rate 0.7
    var charCount = cleaned.length;
    var ttsDuration = Math.max(2000, charCount * 80 + 600);
    
    if (typeof Android !== 'undefined' && Android.speak) {
        Android.speak(cleaned);
        setTimeout(function() {
            isSpeaking = false;
            if (isListening) resumeListening(1200);
        }, ttsDuration);
        return;
    }
    if (window.speechSynthesis) {
        speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(cleaned);
        utterance.rate = 0.7;
        utterance.pitch = 0.95;
        const isHindi = /[\u0900-\u097F]/.test(cleaned);
        utterance.lang = isHindi ? 'hi-IN' : 'en-US';
        
        // Safety timeout: if onend/onerror never fire, force cleanup
        var safetyTimer = setTimeout(function() {
            isSpeaking = false;
            if (isListening) resumeListening(600);
        }, ttsDuration);
        
        utterance.onend = function() {
            clearTimeout(safetyTimer);
            isSpeaking = false;
            if (isListening) resumeListening(600);
        };
        utterance.onerror = function() {
            clearTimeout(safetyTimer);
            isSpeaking = false;
            if (isListening) resumeListening(600);
        };
        speechSynthesis.speak(utterance);
    } else {
        isSpeaking = false;
        if (isListening) resumeListening(300);
    }
}

function updateUI(state, text) {
    if (statusText) statusText.textContent = text;
    if (voiceTrigger) voiceTrigger.className = 'center ' + state;
    if (!hintText) return;
    if (state === 'listening') {
        hintText.textContent = text || 'LISTENING...';
    } else if (state === 'processing') {
        hintText.textContent = text || 'WORKING...';
    } else {
        hintText.textContent = isListening ? 'ALWAYS ON' : 'TAP THE CRYSTAL';
    }
}

function resumeListening(delayMs) {
    if (!isListening || isSpeaking) return;
    var d = delayMs || 600;
    setTimeout(function() {
        if (!isListening || isSpeaking) return;
        // For Android native: stop first, then start with proper delay
        if (typeof Android !== 'undefined') {
            try { Android.stopNativeListening(); } catch(e) {}
            setTimeout(function() {
                if (isListening && !isSpeaking) {
                    try { Android.startNativeListening(false); } catch(e) {}
                }
            }, 200);
        } else if (nativeRecognition === false && recognition) {
            try { recognition.start(); } catch(e) {
                setTimeout(function() { try { recognition.start(); } catch(e2) {} }, 500);
            }
        }
    }, d);
}

function resetState() {
    isListening = false;
    if (nativeRecognition && typeof Android !== 'undefined') {
        try { Android.stopNativeListening(); } catch(e) {}
    }
    if (recognition) { try { recognition.stop(); } catch(e) { try { recognition.abort(); } catch(e2) {} } }
    updateUI('', 'SYSTEM OFFLINE');
}

function restartNativeListening() {
    if (!isListening || isSpeaking || typeof Android === 'undefined') return;
    if (nativeRecognition) {
        try { Android.startNativeListening(false); } catch(e) {}
    }
}

function startListening() {
    isListening = true;
    updateUI('listening', 'LISTENING...');

    if (typeof Android !== 'undefined') {
        nativeRecognition = true;
        try { btConnected = Android.isBluetoothConnected(); } catch(e) { btConnected = false; }
        console.log("Bluetooth headset:", btConnected);
        try { Android.stopNativeListening(); } catch(e) {}
        try { Android.startNativeListening(false); } catch(e) { console.error("Native listen start fail:", e); }
        return;
    }

    nativeRecognition = false;
    if (!recognition) {
        alert("Speech recognition not supported. Please use Chrome.");
        return;
    }
    recognition.lang = 'en-US';
    try { recognition.start(); } catch (e) {
        setTimeout(function() { try { recognition.start(); } catch(e2) {} }, 500);
    }
}

// ─── Admin Voice Routing ────────────────────────────
function routeAdminVoice(text) {
    if (typeof isAdminTrigger === 'undefined') return false;
    if (adminWaitingForPassword) {
        submitAdminPassword(text);
        return true;
    }
    if (isAdminTrigger(text)) {
        enterAdminMode();
        return true;
    }
    if (adminMode && isAdminLogoutTrigger(text)) {
        adminApi('/admin/logout', { method: 'POST' });
        adminMode = false;
        adminToken = null;
        closeAdminPanel();
        appendChat('assistant', '🔒 Admin session closed.');
        speak('Admin session closed.');
        return true;
    }
    if (adminMode && handleAdminVoiceCommand(text)) {
        return true;
    }
    return false;
}

voiceTrigger.addEventListener('click', function() { startListening(); });

const chatInput = document.getElementById('chatInput');
const chatSendBtn = document.getElementById('chatSendBtn');

function sendTextMessage() {
    const text = chatInput.value.trim();
    if (!text) return;
    chatInput.value = '';
    if (routeAdminVoice(text)) return;
    sendToJarvis(text);
}

chatSendBtn.addEventListener('click', sendTextMessage);
chatInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') sendTextMessage();
});

const imageDisplay = document.getElementById("imageDisplay");
if (imageDisplay) {
    imageDisplay.addEventListener("click", function() {
        this.style.display = "none";
        const img = document.getElementById("generatedImg");
        if (img) img.src = "";
    });
}

animate();
updateUI('', 'SYSTEM ONLINE');
console.log("JARVIS UI READY");

// Auto-save memory every 20 seconds
function saveMemory() {
    if (!sessionMsgCount && !sessionLastPreview) return;
    fetch('/memory/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: sessionId,
            preview: sessionLastPreview.slice(0, 120),
            name: 'Session ' + new Date().toLocaleDateString()
        })
    }).catch(function() {});
}

setInterval(saveMemory, 20000);

// Load sessions from backend
function loadSessions() {
    fetch('/sessions')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            const list = document.getElementById("sidebarSessions");
            if (!list) return;
            const sessions = data.sessions || [];
            list.innerHTML = '';
            if (sessions.length === 0) {
                list.innerHTML = '<div class="sidebar-empty">No sessions yet.</div>';
                return;
            }
            sessions.forEach(function(s) {
                const item = document.createElement("div");
                item.className = "sidebar-item";
                item.style.cursor = "pointer";
                const date = new Date(s.updated_at || s.created_at);
                const timeStr = date.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                const preview = s.last_preview || s.name || 'Session ' + s.id.slice(0, 8);
                item.innerHTML = '<div class="item-label">' + s.message_count + ' msgs</div><div>' + escapeHtml(preview.slice(0, 80)) + '</div><div class="item-time">' + timeStr + '</div>';
                item.addEventListener('click', function() {
                    closeSidebar();
                    loadSessionMessages(s.id);
                });
                list.appendChild(item);
            });
        })
        .catch(function() {});
}

// Load messages from a specific session
function loadSessionMessages(sessionId) {
    fetch('/sessions/' + encodeURIComponent(sessionId))
        .then(function(r) { return r.json(); })
        .then(function(data) {
            const msgs = document.getElementById('chatMessages');
            const log = document.getElementById('chatLog');
            if (!msgs) return;
            msgs.innerHTML = '';
            (data.messages || []).forEach(function(m) {
                const div = document.createElement('div');
                div.className = 'chat-msg ' + m.role;
                div.innerHTML = '<div class="label">' + m.role + '</div><div class="text">' + escapeHtml(m.content) + '</div>';
                msgs.appendChild(div);
            });
            log.style.display = 'block';
            log.scrollTop = log.scrollHeight;
        })
        .catch(function() {});
}

// Override updateSidebarSessions to load from backend instead
function updateSidebarSessions(text) {
    // Only loads from /sessions endpoint now
}

// Override toggleSidebar to refresh sessions on open
const origToggle = toggleSidebar;
toggleSidebar = function() {
    const open = sidebarPanel.classList.toggle("open");
    sidebarOverlay.classList.toggle("active", open);
    if (open) loadSessions();
};

// ─── Backend Health Check ───────────────────────────────
function checkBackendHealth(retries) {
    retries = retries || 0;
    if (retries > 3) {
        console.warn("Backend health check failed after 3 retries");
        startupListening();
        return;
    }
    fetch('/health')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            console.log("Backend online:", data);
            appendChat('system', '🔌 Backend connected');
            // Start listening after health check passes
            setTimeout(function() {
                startupListening();
                speakGreeting();
            }, 500);
        })
        .catch(function(err) {
            console.warn("Health check attempt " + (retries + 1) + " failed:", err);
            setTimeout(function() { checkBackendHealth(retries + 1); }, 2000);
        });
}

function speakGreeting() {
    if (typeof Android !== 'undefined' && Android.speak) {
        Android.speak("Crystal systems online");
        return;
    }
    if (window.speechSynthesis) {
        isSpeaking = true;
        var u = new SpeechSynthesisUtterance("Crystal systems online");
        u.rate = 0.7;
        u.pitch = 0.95;
        u.onend = function() { isSpeaking = false; };
        u.onerror = function() { isSpeaking = false; };
        speechSynthesis.speak(u);
    }
}

// Retry startup until listening is confirmed or Android bridge is ready
function startupListening(attempts) {
    attempts = attempts || 0;
    if (attempts > 5) { console.warn("Startup listening failed after 5 retries"); return; }
    if (typeof Android !== 'undefined') {
        nativeRecognition = true;
        startListening();
        return;
    }
    if (recognition) {
        startListening();
        return;
    }
    setTimeout(function() { startupListening(attempts + 1); }, 1000);
}

// Auto-start on page load
setTimeout(function() {
    var log = document.getElementById('chatLog');
    if (log) log.style.display = 'block';
    checkBackendHealth();
}, 800);
