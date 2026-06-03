#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi
if [ "$1" = "--port" ] && [ -n "$2" ]; then
    export PORT="$2"
fi
export PORT="${PORT:-8001}"
export GROQ_API_BASE="${GROQ_API_BASE:-https://api.groq.com/openai/v1}"
export GROQ_CHAT_MODEL="${GROQ_CHAT_MODEL:-llama-3.3-70b-versatile}"
if [ -z "$GROQ_CHAT_API_KEY" ]; then
    echo ""
    echo "  [WARN] GROQ_CHAT_API_KEY is not set!"
    echo "  Set it with:"
    echo "    export GROQ_CHAT_API_KEY='gsk_your_key_here'"
    echo "  Or create a .env file in $SCRIPT_DIR"
    echo ""
fi
echo ""
echo "  JARVIS Productivity Backend"
echo "  Port:      $PORT"
echo "  API Base:  $GROQ_API_BASE"
echo "  Model:     $GROQ_CHAT_MODEL"
echo "  Key Set:   $([ -n \"$GROQ_CHAT_API_KEY\" ] && echo 'Yes' || echo 'No')"
echo "  Start Cmd: python app_productivity.py"
echo "  Health:    curl http://127.0.0.1:$PORT/health"
echo ""
exec python app_productivity.py