# JARVIS Backend

AI assistant backend deployed on Render. Powers the JARVIS Android app with chat, voice, task automation, and memory.

## Features

- **Voice-to-Voice**: Say "Jarvis" to wake, speak naturally, hear spoken responses
- **Chat Mode**: Type messages in the persistent chat bar
- **Auto-Save Memory**: Conversation sessions saved every 20 seconds
- **Session Browsing**: View past conversations via the sidebar
- **Image Generation**: Generate images via AI
- **Task Automation**: Control apps, WiFi, Bluetooth, volume, brightness, and more
- **Knowledge Base**: Searchable integrated knowledge center
- **Auto-Skills**: Learns and applies reusable skills

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Send a message to JARVIS |
| `/history` | GET | Get recent chat history |
| `/sessions` | GET | List past sessions |
| `/sessions/<id>` | GET | Get session messages |
| `/memory/save` | POST | Save session checkpoint |
| `/health` | GET | Health check |
| `/status` | GET | System status |
| `/knowledge/search` | POST | Search knowledge base |

## Deploy on Render

1. Connect this repo to Render
2. Set environment variables:
   - `GROQ_CHAT_API_KEY` - Your Groq API key
   - `JARVIS_SHUTDOWN_TOKEN` - Optional, only if you intend to enable the shutdown endpoint
3. Start command: `gunicorn app:app`

## Android APK

Download `Jarvis.apk` from this repo to install on your device.
