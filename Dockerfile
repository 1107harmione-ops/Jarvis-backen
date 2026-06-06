# ── JARVIS V3 Dockerfile ──
# Multi-stage build for minimal image size.

# ── Stage 1: Builder ──
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build deps + Python packages
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt && \
    pip install --user --no-cache-dir "uvicorn[standard]>=0.27"

# ── Stage 2: Runtime ──
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# ── Runtime config ──
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

# Start FastAPI (or switch to Flask by changing to: gunicorn app:app)
CMD ["uvicorn", "app_fastapi:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
