#!/usr/bin/env bash
set -euo pipefail
echo "Unpausing meal_analysis DAG..."
airflow dags unpause meal_analysis || true
echo "Bootstrap complete."
