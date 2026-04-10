# ── Stage 1: builder ──────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
COPY app/requirements.txt .

# Install dependencies into an isolated prefix so stage 2 stays clean
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime ─────────────────────────────────────────
FROM python:3.12-slim

# Security: run as non-root
RUN useradd --create-home appuser
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ .

# Ownership
RUN chown -R appuser:appuser /app
USER appuser

# Runtime environment (overridden by Kubernetes env vars)
ENV APP_VERSION=v1 \
    APP_COLOR=#3B82F6 \
    ERROR_RATE=0.0 \
    PYTHONUNBUFFERED=1

EXPOSE 5000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"

CMD ["python", "app.py"]