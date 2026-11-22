#!/bin/sh
# A Railway volume mounted at the static directory is root-owned. Medusa's
# local file provider writes product photos there, and the server runs as node.
# Chown first, then drop privileges. Arguments are the container command so
# Railway's pre-deploy command runs as node too.
#
# `release` is the pre-deploy command: migrate, then bootstrap. Railway runs a
# pre-deploy command without a shell, so `&&` in it is never interpreted.
# The deploy block names this script, so it works whether Railway passes the
# command to the entrypoint or runs it in its place: drop our own path first.
set -eu
if [ "${1:-}" = "$0" ]; then shift; fi
static_dir="/app/apps/storefront/commerce/.medusa/server/static"
mkdir -p "$static_dir"
chown -R node:node "$static_dir"
medusa_bin=/app/apps/storefront/commerce/node_modules/.bin/medusa
if [ ! -f "$medusa_bin" ]; then
  medusa_bin=/app/node_modules/.bin/medusa
fi
case "${1:-start}" in
  start)
    if [ "$#" -gt 0 ]; then shift; fi
    set -- node "$medusa_bin" start "$@"
    ;;
  release)
    su-exec node node "$medusa_bin" db:migrate
    exec su-exec node node "$medusa_bin" exec ./src/scripts/bootstrap-storefront.js
    ;;
esac
exec su-exec node "$@"
