#!/bin/sh
# Publish the built UI into the data dirs (data JSON comes from the tracker), then serve both dashboards.
set -eu
for k in bikes wheels; do
  d="/data/$k"; mkdir -p "$d/vendor"
  cp "/app/site/index-$k.html" "$d/index.html"
  cp /app/dashboard/vendor/* "$d/vendor/"
  gzip -kf9 "$d/index.html" "$d/vendor/primer.css" "$d/vendor/primer_view_components.css" "$d/vendor/chart.umd.min.js"
done
/app/.venv/bin/python /app/dashboard/serve.py 8095 /data/bikes &
/app/.venv/bin/python /app/dashboard/serve.py 8096 /data/wheels &
wait
