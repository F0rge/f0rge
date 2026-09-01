FROM python:3.10-slim

RUN groupadd --gid 1000 app && useradd --uid 1000 --gid 1000 --create-home app

# Repo-root build context: mirror the monorepo layout so shared libs resolve
# at the same relative paths as in the repo.
WORKDIR /app/apps/vellano/backend

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY apps/vellano/backend/pyproject.toml apps/vellano/backend/uv.lock ./
COPY libs/backend/core/pyproject.toml /app/libs/backend/core/pyproject.toml
COPY libs/backend/core/src /app/libs/backend/core/src
COPY libs/backend/db/pyproject.toml /app/libs/backend/db/pyproject.toml
COPY libs/backend/db/src /app/libs/backend/db/src
# S3 packing PDFs need f0rge-storage (runtime path dep); must exist before uv sync.
COPY libs/backend/storage/pyproject.toml /app/libs/backend/storage/pyproject.toml
COPY libs/backend/storage/src /app/libs/backend/storage/src
# uv.lock records f0rge-testing even for --no-dev; `uv run` at start needs the path.
COPY libs/backend/testing/pyproject.toml /app/libs/backend/testing/pyproject.toml
COPY libs/backend/testing/src /app/libs/backend/testing/src
RUN uv sync --frozen --no-dev

COPY apps/vellano/backend/app ./app
COPY apps/vellano/backend/alembic.ini ./alembic.ini
COPY apps/vellano/backend/migrations ./migrations

RUN chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
