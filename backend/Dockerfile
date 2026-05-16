FROM python:3.10-slim

# Match host user `leo` (uid 1000) so vault writes land owned correctly
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid 1000 --create-home app

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY ./app ./app
COPY ./scripts ./scripts
# Ship the dietary reference JSON files under a separate path so they
# aren't shadowed by the runtime /app/data volume mount that holds health.db.
COPY ./data /app/data-seed

# Tell the seed scripts and the lifespan hook where to find the JSON files.
ENV DIETARY_DATA_DIR=/app/data-seed

RUN mkdir -p /app/data /app/photos /app/lab_attachments && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
