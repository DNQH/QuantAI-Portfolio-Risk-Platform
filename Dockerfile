# QuantAI — single-container image: FastAPI API + built React UI on one port.
#
#   docker build -t quantai .
#   docker run --rm -p 8000:8000 -e GEMINI_API_KEY=... quantai
#   open http://localhost:8000
#
# Works as-is on Docker-based hosts (Render, Railway, Fly.io, Cloud Run, ...):
# the server listens on $PORT when the platform provides one.

# ---------- Stage 1: build the frontend ----------
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: Python runtime ----------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY backend/requirements.txt backend/requirements-deploy.txt ./backend/
RUN pip install -r backend/requirements-deploy.txt

COPY backend/app ./backend/app
COPY --from=web /web/dist ./frontend/dist

# Unprivileged user; SQLite lives in /data (mount a volume there to persist saved portfolios).
RUN useradd --create-home --uid 10001 quantai \
    && mkdir -p /data \
    && chown quantai:quantai /data
USER quantai

ENV QUANTAI_ENV=production \
    QUANTAI_DB_PATH=/data/quantai.db \
    QUANTAI_FRONTEND_DIST=/app/frontend/dist \
    QUANTAI_ENABLE_YFINANCE_FALLBACK=true \
    PORT=8000

WORKDIR /app/backend
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/v1/health', timeout=4)" || exit 1

# --proxy-headers: trust X-Forwarded-For from the platform's load balancer so per-client
# rate limits key on the real visitor IP. Single worker: the in-memory rate limiter and
# SQLite are process-local.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*' --workers 1"]
