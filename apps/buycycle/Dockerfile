# Buycycle dashboards + tracker for the Pi (Coolify, Dockerfile build, base directory "/").
# Static servers on 8095 (bikes) and 8096 (wheels). Data lives on the /data volume, never in the image.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /bin/uv
ENV TZ=Europe/Luxembourg PYTHONUNBUFFERED=1 UV_PROJECT_ENVIRONMENT=/app/.venv \
    BUYCYCLE_DB=/data/buycycle.turso.db BUYCYCLE_OUT_BIKES=/data/bikes BUYCYCLE_OUT_WHEELS=/data/wheels
WORKDIR /app
COPY apps/buycycle/pyproject.toml apps/buycycle/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY apps/buycycle/tracker ./tracker
COPY apps/buycycle/dashboard ./dashboard
COPY apps/buycycle/entrypoint.sh apps/buycycle/run-tracker.sh ./
RUN /app/.venv/bin/python dashboard/render.py dashboard/index.tpl.html /app/site && chmod +x entrypoint.sh run-tracker.sh \
 && useradd -u 1000 -m leo && mkdir -p /data && chown -R 1000:1000 /data
USER 1000:1000
VOLUME ["/data"]
EXPOSE 8095 8096
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request as u;u.urlopen('http://127.0.0.1:8095/');u.urlopen('http://127.0.0.1:8096/')"
ENTRYPOINT ["/app/entrypoint.sh"]
