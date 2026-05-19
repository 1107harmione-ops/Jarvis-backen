#!/data/data/com.termux/files/usr/bin/bash
set -e
SCRIPT_VERSION="1.0.0"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $1"; }
step()  { echo -e "\n${CYAN}===== $1 =====${NC}"; }
ask()   { echo -e "${YELLOW}[?]${NC}  $1"; }
step "1. Environment Detection"
IS_TERMUX=false
if [ -d "/data/data/com.termux" ] || [ -n "$TERMUX_VERSION" ]; then
    IS_TERMUX=true
    info "Platform: Termux $TERMUX_VERSION"
else
    info "Platform: Linux (non-Termux)"
fi
ANDROID_SDK=$(getprop ro.build.version.sdk 2>/dev/null || echo "0")
info "Android SDK: $ANDROID_SDK"
BACKEND_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$BACKEND_DIR")"
info "Backend dir: $BACKEND_DIR"
if command -v python3 &>/dev/null; then
    PYTHON=python3
    ok "Python: $(python3 --version)"
elif command -v python &>/dev/null; then
    PYTHON=python
    ok "Python: $(python --version)"
else
    fail "Python not found. Installing..."
    pkg install python -y || apt install python3 -y
    PYTHON=python3
fi
run_fallback() {
    local desc="$1"; shift
    info "Trying: $desc"
    for cmd in "$@"; do
        if eval "$cmd" 2>/dev/null; then
            ok "$desc - succeeded"
            return 0
        fi
        warn "Method failed, trying next..."
    done
    fail "$desc - all methods failed"
    return 1
}
step "2. System Packages"
install_pkg() {
    local pkg="$1"
    if command -v pkg &>/dev/null; then
        pkg install -y "$pkg" 2>/dev/null && return 0
    fi
    if command -v apt &>/dev/null; then
        apt install -y "$pkg" 2>/dev/null && return 0
    fi
    if command -v apt-get &>/dev/null; then
        apt-get install -y "$pkg" 2>/dev/null && return 0
    fi
    if command -v apk &>/dev/null; then
        apk add "$pkg" 2>/dev/null && return 0
    fi
    return 1
}
PACKAGES="python git curl wget termux-api termux-services"
for pkg in $PACKAGES; do
    if install_pkg "$pkg"; then
        ok "Package: $pkg"
    else
        warn "Package $pkg not installed (may not be critical)"
    fi
done
step "3. Storage Setup"
if $IS_TERMUX; then
    if [ ! -d "$HOME/storage" ]; then
        ask "Run 'termux-setup-storage' to access shared storage?"
        echo -e "  ${YELLOW}This is needed for saving notes, screenshots, photos.${NC}"
        read -r -p "  Run now? [Y/n]: " ans
        if [[ "$ans" =~ ^[Yy]?$ ]]; then
            termux-setup-storage
            ok "Storage permission requested"
        else
            warn "Skipped. Notes/screenshots will use app-internal storage."
            mkdir -p "$HOME/.jarvis_notes"
            export JARVIS_NOTES_DIR="$HOME/.jarvis_notes"
            info "Fallback NOTES_DIR: $HOME/.jarvis_notes"
        fi
    else
        ok "Shared storage already configured"
    fi
fi
step "4. Python Dependencies"
REQUIREMENTS="$BACKEND_DIR/requirements.txt"
install_python_deps() {
    local req="$1"
    $PYTHON -m pip install --upgrade pip -q 2>/dev/null
    if $PYTHON -m pip install -r "$req" 2>/dev/null; then
        return 0
    fi
    warn "pip install failed, trying alternatives..."
    while IFS= read -r line; do
        [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
        pkg_name=$(echo "$line" | sed 's/[>=<].*//')
        $PYTHON -m pip install "$pkg_name" 2>/dev/null && continue
        $PYTHON -m pip install "$pkg_name" --no-deps 2>/dev/null && continue
        warn "Could not install $pkg_name"
    done < "$req"
}
install_python_deps "$REQUIREMENTS"
CRITICAL_PKGS="flask requests numpy"
for pkg in $CRITICAL_PKGS; do
    if $PYTHON -c "import $pkg" 2>/dev/null; then
        ok "Python: $pkg"
    else
        fail "Critical package $pkg is missing!"
        warn "Try: pip install $pkg"
    fi
done
OPTIONAL_PKGS="PIL bs4 lxml groq"
for pkg in $OPTIONAL_PKGS; do
    import_name="$pkg"
    [ "$pkg" = "PIL" ] && import_name="PIL"
    [ "$pkg" = "bs4" ] && import_name="bs4"
    if $PYTHON -c "import $import_name" 2>/dev/null; then
        ok "Python: $pkg"
    else
        warn "Optional package $pkg missing (some features may be limited)"
    fi
done
step "5. LLM / API Provider Configuration"
echo ""
echo -e "${CYAN}Choose your LLM provider:${NC}"
echo "  1) Groq (default) - FREE tier, very fast"
echo "  2) OpenAI - Paid, most compatible"
echo "  3) Google Gemini - FREE tier (60 req/min)"
echo "  4) Anthropic Claude - Paid"
echo "  5) DeepSeek - CHEAP (\$0.14/1M tokens)"
echo "  6) Hugging Face - FREE (rate limited)"
echo "  7) Together AI - FREE credits available"
echo "  8) Mistral AI - FREE tier available"
echo "  9) opencode Zen - FREE, no API key needed"
echo "  10) Skip (configure manually later)"
echo ""
read -r -p "  Select provider [1-10] (default=1): " provider_choice
provider_choice=${provider_choice:-1}
configure_provider() {
    local name="$1" key_var="$2" key_prompt="$3" model_var="$4" default_model="$5" base_var="$6" base_url="$7"
    echo ""
    ask "$key_prompt"
    read -r -p "  Enter key (or press Enter to skip): " api_key
    if [ -n "$api_key" ]; then
        echo "export $key_var='$api_key'" >> "$BACKEND_DIR/.env"
        ok "$name API key saved"
    else
        warn "$name key not set. The system will use a dummy key and may fail."
        echo "# $name key not configured" >> "$BACKEND_DIR/.env"
    fi
    echo "export $model_var='$default_model'" >> "$BACKEND_DIR/.env"
    [ -n "$base_var" ] && echo "export $base_var='$base_url'" >> "$BACKEND_DIR/.env"
}
case "$provider_choice" in
    1) configure_provider "Groq" "GROQ_CHAT_API_KEY" "Enter your Groq API key (get at https://console.groq.com/keys)" "GROQ_CHAT_MODEL" "llama-3.1-8b-instant" "GROQ_API_BASE" "https://api.groq.com/openai/v1"
       echo "export GROQ_CODING_MODEL='llama-3.3-70b-versatile'" >> "$BACKEND_DIR/.env"
       echo "export GROQ_COMPOUND_MODEL='llama-3.3-70b-versatile'" >> "$BACKEND_DIR/.env"
       PROVIDER_NAME="Groq"; PROVIDER_TYPE="free" ;;
    2) configure_provider "OpenAI" "GROQ_CHAT_API_KEY" "Enter your OpenAI API key (get at https://platform.openai.com/api-keys)" "GROQ_CHAT_MODEL" "gpt-4o-mini" "GROQ_API_BASE" "https://api.openai.com/v1"
       echo "export GROQ_CODING_MODEL='gpt-4o-mini'" >> "$BACKEND_DIR/.env"
       echo "export GROQ_COMPOUND_MODEL='gpt-4o'" >> "$BACKEND_DIR/.env"
       PROVIDER_NAME="OpenAI"; PROVIDER_TYPE="paid" ;;
    3) configure_provider "Gemini" "GROQ_CHAT_API_KEY" "Enter your Gemini API key (get at https://aistudio.google.com/apikey)" "GROQ_CHAT_MODEL" "gemini-1.5-flash" "GROQ_API_BASE" "https://generativelanguage.googleapis.com/v1beta"
       echo "export GROQ_CODING_MODEL='gemini-1.5-flash'" >> "$BACKEND_DIR/.env"
       echo "export GROQ_COMPOUND_MODEL='gemini-1.5-pro'" >> "$BACKEND_DIR/.env"
       PROVIDER_NAME="Gemini"; PROVIDER_TYPE="free" ;;
    4) configure_provider "Claude" "GROQ_CHAT_API_KEY" "Enter your Anthropic API key (get at https://console.anthropic.com/)" "GROQ_CHAT_MODEL" "claude-3-haiku-20240307" "GROQ_API_BASE" "https://api.anthropic.com/v1"
       echo "export GROQ_CODING_MODEL='claude-3-haiku-20240307'" >> "$BACKEND_DIR/.env"
       echo "export GROQ_COMPOUND_MODEL='claude-3-sonnet-20240229'" >> "$BACKEND_DIR/.env"
       PROVIDER_NAME="Claude"; PROVIDER_TYPE="paid" ;;
    5) configure_provider "DeepSeek" "GROQ_CHAT_API_KEY" "Enter your DeepSeek API key (get at https://platform.deepseek.com/)" "GROQ_CHAT_MODEL" "deepseek-chat" "GROQ_API_BASE" "https://api.deepseek.com"
       echo "export GROQ_CODING_MODEL='deepseek-chat'" >> "$BACKEND_DIR/.env"
       echo "export GROQ_COMPOUND_MODEL='deepseek-reasoner'" >> "$BACKEND_DIR/.env"
       PROVIDER_NAME="DeepSeek"; PROVIDER_TYPE="paid" ;;
    6) configure_provider "HuggingFace" "GROQ_CHAT_API_KEY" "Enter your Hugging Face token (get at https://huggingface.co/settings/tokens)" "GROQ_CHAT_MODEL" "mistralai/Mistral-7B-Instruct-v0.3" "GROQ_API_BASE" "https://api-inference.huggingface.co/models"
       echo "export GROQ_CODING_MODEL='codellama/CodeLlama-34b-Instruct-hf'" >> "$BACKEND_DIR/.env"
       echo "export GROQ_COMPOUND_MODEL='mistralai/Mixtral-8x7B-Instruct-v0.1'" >> "$BACKEND_DIR/.env"
       PROVIDER_NAME="HuggingFace"; PROVIDER_TYPE="free" ;;
    7) configure_provider "TogetherAI" "GROQ_CHAT_API_KEY" "Enter your Together AI key (get at https://api.together.xyz/settings/api-keys)" "GROQ_CHAT_MODEL" "meta-llama/Llama-3.3-70B-Instruct-Turbo" "GROQ_API_BASE" "https://api.together.xyz/v1"
       echo "export GROQ_CODING_MODEL='codellama/CodeLlama-34b-Instruct-hf'" >> "$BACKEND_DIR/.env"
       echo "export GROQ_COMPOUND_MODEL='meta-llama/Llama-3.3-70B-Instruct-Turbo'" >> "$BACKEND_DIR/.env"
       PROVIDER_NAME="TogetherAI"; PROVIDER_TYPE="free" ;;
    8) configure_provider "Mistral" "GROQ_CHAT_API_KEY" "Enter your Mistral API key (get at https://api.mistral.ai/api-keys/)" "GROQ_CHAT_MODEL" "mistral-small-latest" "GROQ_API_BASE" "https://api.mistral.ai/v1"
       echo "export GROQ_CODING_MODEL='codestral-latest'" >> "$BACKEND_DIR/.env"
       echo "export GROQ_COMPOUND_MODEL='mistral-large-latest'" >> "$BACKEND_DIR/.env"
       PROVIDER_NAME="Mistral"; PROVIDER_TYPE="free" ;;
    9) configure_provider "opencodeZen" "GROQ_CHAT_API_KEY" "Enter your opencode API key (get at https://opencode.ai) or press Enter for free tier" "GROQ_CHAT_MODEL" "opencode-zen" "GROQ_API_BASE" "https://api.opencode.ai/v1"
       echo "export GROQ_CODING_MODEL='opencode-zen'" >> "$BACKEND_DIR/.env"
       echo "export GROQ_COMPOUND_MODEL='opencode-zen'" >> "$BACKEND_DIR/.env"
       PROVIDER_NAME="opencodeZen"; PROVIDER_TYPE="free" ;;
    10) warn "Skipping LLM provider config. You'll need to set GROQ_CHAT_API_KEY manually."
       echo "# LLM provider not configured during setup" >> "$BACKEND_DIR/.env"
       PROVIDER_NAME="none"; PROVIDER_TYPE="none" ;;
esac
step "6. Search Provider Configuration"
echo ""
echo -e "${CYAN}Choose your Search / Web Research provider:${NC}"
echo "  1) SerpAPI (default) - Paid (100 free calls/month)"
echo "  2) DuckDuckGO - FREE, no API key needed"
echo "  3) Google Programmable Search - FREE (100 queries/day)"
echo "  4) Skip (configure later)"
echo ""
read -r -p "  Select search provider [1-4] (default=1): " search_choice
search_choice=${search_choice:-1}
case "$search_choice" in
    1) ask "Enter your SerpAPI key (get at https://serpapi.com/)"
       read -r -p "  Key: " serp_key
       if [ -n "$serp_key" ]; then
           echo "export SERP_API_KEY='$serp_key'" >> "$BACKEND_DIR/.env"
           ok "SerpAPI key saved"
       else
           warn "SerpAPI key not set. Web search features will be limited."
       fi ;;
    2) ok "DuckDuckGo selected - no API key needed!"
       $PYTHON -m pip install duckduckgo-search -q 2>/dev/null && ok "duckduckgo-search installed"
       echo "# Using DuckDuckGo (no API key needed)" >> "$BACKEND_DIR/.env"
       echo "export SEARCH_PROVIDER='duckduckgo'" >> "$BACKEND_DIR/.env" ;;
    3) ask "Enter your Google API key:"; read -r -p "  Key: " google_key
       ask "Enter your Search Engine ID (cx):"; read -r -p "  CX: " google_cx
       if [ -n "$google_key" ] && [ -n "$google_cx" ]; then
           echo "export GOOGLE_API_KEY='$google_key'" >> "$BACKEND_DIR/.env"
           echo "export GOOGLE_CX='$google_cx'" >> "$BACKEND_DIR/.env"
           ok "Google Programmable Search configured"
       else
           warn "Missing key or CX. Search features may not work."
       fi ;;
    4) warn "Search provider skipped. Manual config needed later." ;;
esac
step "7. News Provider Configuration"
echo ""
echo -e "${CYAN}Choose your News provider:${NC}"
echo "  1) NewsAPI (default) - 100 free requests/day"
echo "  2) GNews - FREE (100 requests/day)"
echo "  3) RSS Feeds - FREE, no API key"
echo "  4) Skip (configure later)"
echo ""
read -r -p "  Select news provider [1-4] (default=1): " news_choice
news_choice=${news_choice:-1}
case "$news_choice" in
    1) ask "Enter your NewsAPI key (get at https://newsapi.org/register):"
       read -r -p "  Key: " news_key
       if [ -n "$news_key" ]; then
           echo "export NEWS_API_KEY='$news_key'" >> "$BACKEND_DIR/.env"
           ok "NewsAPI key saved"
       else
           warn "NewsAPI key not set."
       fi ;;
    2) ask "Enter your GNews API key (get at https://gnews.io/):"
       read -r -p "  Key: " gnews_key
       if [ -n "$gnews_key" ]; then
           echo "export NEWS_API_KEY='$gnews_key'" >> "$BACKEND_DIR/.env"
           echo "export NEWS_PROVIDER='gnews'" >> "$BACKEND_DIR/.env"
           ok "GNews key saved"
       else
           warn "GNews key not set."
       fi ;;
    3) ok "RSS Feeds selected - no API key needed!"
       $PYTHON -m pip install feedparser -q 2>/dev/null && ok "feedparser installed"
       echo "# Using RSS feeds (no API key)" >> "$BACKEND_DIR/.env"
       echo "export NEWS_PROVIDER='rss'" >> "$BACKEND_DIR/.env" ;;
    4) warn "News provider skipped. Manual config needed later." ;;
esac
step "8. Port Configuration"
DEFAULT_PORT=8001
ask "Which port should the backend listen on? [default: $DEFAULT_PORT]"
read -r -p "  Port: " custom_port
PORT=${custom_port:-$DEFAULT_PORT}
if command -v ss &>/dev/null; then
    if ss -tln | grep -q ":$PORT "; then
        warn "Port $PORT is already in use!"
        ask "Try a different port? [Y/n]: " change_port
        if [[ "$change_port" =~ ^[Yy]?$ ]]; then
            read -r -p "  New port: " PORT
        fi
    fi
elif command -v netstat &>/dev/null; then
    if netstat -tln 2>/dev/null | grep -q ":$PORT "; then
        PORT=$((PORT+1))
    fi
fi
echo "export PORT=$PORT" >> "$BACKEND_DIR/.env"
ok "Port: $PORT"
step "9. Environment File"
ENV_LOADER="$BACKEND_DIR/.env"
chmod 600 "$ENV_LOADER" 2>/dev/null || true
cat > "$BACKEND_DIR/start.sh" << 'STARTSCRIPT'
#!/data/data/com.termux/files/usr/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi
export PORT="${PORT:-8001}"
export GROQ_API_BASE="${GROQ_API_BASE:-https://api.groq.com/openai/v1}"
export GROQ_CHAT_MODEL="${GROQ_CHAT_MODEL:-llama-3.1-8b-instant}"
echo "JARVIS Backend starting on port $PORT..."
echo "Provider: ${PROVIDER_NAME:-custom} (${PROVIDER_TYPE:-configured})"
echo "Model: $GROQ_CHAT_MODEL"
exec python app_productivity.py
STARTSCRIPT
chmod +x "$BACKEND_DIR/start.sh"
ok "Created $BACKEND_DIR/start.sh"
step "10. Multi-Provider LLM Adapter"
cat > "$BACKEND_DIR/core/llm_adapter.py" << 'ADAPTER'
import json, os, re, requests
GROQ_API_BASE = os.environ.get("GROQ_API_BASE", "https://api.groq.com/openai/v1")
GROQ_CHAT_API_KEY = os.environ.get("GROQ_CHAT_API_KEY", "")
GROQ_CHAT_MODEL = os.environ.get("GROQ_CHAT_MODEL", "llama-3.1-8b-instant")
PROVIDER_HEADERS = {
    "api.anthropic.com": lambda key: {"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
    "generativelanguage.googleapis.com": lambda key: {"Content-Type": "application/json"},
}
def get_headers():
    base = GROQ_API_BASE.lower()
    for domain, header_fn in PROVIDER_HEADERS.items():
        if domain in base:
            return header_fn(GROQ_CHAT_API_KEY)
    return {"Authorization": f"Bearer {GROQ_CHAT_API_KEY}", "Content-Type": "application/json"}
def adapt_payload(messages, model=None, temperature=0.7, max_tokens=1024):
    base = GROQ_API_BASE.lower()
    model = model or GROQ_CHAT_MODEL
    if "anthropic.com" in base:
        system_msg = ""; user_msgs = []
        for m in messages:
            if m["role"] == "system": system_msg = m["content"]
            else: user_msgs.append(m)
        return {"model": model, "system": system_msg, "messages": user_msgs, "max_tokens": max_tokens, "temperature": temperature}
    if "generativelanguage.googleapis.com" in base:
        contents = []
        for m in messages:
            role = "user" if m["role"] in ("user", "system") else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        return {"contents": contents, "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}}
    return {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
def adapt_response(response_json, base_url):
    base = base_url.lower()
    if "anthropic.com" in base:
        content = response_json.get("content", [{}])
        return content[0].get("text", "") if content else ""
    if "generativelanguage.googleapis.com" in base:
        candidates = response_json.get("candidates", [{}])
        content = candidates[0].get("content", {})
        parts = content.get("parts", [{}])
        return parts[0].get("text", "") if parts else ""
    choices = response_json.get("choices", [{}])
    message = choices[0].get("message", {})
    return message.get("content", "")
def llm_completion(messages, model=None, temperature=0.7, max_tokens=1024):
    if not GROQ_CHAT_API_KEY:
        return "[LLM not configured - set GROQ_CHAT_API_KEY in .env]"
    payload = adapt_payload(messages, model, temperature, max_tokens)
    headers = get_headers()
    base = GROQ_API_BASE.rstrip("/")
    if "generativelanguage.googleapis.com" in base:
        url = f"{base}/models/{GROQ_CHAT_MODEL}:generateContent?key={GROQ_CHAT_API_KEY}"
    elif "anthropic.com" in base:
        url = f"{base}/messages"
    else:
        url = f"{base}/chat/completions"
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        return adapt_response(r.json(), base)
    except requests.exceptions.Timeout:
        return "[LLM timeout - provider may be slow or unreachable]"
    except requests.exceptions.HTTPError as e:
        status = r.status_code if 'r' in dir() else '?'
        body = r.text[:500] if 'r' in dir() else ''
        return f"[LLM error {status}: {e}. Body: {body}]"
    except Exception as e:
        return f"[LLM error: {e}]"
def patch_groq_completion(module):
    if hasattr(module, "groq_completion"):
        module.groq_completion = llm_completion
        return True
    return False
ADAPTER
ok "Created multi-provider LLM adapter: core/llm_adapter.py"
step "11. Database Initialization"
if $PYTHON -c "
import sys
sys.path.insert(0, '$BACKEND_DIR')
from core.data_center import DataCenter
dc = DataCenter()
stats = dc.stats()
print(f'Database OK - {stats[\"total_entries\"]} entries, {len(stats[\"entries_by_category\"])} categories')
" 2>/dev/null; then
    ok "DataCenter initialized successfully"
else
    warn "DataCenter initialization had issues. Check permissions."
fi
step "12. Quick Test"
echo ""
info "Starting backend for quick health check..."
cd "$BACKEND_DIR"
export PORT="${PORT:-8001}"
export GROQ_API_BASE="${GROQ_API_BASE:-https://api.groq.com/openai/v1}"
export GROQ_CHAT_MODEL="${GROQ_CHAT_MODEL:-llama-3.1-8b-instant}"
$PYTHON app_productivity.py &
SERVER_PID=$!
sleep 2
if command -v curl &>/dev/null; then
    HEALTH=$(curl -s http://127.0.0.1:$PORT/health 2>/dev/null)
    if [ -n "$HEALTH" ]; then
        ok "Health endpoint: $HEALTH"
    else
        warn "Health check failed. Server may need more time."
    fi
elif command -v wget &>/dev/null; then
    HEALTH=$(wget -qO- http://127.0.0.1:$PORT/health 2>/dev/null)
    if [ -n "$HEALTH" ]; then
        ok "Health endpoint: $HEALTH"
    else
        warn "Health check failed."
    fi
fi
kill $SERVER_PID 2>/dev/null; wait $SERVER_PID 2>/dev/null
echo ""; ok "Quick test completed"
step "13. Auto-Start Configuration"
echo ""
echo -e "${CYAN}Choose auto-start method:${NC}"
echo "  1) Termux:Boot (recommended) - starts on device boot"
echo "  2) Manual start - you run 'start.sh' yourself"
echo "  3) Screen session - runs in background via 'screen'"
echo ""
read -r -p "  Select [1-3] (default=2): " autostart_choice
autostart_choice=${autostart_choice:-2}
case "$autostart_choice" in
    1) BOOT_DIR="$HOME/.termux/boot"; mkdir -p "$BOOT_DIR"
       cp "$BACKEND_DIR/start.sh" "$BOOT_DIR/start-jarvis.sh"; chmod +x "$BOOT_DIR/start-jarvis.sh"
       ok "Termux:Boot script installed at $BOOT_DIR/start-jarvis.sh"
       warn "Install Termux:Boot from F-Droid and reboot." ;;
    2) ok "Manual start chosen. Run: cd $BACKEND_DIR && bash start.sh" ;;
    3) if command -v screen &>/dev/null; then
           screen -dmS jarvis bash -c "cd $BACKEND_DIR && bash start.sh"
           ok "Started in screen session 'jarvis'"
       else
           warn "screen not installed. Falling back to manual start."
       fi ;;
esac
step "14. Setup Complete"
echo ""
echo -e "${GREEN}+==================================================+${NC}"
echo -e "${GREEN}|          JARVIS Backend - Setup Complete            |${NC}"
echo -e "${GREEN}+==================================================+${NC}"
echo ""
echo -e "  ${CYAN}Backend:${NC}  $BACKEND_DIR"
echo -e "  ${CYAN}Port:${NC}     $PORT"
echo -e "  ${CYAN}Provider:${NC} ${PROVIDER_NAME:-custom} (${PROVIDER_TYPE:-configured})"
echo -e "  ${CYAN}Model:${NC}    ${GROQ_CHAT_MODEL:-llama-3.1-8b-instant}"
echo ""
echo -e "  ${YELLOW}To start:${NC}"
echo "    cd $BACKEND_DIR && bash start.sh"
echo ""
echo -e "  ${YELLOW}Environment:${NC}"
echo "    Edit $BACKEND_DIR/.env to change keys/models"
echo "    Edit $BACKEND_DIR/core/config.py for advanced settings"
echo ""
if [ "$PROVIDER_TYPE" = "none" ]; then
    warn "No API provider configured! Edit $BACKEND_DIR/.env to set your keys."
    echo ""
    echo "  Quick config:"
    echo "    echo \"export GROQ_CHAT_API_KEY='your_key_here'\" >> $BACKEND_DIR/.env"
    echo "    echo \"export GROQ_CHAT_MODEL='llama-3.1-8b-instant'\" >> $BACKEND_DIR/.env"
fi
echo ""
echo -e "${GREEN}Happy building! - JARVIS Team${NC}"
echo ""
