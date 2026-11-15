#!/bin/sh
set -eu
# Secret files are supplied by the host secret manager, never baked into images.
if [ -n "${BUYCYCLE_DATABASE_URL_FILE:-}" ]; then
  DATABASE_URL=$(cat "$BUYCYCLE_DATABASE_URL_FILE")
  export DATABASE_URL
fi
if [ -n "${BUYCYCLE_MIGRATION_DATABASE_URL_FILE:-}" ]; then
  MIGRATION_DATABASE_URL=$(cat "$BUYCYCLE_MIGRATION_DATABASE_URL_FILE")
  export MIGRATION_DATABASE_URL
fi
if [ -n "${BUYCYCLE_API_KEY_FILE:-}" ]; then
  BUYCYCLE_API_KEY=$(cat "$BUYCYCLE_API_KEY_FILE")
  export BUYCYCLE_API_KEY
fi
exec "$@"
