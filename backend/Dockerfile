FROM python:3.10-slim

# Match host user `leo` (uid 1000) so vault writes land owned correctly
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid 1000 --create-home app

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY ./app ./app
COPY ./scripts ./scripts
COPY ./alembic.ini ./alembic.ini
COPY ./migrations ./migrations
# Ship the dietary reference JSON files under a separate path so they
# aren't shadowed by the runtime /app/data volume mount that holds health.db.
COPY ./data /app/data-seed

# Entrypoint runs `alembic upgrade head` before the CMD when RUN_MIGRATIONS=1.
# See backend/docker-entrypoint.sh for the opt-in mechanic (only the backend
# service sets the flag; mcp-server and embedding-worker share the image but
# skip migrations to avoid racing on DDL locks).
COPY ./docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Tell the seed scripts and the lifespan hook where to find the JSON files.
ENV DIETARY_DATA_DIR=/app/data-seed

RUN mkdir -p /app/data /app/photos /app/lab_attachments && chown -R app:app /app

USER app

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
