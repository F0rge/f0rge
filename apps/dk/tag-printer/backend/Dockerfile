FROM python:3.10-slim

WORKDIR /app/apps/dk/tag-printer/backend

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY apps/dk/tag-printer/backend/pyproject.toml apps/dk/tag-printer/backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY apps/dk/tag-printer/backend/app ./app

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
