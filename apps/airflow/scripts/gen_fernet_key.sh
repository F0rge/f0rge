#!/usr/bin/env bash
# Optional helper: print Fernet key for AIRFLOW__CORE__FERNET_KEY.
set -euo pipefail
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
