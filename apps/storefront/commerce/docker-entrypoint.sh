#!/bin/sh
# A Railway volume mounted at the static directory is root-owned. Medusa's
# local file provider writes product photos there, and the server runs as node.
# Chown first, then drop privileges. Arguments are the container command so
# Railway's pre-deploy migrate runs as node too.
set -eu
static_dir="/app/apps/storefront/commerce/.medusa/server/static"
mkdir -p "$static_dir"
chown -R node:node "$static_dir"
if [ "$#" -eq 0 ]; then
  set -- node /app/node_modules/.bin/medusa start
fi
exec su-exec node "$@"
