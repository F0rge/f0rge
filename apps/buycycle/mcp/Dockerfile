# Buycycle read-only MCP. Tailscale only — no public hostname, no Cloudflare tunnel.
# Container port 8097. On the Pi, publish 100.103.61.77:8097 (not 0.0.0.0).
# Build context is the repo root (Coolify base directory "/").
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /bin/uv
ENV TZ=Europe/Luxembourg PYTHONUNBUFFERED=1 UV_PROJECT_ENVIRONMENT=/app/.venv \
    BUYCYCLE_DB=/data/buycycle.turso.db \
    BUYCYCLE_MCP_HOST=0.0.0.0 \
    BUYCYCLE_MCP_PORT=8097
WORKDIR /app
COPY apps/buycycle/mcp/pyproject.toml apps/buycycle/mcp/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY apps/buycycle/mcp/buycycle_mcp ./buycycle_mcp
COPY apps/buycycle/mcp/healthcheck.py ./healthcheck.py
COPY apps/buycycle/tracker/fees.py apps/buycycle/tracker/market.py ./tracker/
RUN useradd -u 1000 -m leo && mkdir -p /data && chown 1000:1000 /data
USER 1000:1000
EXPOSE 8097
HEALTHCHECK --interval=60s --timeout=5s CMD python /app/healthcheck.py
ENTRYPOINT ["/app/.venv/bin/python", "-m", "buycycle_mcp"]
