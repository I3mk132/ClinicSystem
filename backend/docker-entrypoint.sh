#!/bin/sh
set -e

# Create tables + default admin (+ demo data unless SEED_DEMO_DATA=false).
# The seed script is idempotent - safe on every container start.
python -m app.seed

# --proxy-headers so real client IPs/scheme survive a reverse proxy
# (Nginx Proxy Manager / Traefik / Caddy in front of this container).
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-1}" \
    --proxy-headers \
    --forwarded-allow-ips "*"
