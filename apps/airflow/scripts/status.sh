#!/usr/bin/env bash
# Print health of the Pi airflow compose stack (containers, redis, celery, API).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

CELERY_APP="airflow.providers.celery.executors.celery_executor.app"

echo "=== compose ps ==="
docker compose -p airflow ps

echo
echo "=== docker stats (snapshot) ==="
ids="$(docker compose -p airflow ps -q 2>/dev/null || true)"
if [[ -n "${ids}" ]]; then
  # shellcheck disable=SC2086
  docker stats --no-stream ${ids}
else
  echo "(no containers)"
fi

echo
echo "=== redis ping ==="
docker compose -p airflow exec -T redis redis-cli ping || echo "redis ping FAILED"

echo
echo "=== celery inspect ping ==="
docker compose -p airflow exec -T airflow-worker \
  celery --app "${CELERY_APP}" inspect ping || echo "celery ping FAILED"

echo
echo "=== celery inspect active ==="
docker compose -p airflow exec -T airflow-worker \
  celery --app "${CELERY_APP}" inspect active || true

echo
echo "=== celery inspect stats (concurrency) ==="
docker compose -p airflow exec -T airflow-worker \
  celery --app "${CELERY_APP}" inspect stats 2>/dev/null \
  | head -n 80 || true

echo
echo "=== api version ==="
curl -sS -o /dev/null -w "http://127.0.0.1:8082/api/v2/version -> %{http_code}\n" \
  http://127.0.0.1:8082/api/v2/version || echo "api FAILED"

echo
echo "Flower (Tailscale): http://100.103.61.77:5555"
echo "UI (public):        https://airflow.leo-figueiredo.com"
