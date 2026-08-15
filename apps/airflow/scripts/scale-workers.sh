#!/usr/bin/env bash
# Scale Celery workers on the Pi airflow compose project. Usage: ./scripts/scale-workers.sh 1|2|3
set -euo pipefail

N="${1:-}"
if [[ ! "${N}" =~ ^[123]$ ]]; then
  echo "usage: $0 1|2|3" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

export AIRFLOW_UID="${AIRFLOW_UID:-1000}"
docker compose -p airflow up -d --scale "airflow-worker=${N}" --no-recreate
echo "airflow-worker scaled to ${N}"
docker compose -p airflow ps airflow-worker
