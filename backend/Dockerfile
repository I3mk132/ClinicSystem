# ============================================================
# Clinic Booking System - Backend (FastAPI)
# Build:  docker build -t clinic-backend .
# Run:    see docker-compose.yml (recommended, especially with Portainer)
# ============================================================
FROM python:3.12-slim

# Never write .pyc files / never buffer stdout (logs appear immediately)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# tzdata so the TZ env var works (slot logic compares against local "today"/"now")
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so this layer is cached between code changes
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Run as a non-root user; /data holds the SQLite database (mounted as a volume)
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data
USER appuser

VOLUME /data
EXPOSE 8000

# No curl needed - use Python itself for the container healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/', timeout=4).status == 200 else 1)"

ENTRYPOINT ["docker-entrypoint.sh"]
