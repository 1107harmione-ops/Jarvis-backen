/* ─── Admin Panel — JARVIS Admin System ─── */

let adminToken = null;
let adminMode = false;
let adminWaitingForPassword = false;
let adminPasswordAttempts = 0;
const ADMIN_MAX_ATTEMPTS = 3;
const ADMIN_TRIGGERS = ["admin access", "admin mode", "admin panel", "open admin", "system admin", "admin"];
const ADMIN_LOGOUT_TRIGGERS = ["exit admin", "close admin", "logout", "admin logout"];
const ADMIN_BASE = window.location.origin;

function updateAdminBadge() {
    const badge = document.getElementById('adminBadge');
    if (badge) badge.style.display = adminMode ? 'block' : 'none';
}

// ─── Auth ─────────────────────────────────────────────

async function adminAuth(password) {
    try {
        const r = await fetch(ADMIN_BASE + '/admin/auth', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password })
        });
        const data = await r.json();
        if (data.status === 'granted') {
            adminToken = data.token;
            adminMode = true;
            updateAdminBadge();
            adminWaitingForPassword = false;
            appendChat('assistant', '✅ ' + data.message);
            speak(data.message);
            openAdminPanel();
            return true;
        } else if (data.status === 'locked') {
            appendChat('assistant', '🔒 ' + data.message);
            speak('Admin access locked. Too many attempts.');
            adminWaitingForPassword = false;
            return false;
        } else {
            adminPasswordAttempts++;
            if (adminPasswordAttempts >= ADMIN_MAX_ATTEMPTS) {
                appendChat('assistant', '🔒 Too many failed attempts. Try again in 30 seconds.');
                speak('Too many failed attempts.');
                adminWaitingForPassword = false;
            } else {
                appendChat('assistant', '❌ Invalid password. ' + (ADMIN_MAX_ATTEMPTS - adminPasswordAttempts) + ' attempts remaining.');
                speak('Invalid password.');
                adminWaitingForPassword = true;
            }
            return false;
        }
    } catch (e) {
        appendChat('assistant', '⚠️ Admin auth failed: ' + e.message);
        speak('Admin authentication failed.');
        adminWaitingForPassword = false;
        return false;
    }
}

function isAdminTrigger(text) {
    const t = text.toLowerCase().trim();
    return ADMIN_TRIGGERS.some(tr => t === tr || t.startsWith(tr + " ") || t === tr + ".");
}

function isAdminLogoutTrigger(text) {
    const t = text.toLowerCase().trim();
    return ADMIN_LOGOUT_TRIGGERS.some(tr => t === tr || t.startsWith(tr + " ") || t === tr + ".");
}

function enterAdminMode() {
    adminWaitingForPassword = true;
    adminPasswordAttempts = 0;
    appendChat('assistant', '🔐 Enter admin password:');
    speak('Enter admin password.');
}

function submitAdminPassword(password) {
    adminAuth(password);
}

// ─── Admin Panel UI ──────────────────────────────────

function openAdminPanel() {
    const panel = document.getElementById('adminPanel');
    if (panel) {
        panel.classList.add('open');
        loadAdminTab('files');
    }
    showAdminBadge(true);
}

function closeAdminPanel() {
    const panel = document.getElementById('adminPanel');
    if (panel) panel.classList.remove('open');
    showAdminBadge(false);
}

function showAdminBadge(show) {
    let badge = document.getElementById('adminBadge');
    if (show) {
        if (!badge) {
            badge = document.createElement('div');
            badge.id = 'adminBadge';
            badge.style.cssText = 'position:fixed;top:16px;right:16px;z-index:100;background:rgba(255,215,0,0.12);border:1px solid rgba(255,215,0,0.3);border-radius:4px;padding:3px 10px;font-family:monospace;font-size:10px;color:#ffd700;letter-spacing:2px;cursor:pointer;';
            badge.textContent = '🛡 ADMIN';
            badge.onclick = function() {
                const panel = document.getElementById('adminPanel');
                if (panel) panel.classList.toggle('open');
            };
            document.body.appendChild(badge);
        }
        badge.style.display = 'block';
    } else {
        if (badge) badge.style.display = 'none';
    }
}

function switchAdminTab(tabName) {
    document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.admin-tab-content').forEach(t => t.classList.remove('active'));
    const tab = document.querySelector('.admin-tab[data-tab="' + tabName + '"]');
    if (tab) tab.classList.add('active');
    const content = document.getElementById('adminTab' + tabName.charAt(0).toUpperCase() + tabName.slice(1));
    if (content) content.classList.add('active');
    loadAdminTab(tabName);
}

function loadAdminTab(tabName) {
    switch(tabName) {
        case 'files': loadFiles(); break;
        case 'config': loadConfig(); break;
        case 'apikeys': loadApiKeys(); break;
        case 'providers': loadProviders(); break;
        case 'sessions': loadSessions(); break;
        case 'database': break;
        case 'system': loadSystem(); break;
        case 'audit': loadAudit(); break;
    }
}

// ─── API Helper ───────────────────────────────────────

async function adminApi(path, options = {}) {
    const headers = { 'X-Admin-Token': adminToken };
    if (options.body && !(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }
    const r = await fetch(ADMIN_BASE + path, { ...options, headers });
    if (r.status === 401) {
        adminMode = false;
        updateAdminBadge();
        adminToken = null;
        closeAdminPanel();
        appendChat('assistant', '🔒 Admin session expired. Say "admin access" to re-authenticate.');
        return null;
    }
    return r.json();
}

function showToast(msg, type) {
    const t = document.getElementById('adminToast');
    if (!t) return;
    t.textContent = msg;
    t.className = 'admin-toast show' + (type ? ' ' + type : '');
    clearTimeout(t._hide);
    t._hide = setTimeout(() => t.classList.remove('show'), 2500);
}

// ─── Files Tab ────────────────────────────────────────

let currentFilePath = '';

async function loadFiles(path) {
    path = path || '';
    currentFilePath = path;
    const cont = document.getElementById('adminTabFiles');
    if (!cont) return;
    cont.innerHTML = '<div class="admin-loading">Loading files</div>';
    const data = await adminApi('/admin/files?path=' + encodeURIComponent(path));
    if (!data) return;
    if (data.error) { cont.innerHTML = '<div class="admin-card">' + data.error + '</div>'; return; }
    let html = '<div class="file-breadcrumb">';
    const parts = (data.path || '').split('/').filter(Boolean);
    let cum = '';
    html += '<span onclick="loadFiles(\'\')">~</span>';
    parts.forEach(p => {
        cum += '/' + p;
        html += '<span class="sep">›</span><span onclick="loadFiles(\'' + cum + '\')">' + p + '</span>';
    });
    html += '</div><ul class="file-tree">';
    data.entries.forEach(e => {
        const icon = e.type === 'dir' ? '📁' : '📄';
        const cls = e.type === 'dir' ? 'file-dir' : 'file-file';
        const onClick = e.type === 'dir'
            ? 'loadFiles(\'' + (data.path ? data.path + '/' : '') + e.name + '\')'
            : 'openFile(\'' + (data.path ? data.path + '/' : '') + e.name + '\')';
        html += '<li class="' + cls + '" onclick="' + onClick + '"><span class="file-icon">' + icon + '</span>' + e.name + '</li>';
    });
    html += '</ul>';
    cont.innerHTML = html;
}

async function openFile(filePath) {
    const data = await adminApi('/admin/files/read?path=' + encodeURIComponent(filePath));
    if (!data || data.error) { showToast(data?.error || 'Failed to read file', 'error'); return; }
    const cont = document.getElementById('adminTabFiles');
    if (!cont) return;
    cont.innerHTML = '<div class="file-breadcrumb"><span onclick="loadFiles(\'' + currentFilePath + '\')">‹ back</span></div>'
        + '<div class="admin-card" style="padding:0;border:none;background:none;">'
        + '<div class="admin-card-title">' + filePath + ' <span style="font-size:10px;color:rgba(255,215,0,0.3);">' + data.size + 'B</span></div>'
        + '<textarea class="code-editor" id="fileEditor" spellcheck="false">' + escapeHtml(data.content) + '</textarea>'
        + '<div class="editor-actions">'
        + '<button class="admin-btn" onclick="loadFiles(\'' + currentFilePath + '\')">Cancel</button>'
        + '<button class="admin-btn gold" onclick="saveFile(\'' + filePath + '\')">Save</button>'
        + '</div></div>';
}

async function saveFile(filePath) {
    const content = document.getElementById('fileEditor')?.value;
    if (!content) return;
    const data = await adminApi('/admin/files/write', {
        method: 'POST', body: JSON.stringify({ path: filePath, content })
    });
    if (data?.status === 'saved') {
        showToast('File saved (' + data.size + 'B)', 'success');
    } else {
        showToast(data?.error || 'Save failed', 'error');
    }
}

// ─── Config Tab ────────────────────────────────────────

async function loadConfig() {
    const cont = document.getElementById('adminTabConfig');
    if (!cont) return;
    cont.innerHTML = '<div class="admin-loading">Loading config</div>';
    const data = await adminApi('/admin/config');
    if (!data) return;
    if (!data.config) { cont.innerHTML = '<div class="admin-card">No config data</div>'; return; }
    let html = '<div class="admin-card"><table class="config-table"><thead><tr><th>KEY</th><th>VALUE</th><th></th></tr></thead><tbody>';
    Object.entries(data.config).forEach(([key, val]) => {
        const isSensitive = key.includes('KEY') || key.includes('SECRET') || key.includes('PASSWORD');
        html += '<tr><td class="key">' + key + '</td>'
            + '<td class="val"><input type="' + (isSensitive ? 'password' : 'text') + '" id="cfg_' + key + '" value="' + escapeHtml(val) + '" placeholder="not set"></td>'
            + '<td><button class="admin-btn admin-btn-sm" onclick="updateConfig(\'' + key + '\')">Save</button></td></tr>';
    });
    html += '</tbody></table></div>';
    cont.innerHTML = html;
}

async function updateConfig(key) {
    const input = document.getElementById('cfg_' + key);
    if (!input) return;
    const data = await adminApi('/admin/config/update', {
        method: 'POST', body: JSON.stringify({ key, value: input.value })
    });
    if (data?.status === 'updated') {
        showToast(data.message, 'success');
    } else {
        showToast(data?.error || 'Update failed', 'error');
    }
}

// ─── API Keys Tab ─────────────────────────────────────

async function loadApiKeys() {
    const cont = document.getElementById('adminTabApikeys');
    if (!cont) return;
    cont.innerHTML = '<div class="admin-loading">Loading API keys</div>';
    const data = await adminApi('/admin/api-keys');
    if (!data) return;
    let html = '';
    data.keys.forEach(k => {
        html += '<div class="admin-card"><div class="admin-card-title">' + k.provider.toUpperCase()
            + ' <span style="font-size:10px;color:' + (k.has_key ? '#00d4ff' : '#ff5252') + ';">'
            + (k.has_key ? '● key set' : '○ no key') + '</span></div>';
        if (k.key_env) {
            html += '<div style="margin-bottom:6px;"><span style="font-size:10px;color:rgba(255,215,0,0.4);">' + k.key_env + '</span>'
                + '<br><input type="password" id="apikey_' + k.provider + '" value="' + escapeHtml(k.key || '') + '"'
                + ' placeholder="Enter ' + k.provider + ' API key" style="width:100%;box-sizing:border-box;background:rgba(255,255,255,0.04);border:1px solid rgba(255,165,0,0.15);border-radius:4px;padding:6px 10px;color:#ffd700;font-family:monospace;font-size:12px;margin-top:4px;"></div>';
        }
        if (k.model_env) {
            html += '<div style="margin-bottom:6px;"><span style="font-size:10px;color:rgba(255,215,0,0.4);">' + k.model_env + '</span>'
                + '<br><input type="text" id="apimodel_' + k.provider + '" value="' + escapeHtml(k.model || '') + '"'
                + ' placeholder="Model name" style="width:100%;box-sizing:border-box;background:rgba(255,255,255,0.04);border:1px solid rgba(255,165,0,0.15);border-radius:4px;padding:6px 10px;color:#ffd700;font-family:monospace;font-size:12px;margin-top:4px;"></div>';
        }
        html += '<button class="admin-btn admin-btn-sm gold" onclick="updateApiKey(\'' + k.provider + '\')">Update</button></div>';
    });
    html += '<div class="admin-card"><button class="admin-btn" onclick="showAddProviderForm()">+ Add Provider</button></div>';
    cont.innerHTML = html;
}

async function updateApiKey(provider) {
    const keyInput = document.getElementById('apikey_' + provider);
    const modelInput = document.getElementById('apimodel_' + provider);
    const body = { provider };
    if (keyInput && keyInput.value) body.key = keyInput.value;
    if (modelInput && modelInput.value) body.model = modelInput.value;
    const data = await adminApi('/admin/api-keys/update', { method: 'POST', body: JSON.stringify(body) });
    if (data?.status === 'updated') {
        showToast(data.message, 'success');
    } else {
        showToast(data?.error || 'Update failed', 'error');
    }
}

// ─── Providers Tab ────────────────────────────────────

async function loadProviders() {
    const cont = document.getElementById('adminTabProviders');
    if (!cont) return;
    cont.innerHTML = '<div class="admin-loading">Loading providers</div>';
    const data = await adminApi('/admin/providers');
    if (!data) return;
    let html = '';
    data.providers.forEach(p => {
        html += '<div class="provider-card">'
            + '<div class="admin-card-title">' + p.name + ' <span style="font-size:10px;color:' + (p.enabled ? '#00d4ff' : '#ff5252') + ';">' + (p.enabled ? 'enabled' : 'disabled') + '</span></div>'
            + '<div class="p-url">' + (p.base_url || 'no URL') + '</div>'
            + '<div class="p-models">' + (p.models || []).map(m => '<span class="p-model-tag">' + m + '</span>').join('') + '</div>'
            + '<div style="margin-top:8px;display:flex;gap:4px;">'
            + '<button class="admin-btn admin-btn-sm" onclick="showAddModelForm(\'' + p.name + '\')">+ Model</button>'
            + '<button class="admin-btn admin-btn-sm danger" onclick="removeProvider(\'' + p.name + '\')">Remove</button>'
            + '</div></div>';
    });
    html += '<div class="admin-card" style="text-align:center;"><button class="admin-btn gold" onclick="showAddProviderFullForm()">+ Add New Provider</button></div>';
    cont.innerHTML = html;
}

function showAddProviderFullForm() {
    showModal('Add New Provider',
        '<input id="mod_provider_name" placeholder="Provider name (e.g. anthropic)">'
        + '<input id="mod_provider_url" placeholder="Base URL (e.g. https://api.anthropic.com/v1)">'
        + '<input id="mod_provider_key" placeholder="API key env var (e.g. ANTHROPIC_API_KEY)">',
        function() {
            const name = document.getElementById('mod_provider_name')?.value.trim();
            if (!name) { showToast('Provider name required', 'error'); return; }
            adminApi('/admin/providers/add', {
                method: 'POST', body: JSON.stringify({
                    name, base_url: document.getElementById('mod_provider_url')?.value || '',
                    api_key_env: document.getElementById('mod_provider_key')?.value || '',
                    models: [], enabled: true
                })
            }).then(d => {
                if (d?.status === 'added') { showToast('Provider added: ' + name, 'success'); loadProviders(); closeModal(); }
                else showToast(d?.error || 'Failed', 'error');
            });
        }
    );
}

async function removeProvider(name) {
    if (!confirm('Remove provider "' + name + '"?')) return;
    const data = await adminApi('/admin/providers/remove', { method: 'POST', body: JSON.stringify({ name }) });
    if (data?.status === 'removed') { showToast('Removed: ' + name, 'success'); loadProviders(); }
    else showToast(data?.error || 'Failed', 'error');
}

function showAddModelForm(provider) {
    showModal('Add Model to ' + provider,
        '<input id="mod_model_name" placeholder="Model name (e.g. claude-3-opus-20240229)">',
        function() {
            const model = document.getElementById('mod_model_name')?.value.trim();
            if (!model) { showToast('Model name required', 'error'); return; }
            adminApi('/admin/providers/models/add', {
                method: 'POST', body: JSON.stringify({ provider, model })
            }).then(d => {
                if (d?.status === 'added') { showToast('Model added', 'success'); loadProviders(); closeModal(); }
                else showToast(d?.error || 'Failed', 'error');
            });
        }
    );
}

// ─── Sessions Tab ─────────────────────────────────────

async function loadSessions() {
    const cont = document.getElementById('adminTabSessions');
    if (!cont) return;
    cont.innerHTML = '<div class="admin-loading">Loading sessions</div>';
    const data = await adminApi('/admin/sessions');
    if (!data) return;
    let html = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
        + '<span style="font-size:11px;color:rgba(255,215,0,0.4);">' + (data.count || 0) + ' sessions</span>'
        + '<input id="sessionSearch" placeholder="Search..." oninput="filterSessions()" style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,165,0,0.15);border-radius:4px;padding:4px 8px;color:#ffd700;font-family:monospace;font-size:11px;width:200px;outline:none;">'
        + '</div><div id="sessionList">';
    (data.sessions || []).forEach(s => {
        html += '<div class="session-item" onclick="toggleSessionDetail(\'' + s.id + '\')" data-sid="' + s.id + '">'
            + '<div class="s-meta"><span>' + (s.message_count || 0) + ' msgs</span><span>' + (s.updated_at || '') + '</span></div>'
            + '<div class="s-preview">' + escapeHtml((s.last_preview || s.name || 'Session ' + (s.id || '').slice(0, 8)).slice(0, 80)) + '</div>'
            + '<div class="s-id">' + (s.id || '').slice(0, 20) + '...</div>'
            + '<div class="session-detail" id="sdetail_' + (s.id || '') + '"></div>'
            + '</div>';
    });
    html += '</div>';
    cont.innerHTML = html;
}

async function toggleSessionDetail(sid) {
    const detail = document.getElementById('sdetail_' + sid);
    if (!detail) return;
    if (detail.classList.contains('open')) {
        detail.classList.remove('open');
        detail.innerHTML = '';
        return;
    }
    detail.innerHTML = '<div class="admin-loading">Loading messages</div>';
    detail.classList.add('open');
    const data = await adminApi('/admin/sessions/' + encodeURIComponent(sid));
    if (!data) return;
    let html = '';
    (data.messages || []).forEach(m => {
        html += '<div class="session-msg ' + m.role + '">[' + (m.timestamp || '') + '] ' + escapeHtml(m.content) + '</div>';
    });
    if (!html) html = '<div style="font-size:11px;color:rgba(255,215,0,0.3);">No messages</div>';
    html += '<div style="margin-top:6px;"><button class="admin-btn admin-btn-sm danger" onclick="deleteSession(\'' + sid + '\')">Delete Session</button></div>';
    detail.innerHTML = html;
}

function filterSessions() {
    const q = (document.getElementById('sessionSearch')?.value || '').toLowerCase();
    document.querySelectorAll('.session-item').forEach(el => {
        const text = el.textContent.toLowerCase();
        el.style.display = text.includes(q) ? 'block' : 'none';
    });
}

async function deleteSession(sid) {
    if (!confirm('Delete this session and all its messages?')) return;
    const data = await adminApi('/admin/sessions/delete', { method: 'POST', body: JSON.stringify({ session_id: sid }) });
    if (data?.status === 'deleted') { showToast('Session deleted', 'success'); loadSessions(); }
    else showToast(data?.error || 'Delete failed', 'error');
}

// ─── System Tab ───────────────────────────────────────

async function loadSystem() {
    const cont = document.getElementById('adminTabSystem');
    if (!cont) return;
    cont.innerHTML = '<div class="admin-loading">Loading system info</div>';
    const data = await adminApi('/admin/system');
    if (!data) return;
    let html = '<div class="sys-grid">'
        + '<div class="sys-card"><div class="s-value">' + (data.cpu_percent !== undefined ? data.cpu_percent + '%' : 'N/A') + '</div><div class="s-label">CPU</div></div>'
        + '<div class="sys-card"><div class="s-value">' + (data.memory?.percent !== undefined ? data.memory.percent + '%' : 'N/A') + '</div><div class="s-label">RAM</div></div>'
        + '<div class="sys-card"><div class="s-value">' + (data.disk?.percent !== undefined ? data.disk.percent + '%' : 'N/A') + '</div><div class="s-label">DISK</div></div>'
        + '<div class="sys-card"><div class="s-value">' + (data.uptime || 'N/A') + '</div><div class="s-label">UPTIME</div></div>'
        + '</div>';
    html += '<div class="admin-card"><div class="admin-card-title">Details</div>'
        + '<div style="font-size:11px;color:#aaddff;line-height:1.8;">'
        + '<b style="color:rgba(255,215,0,0.5);">Platform:</b> ' + (data.platform || 'N/A') + '<br>'
        + '<b style="color:rgba(255,215,0,0.5);">Python:</b> ' + (data.python_version || 'N/A') + '<br>'
        + '<b style="color:rgba(255,215,0,0.5);">Machine:</b> ' + (data.machine || 'N/A') + '<br>'
        + '<b style="color:rgba(255,215,0,0.5);">CPU Count:</b> ' + (data.cpu_count || 'N/A') + '<br>'
        + '<b style="color:rgba(255,215,0,0.5);">Hostname:</b> ' + (data.hostname || 'N/A') + '<br>'
        + '<b style="color:rgba(255,215,0,0.5);">Boot:</b> ' + (data.boot_time || 'N/A') + '<br>'
        + '<b style="color:rgba(255,215,0,0.5);">PID:</b> ' + (data.pid || 'N/A') + '<br>'
        + '</div></div>';
    html += '<div style="display:flex;gap:8px;margin-top:8px;">'
        + '<button class="admin-btn danger" onclick="restartApp()">Restart App</button>'
        + '<button class="admin-btn" onclick="clearCache()">Clear Cache</button>'
        + '</div>';
    cont.innerHTML = html;
}

async function restartApp() {
    if (!confirm('Restart the JARVIS server? This will cause brief downtime.')) return;
    const data = await adminApi('/admin/system/restart', { method: 'POST' });
    if (data?.status === 'restarting') {
        showToast('Server restarting...', 'success');
        setTimeout(() => { location.reload(); }, 3000);
    }
}

async function clearCache() {
    const data = await adminApi('/admin/cache/clear', { method: 'POST' });
    if (data?.status === 'cleared') showToast('Cache cleared', 'success');
    else showToast(data?.error || 'Failed', 'error');
}

// ─── Audit Tab ────────────────────────────────────────

async function loadAudit() {
    const cont = document.getElementById('adminTabAudit');
    if (!cont) return;
    cont.innerHTML = '<div class="admin-loading">Loading audit log</div>';
    const data = await adminApi('/admin/audit');
    if (!data) return;
    let html = '<div style="font-size:11px;color:rgba(255,215,0,0.4);margin-bottom:8px;">' + (data.count || 0) + ' entries</div>';
    (data.log || []).forEach(entry => {
        const time = entry.timestamp ? new Date(entry.timestamp * 1000).toLocaleString() : '';
        html += '<div class="admin-card" style="padding:8px 12px;margin-bottom:4px;">'
            + '<div style="font-size:10px;color:rgba(255,215,0,0.3);display:flex;gap:8px;">'
            + '<span>' + time + '</span><span>' + (entry.action || '') + '</span><span>' + (entry.ip || '') + '</span>'
            + '</div>'
            + '<div style="font-size:11px;color:#aaddff;margin-top:2px;">' + escapeHtml(entry.details || '') + '</div>'
            + '</div>';
    });
    if (!html) html = '<div class="admin-card" style="color:rgba(255,215,0,0.3);">No audit entries yet</div>';
    cont.innerHTML = html;
}

// ─── Database Tab ─────────────────────────────────────

function loadDbCollection() {
    const sel = document.getElementById('dbCollectionSelect');
    const cont = document.getElementById('dbResults');
    if (!sel || !cont) return;
    const col = sel.value;
    if (!col) { cont.textContent = 'Select a collection'; return; }
    cont.textContent = 'Querying...';
    adminApi('/admin/db/query', { method: 'POST', body: JSON.stringify({ collection: col, filter: {}, limit: 20 }) })
        .then(data => {
            if (!data) return;
            if (data.error) { cont.textContent = 'Error: ' + data.error; return; }
            cont.innerHTML = '<div style="font-size:10px;color:rgba(255,215,0,0.4);margin-bottom:4px;">' + (data.count || 0) + ' results</div>'
                + '<pre style="margin:0;font-size:11px;line-height:1.5;white-space:pre-wrap;word-break:break-all;">' + syntaxHighlight(JSON.stringify(data.results, null, 2)) + '</pre>';
        });
}

function syntaxHighlight(json) {
    return json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
        .replace(/: "([^"]+)"/g, ': <span class="json-string">"$1"</span>')
        .replace(/: (\d+\.?\d*)/g, ': <span class="json-number">$1</span>');
}

// ─── Modal ────────────────────────────────────────────

function showModal(title, content, onConfirm) {
    let overlay = document.getElementById('adminModalOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'adminModalOverlay';
        overlay.className = 'admin-modal-overlay';
        overlay.innerHTML = '<div class="admin-modal"><h3 id="modalTitle"></h3><div id="modalBody"></div>'
            + '<div class="admin-modal-actions">'
            + '<button class="admin-btn" onclick="closeModal()">Cancel</button>'
            + '<button class="admin-btn gold" id="modalConfirmBtn">Confirm</button>'
            + '</div></div>';
        document.body.appendChild(overlay);
    }
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalBody').innerHTML = content;
    const btn = document.getElementById('modalConfirmBtn');
    btn.onclick = onConfirm;
    overlay.classList.add('open');
}

function closeModal() {
    const overlay = document.getElementById('adminModalOverlay');
    if (overlay) overlay.classList.remove('open');
}

// ─── Admin Voice Commands (called from script.js) ────

function handleAdminVoiceCommand(text) {
    const t = text.toLowerCase().trim();
    if (isAdminLogoutTrigger(t) && adminMode) {
        adminApi('/admin/logout', { method: 'POST' });
        adminMode = false;
        updateAdminBadge();
        adminToken = null;
        closeAdminPanel();
        appendChat('assistant', '🔒 Admin session closed.');
        speak('Admin session closed.');
        return true;
    }
    if (t.includes("show files") || t.includes("list files") || t.includes("file manager")) {
        switchAdminTab('files'); return true;
    }
    if (t.includes("show config") || t.includes("configuration")) {
        switchAdminTab('config'); return true;
    }
    if (t.includes("api key") || t.includes("api keys")) {
        switchAdminTab('apikeys'); return true;
    }
    if (t.includes("show provider") || t.includes("list provider")) {
        switchAdminTab('providers'); return true;
    }
    if (t.includes("show session") || t.includes("list session")) {
        switchAdminTab('sessions'); return true;
    }
    if (t.includes("show system") || t.includes("system status") || t.includes("system info")) {
        switchAdminTab('system'); return true;
    }
    if (t.includes("audit") || t.includes("audit log")) {
        switchAdminTab('audit'); return true;
    }
    if (t.includes("database") || t.includes("db query")) {
        switchAdminTab('database'); return true;
    }
    return false;
}

// ─── Init ─────────────────────────────────────────────

function initAdminPanel() {
    const panelHtml = `
    <div class="admin-overlay" id="adminPanel">
        <div class="admin-header">
            <div><h1>🛡 ADMIN PANEL <span class="admin-badge">ACTIVE</span></h1></div>
            <button class="admin-exit-btn" onclick="closeAdminPanel()">EXIT</button>
        </div>
        <div class="admin-tabs">
            <button class="admin-tab active" data-tab="files" onclick="switchAdminTab('files')">Files</button>
            <button class="admin-tab" data-tab="config" onclick="switchAdminTab('config')">Config</button>
            <button class="admin-tab" data-tab="apikeys" onclick="switchAdminTab('apikeys')">API Keys</button>
            <button class="admin-tab" data-tab="providers" onclick="switchAdminTab('providers')">Providers</button>
            <button class="admin-tab" data-tab="sessions" onclick="switchAdminTab('sessions')">Sessions</button>
            <button class="admin-tab" data-tab="database" onclick="switchAdminTab('database')">Database</button>
            <button class="admin-tab" data-tab="system" onclick="switchAdminTab('system')">System</button>
            <button class="admin-tab" data-tab="audit" onclick="switchAdminTab('audit')">Audit</button>
        </div>
        <div class="admin-content" id="adminContent">
            <div class="admin-tab-content active" id="adminTabFiles"></div>
            <div class="admin-tab-content" id="adminTabConfig"></div>
            <div class="admin-tab-content" id="adminTabApikeys"></div>
            <div class="admin-tab-content" id="adminTabProviders"></div>
            <div class="admin-tab-content" id="adminTabSessions"></div>
            <div class="admin-tab-content" id="adminTabDatabase">
                <div class="admin-card">
                    <div class="admin-card-title">MongoDB Query</div>
                    <div class="db-collection-select">
                        <select id="dbCollectionSelect">
                            <option value="">Select collection...</option>
                            <option value="queries">queries</option>
                            <option value="cache">cache</option>
                            <option value="profile">profile</option>
                            <option value="admin_audit">admin_audit</option>
                        </select>
                        <button class="admin-btn admin-btn-sm gold" onclick="loadDbCollection()">Query</button>
                    </div>
                    <div class="db-results" id="dbResults">Select a collection and click Query</div>
                </div>
            </div>
            <div class="admin-tab-content" id="adminTabSystem"></div>
            <div class="admin-tab-content" id="adminTabAudit"></div>
        </div>
        <div class="admin-toast" id="adminToast"></div>
    </div>
    `;
    const div = document.createElement('div');
    div.innerHTML = panelHtml;
    document.body.appendChild(div.firstElementChild);
}

document.addEventListener('DOMContentLoaded', initAdminPanel);

function escapeHtml(str) {
    if (!str) return '';
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}
