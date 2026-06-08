# ── JARVIS V3 — Dockerfile ─────────────────────────────────────
# Multi-stage: builder → runtime

# ── Builder Stage ──
FROM python:3.12-slim AS builder

WORKDIR /build
COPY backend/requirements.txt .

RUN pip install --no-cache-dir --user -r requirements.txt

# ── Runtime Stage ──
FROM python:3.12-slim

# System dependencies for audio, OpenTelemetry
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    ffmpeg \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY backend/ /app/backend/
COPY .env /app/.env

# Create directories
RUN mkdir -p /app/data/faster_whisper_models /app/generated_audio /app/backend/static

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

EXPOSE 8001

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "4"]
