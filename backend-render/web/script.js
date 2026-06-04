const canvas = document.getElementById("particles");
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

const particles = [];
const count = 150;
const baseRadius = width * 0.35;

for (let i = 0; i < count; i++) {
  particles.push({
    angle: Math.random() * Math.PI * 2,
    radius: baseRadius + Math.random() * (width * 0.1),
    speed: 0.001 + Math.random() * 0.004,
    size: 1 + Math.random() * 2
  });
}

function animate() {
  ctx.clearRect(0, 0, width, height);
  particles.forEach(p => {
    p.angle += p.speed;
    const x = centerX + p.radius * Math.cos(p.angle);
    const y = centerY + p.radius * Math.sin(p.angle);
    const depth = Math.sin(p.angle);
    const opacity = 0.2 + (depth + 1) / 2;
    ctx.fillStyle = `rgba(255,165,0,${opacity * 0.7})`;
    ctx.beginPath();
    ctx.arc(x, y, p.size, 0, Math.PI * 2);
    ctx.fill();
  });
  requestAnimationFrame(animate);
}

let isListening = false;
let isSpeaking = false;
let recognition = null;
const WAKE_WORD = "jarvis";
let wakeMode = true;
let sessionId = 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
let sessionMsgCount = 0;
let sessionLastPreview = "";

const STOP_WORDS = ["stop", "pause", "wait", "ruko", "shut up", "be quiet", "enough", "that's enough", "chup", "bas karo", "stop talking", "hold on", "quiet", "silence", "that's it", "ruka"];

function isStopCommand(text) {
    const t = text.toLowerCase().trim();
    return STOP_WORDS.some(w => t === w || t.startsWith(w + " ") || t.startsWith(w + ".") || t.startsWith(w + "!"));
}

function cancelTts() {
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    if (typeof Android !== 'undefined' && Android.stopTts) Android.stopTts();
    isSpeaking = false;
    if (recognition) {
        try { recognition.abort(); } catch(e) { try { recognition.stop(); } catch(e2) {} }
    }
}

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';
    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        console.log("Transcript:", transcript);
        if (wakeMode) {
            const lower = transcript.toLowerCase().trim();
            const idx = lower.indexOf(WAKE_WORD);
            if (idx === -1) {
                console.log("Wake word not detected, ignoring");
                return;
            }
            let cmd = transcript.slice(idx + WAKE_WORD.length).trim();
            if (cmd.startsWith(",") || cmd.startsWith(".") || cmd.startsWith("!")) cmd = cmd.slice(1).trim();
            if (!cmd) {
                updateUI('listening', 'YES BOSS?');
                setTimeout(() => updateUI('', 'WAITING FOR JARVIS...'), 2000);
                return;
            }
            wakeMode = false;
            sendToJarvis(cmd);
            setTimeout(() => { wakeMode = true; }, 3000);
        } else {
            sendToJarvis(transcript);
        }
    };
    recognition.onerror = (event) => {
        console.error("Speech Error:", event.error);
        if (event.error === 'not-allowed') {
            alert("Microphone access denied. Please allow it in browser settings.");
            isListening = false;
        } else {
            setTimeout(startListening, 100);
        }
    };
    recognition.onend = () => {
        if (isListening && !isSpeaking) {
            setTimeout(() => {
                if (isListening && !isSpeaking) {
                    try { recognition.start(); } catch(e) {}
                }
            }, 100);
        }
    };
    // Auto-restart wake mode if stopped externally
    setInterval(() => {
        if (isListening && !isSpeaking && recognition && recognition.state === 'inactive') {
            try { recognition.start(); } catch(e) {}
        }
    }, 5000);
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
    "youtube": "com.google.android.youtube", "chrome": "com.android.chrome", "whatsapp": "com.whatsapp",
    "telegram": "org.telegram.messenger", "spotify": "com.spotify.music", "gallery": "com.google.android.apps.photos",
    "camera": "com.android.camera", "files": "com.google.android.documentsui", "calculator": "com.android.calculator2",
    "settings": "com.android.settings", "maps": "com.google.android.apps.maps", "gmail": "com.google.android.gm",
    "clock": "com.google.android.deskclock", "contacts": "com.google.android.contacts", "phone": "com.google.android.dialer",
    "play store": "com.android.vending", "instagram": "com.instagram.android", "facebook": "com.facebook.katana",
    "twitter": "com.twitter.android", "linkedin": "com.linkedin.android", "netflix": "com.netflix.mediaclient",
    "prime video": "com.amazon.avod.thirdpartyclient", "notepad": "com.socialnmobile.dictapps.notepad.color.note",
};

const ANDROID_TASK_MAP = {
    "open_app": "openApp", "close_app": "closeApp", "play_yt": "openUrl", "open_website": "openUrl", "search": null,
    "control_volume": "mediaVolume", "control_brightness": "brightness", "toggle_wifi": "wifi", "toggle_bluetooth": "bluetooth",
    "take_shot": null, "take_photo": null, "open_gallery": null, "access_storage": null, "write_note": null,
    "get_battery_status": null, "get_system_info": null, "get_news": null, "call_contact": "openUrl",
    "read_notifications": null, "get_realtime_data": null, "get_time": null, "lock_screen": null, "shutdown": null,
    "restart": null, "cancel_shutdown": null, "send_sms": null, "read_sms": null, "get_contacts": null,
    "media_control": "mediaPlay", "share_content": "share", "get_wifi_info": null, "set_wallpaper": null,
    "get_call_log": null, "get_location": null,
};

function executeAndroidTask(data) {
    if (typeof Android === 'undefined') return;
    const task = data.task;
    const target = data.target;
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
        } else if (task === "call_contact") {
            const url = `tel:${encodeURIComponent(target || "")}`;
            if (Android.openUrl) Android.openUrl(url);
        } else if (task === "open_website") {
            if (target && Android.openUrl) Android.openUrl(target);
        }
    } catch (e) {
        console.error("[Android bridge error]", e);
    }
}

function speak(text) {
    isSpeaking = true;
    if (recognition) {
        try { recognition.abort(); } catch(e) { recognition.stop(); }
    }
    let cleaned = text.replace(/https?:\/\/\S+|www\.\S+/gi, '');
    cleaned = cleaned.replace(/[!@#$%^&*()_+{}[\]:";?'<>,.~`|\\/]/g, '');
    cleaned = cleaned.replace(/\s+/g, ' ').trim();
    if (!cleaned) { isSpeaking = false; return; }
    if (typeof Android !== 'undefined' && Android.speak) {
        Android.speak(cleaned);
        isSpeaking = false;
        if (isListening) startListening();
        return;
    }
    if (window.speechSynthesis) {
        speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(cleaned);
        utterance.rate = 0.7;
        utterance.pitch = 0.95;
        const isHindi = /[\u0900-\u097F]/.test(cleaned);
        utterance.lang = isHindi ? 'hi-IN' : 'en-US';
        utterance.onend = () => {
            isSpeaking = false;
            if (isListening) startListening();
        };
        speechSynthesis.speak(utterance);
    } else {
        isSpeaking = false;
        if (isListening) startListening();
    }
}

function updateUI(state, text) {
    if (statusText) statusText.textContent = text;
    if (voiceTrigger) voiceTrigger.className = 'center ' + state;
    if (!hintText) return;
    if (state === 'listening') {
        hintText.textContent = 'LISTENING...';
    } else if (state === 'processing') {
        hintText.textContent = 'WORKING...';
    } else {
        hintText.textContent = isListening ? 'ALWAYS ON | READY' : 'TAP TO ACTIVATE';
    }
}

function resetState() {
    isListening = false;
    if (recognition) recognition.stop();
    updateUI('', 'SYSTEM OFFLINE');
}

function startListening(bypassWake) {
    if (!recognition) {
        alert("Speech recognition not supported in this browser. Please use Chrome.");
        return;
    }
    isListening = true;
    if (bypassWake) {
        wakeMode = false;
        updateUI('listening', 'LISTENING...');
        setTimeout(() => { wakeMode = true; }, 5000);
    } else {
        updateUI('listening', 'WAITING FOR JARVIS...');
    }
    recognition.lang = 'en-US';
    try { recognition.start(); } catch (e) {}
}

voiceTrigger.addEventListener('click', function() { startListening(true); });

const chatInput = document.getElementById('chatInput');
const chatSendBtn = document.getElementById('chatSendBtn');

function sendTextMessage() {
    const text = chatInput.value.trim();
    if (!text) return;
    chatInput.value = '';
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

const bgCanvas = document.getElementById("bgCanvas");
const bgCtx = bgCanvas.getContext("2d");

function resizeBg() {
    bgCanvas.width = window.innerWidth;
    bgCanvas.height = window.innerHeight;
}
window.addEventListener('resize', resizeBg);
resizeBg();

const planets = [
    { radius: 100, size: 1.8, speed: 0.008, color: "#ff6699", angle: Math.random() * Math.PI * 2, hasRings: false },
    { radius: 160, size: 2.5, speed: 0.006, color: "#00ffff", angle: Math.random() * Math.PI * 2, hasRings: false },
    { radius: 220, size: 3.2, speed: 0.005, color: "#ff4444", angle: Math.random() * Math.PI * 2, hasRings: false },
    { radius: 290, size: 4, speed: 0.004, color: "#ffb700", angle: Math.random() * Math.PI * 2, hasRings: false },
    { radius: 370, size: 5, speed: 0.0032, color: "#00ff88", angle: Math.random() * Math.PI * 2, hasRings: false },
    { radius: 460, size: 6.5, speed: 0.0025, color: "#aa66ff", angle: Math.random() * Math.PI * 2, hasRings: false },
    { radius: 550, size: 9, speed: 0.0018, color: "#0088ff", angle: Math.random() * Math.PI * 2, hasRings: true },
    { radius: 650, size: 5.5, speed: 0.0013, color: "#ff00ff", angle: Math.random() * Math.PI * 2, hasRings: false },
    { radius: 750, size: 4, speed: 0.001, color: "#aaddff", angle: Math.random() * Math.PI * 2, hasRings: false },
    { radius: 860, size: 6, speed: 0.0007, color: "#ffcc00", angle: Math.random() * Math.PI * 2, hasRings: true },
    { radius: 980, size: 3, speed: 0.0005, color: "#66ffcc", angle: Math.random() * Math.PI * 2, hasRings: false },
    { radius: 1100, size: 2, speed: 0.0003, color: "#ff8866", angle: Math.random() * Math.PI * 2, hasRings: false },
];

const stars = [];
const numStars = 600;
for (let i = 0; i < numStars; i++) {
    stars.push({
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        size: Math.random() * 1.5,
        opacity: Math.random()
    });
}

function animateSolarSystem() {
    bgCtx.fillStyle = "rgba(3, 5, 12, 0.3)";
    bgCtx.fillRect(0, 0, bgCanvas.width, bgCanvas.height);
    const cx = bgCanvas.width / 2;
    const cy = bgCanvas.height / 2;
    stars.forEach(star => {
        bgCtx.fillStyle = `rgba(255, 255, 255, ${star.opacity})`;
        bgCtx.beginPath();
        bgCtx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
        bgCtx.fill();
        star.opacity += (Math.random() - 0.5) * 0.03;
        if (star.opacity < 0.05) star.opacity = 0.05;
        if (star.opacity > 1) star.opacity = 1;
        star.x -= 0.15;
        if (star.x < 0) {
            star.x = bgCanvas.width;
            star.y = Math.random() * bgCanvas.height;
        }
    });
    planets.forEach(p => {
        bgCtx.beginPath();
        bgCtx.arc(cx, cy, p.radius, 0, Math.PI * 2);
        bgCtx.strokeStyle = `rgba(0, 255, 255, ${0.04 + p.speed * 2})`;
        bgCtx.lineWidth = 0.5;
        bgCtx.setLineDash([3, 6]);
        bgCtx.stroke();
    });
    bgCtx.setLineDash([]);
    const sunPulse = 0.8 + 0.2 * Math.sin(Date.now() * 0.001);
    bgCtx.shadowBlur = 100;
    bgCtx.shadowColor = "#FF8C00";
    bgCtx.fillStyle = `rgba(255, 140, 0, ${0.04 * sunPulse})`;
    bgCtx.beginPath();
    bgCtx.arc(cx, cy, 120, 0, Math.PI * 2);
    bgCtx.fill();
    bgCtx.shadowBlur = 0;
    planets.forEach(p => {
        p.angle += p.speed;
        const px = cx + Math.cos(p.angle) * p.radius;
        const py = cy + Math.sin(p.angle) * p.radius;
        bgCtx.beginPath();
        bgCtx.moveTo(cx, cy);
        bgCtx.lineTo(px, py);
        bgCtx.strokeStyle = `rgba(255, 255, 255, 0.03)`;
        bgCtx.lineWidth = 1;
        bgCtx.stroke();
        const glowPulse = 0.6 + 0.4 * Math.sin(Date.now() * 0.0008 + p.radius);
        bgCtx.shadowBlur = 15 + 20 * glowPulse;
        bgCtx.shadowColor = p.color;
        bgCtx.fillStyle = p.color;
        bgCtx.beginPath();
        bgCtx.arc(px, py, p.size, 0, Math.PI * 2);
        bgCtx.fill();
        bgCtx.shadowBlur = 0;
        if (p.hasRings) {
            bgCtx.beginPath();
            bgCtx.ellipse(px, py, p.size * 2.8, p.size * 0.8, p.angle, 0, Math.PI * 2);
            bgCtx.strokeStyle = "rgba(0, 136, 255, 0.6)";
            bgCtx.lineWidth = 1.5;
            bgCtx.stroke();
            bgCtx.beginPath();
            bgCtx.ellipse(px, py, p.size * 4, p.size * 1.1, p.angle, 0, Math.PI * 2);
            bgCtx.strokeStyle = "rgba(0, 136, 255, 0.2)";
            bgCtx.lineWidth = 1;
            bgCtx.stroke();
        }
    });
    requestAnimationFrame(animateSolarSystem);
}

animateSolarSystem();

setTimeout(() => {
    if (typeof Android !== 'undefined' && Android.speak) {
        Android.speak("Hello boss");
    } else if (window.speechSynthesis) {
        const u = new SpeechSynthesisUtterance("Hello boss");
        u.rate = 0.7;
        u.pitch = 0.95;
        speechSynthesis.speak(u);
    }
}, 800);
