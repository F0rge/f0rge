#!/usr/bin/env bash
# Sync Tigris (Fly) photos → Railway Bucket (S3-compatible).
#
# Requires AWS CLI v2. Source = Fly Tigris credentials; dest = Railway bucket creds.
#
# Usage:
#   export SRC_AWS_ACCESS_KEY_ID=... SRC_AWS_SECRET_ACCESS_KEY=... SRC_BUCKET=f0rge-marrow-dev-photos
#   export DST_AWS_ACCESS_KEY_ID=... DST_AWS_SECRET_ACCESS_KEY=... DST_BUCKET=...
#   ./apps/marrow/backend/scripts/railway_bucket_sync.sh
set -euo pipefail

: "${SRC_AWS_ACCESS_KEY_ID:?}"
: "${SRC_AWS_SECRET_ACCESS_KEY:?}"
: "${SRC_BUCKET:?}"
: "${DST_AWS_ACCESS_KEY_ID:?}"
: "${DST_AWS_SECRET_ACCESS_KEY:?}"
: "${DST_BUCKET:?}"

SRC_ENDPOINT="${SRC_ENDPOINT:-https://fly.storage.tigris.dev}"
DST_ENDPOINT="${DST_ENDPOINT:-https://t3.storageapi.dev}"
SRC_REGION="${SRC_REGION:-auto}"
DST_REGION="${DST_REGION:-auto}"

export AWS_DEFAULT_REGION=auto

echo "==> Listing source s3://${SRC_BUCKET} via ${SRC_ENDPOINT}"
AWS_ACCESS_KEY_ID="$SRC_AWS_ACCESS_KEY_ID" \
AWS_SECRET_ACCESS_KEY="$SRC_AWS_SECRET_ACCESS_KEY" \
  aws s3 ls "s3://${SRC_BUCKET}/" --endpoint-url "$SRC_ENDPOINT" --region "$SRC_REGION" | head

echo "==> Sync → s3://${DST_BUCKET} via ${DST_ENDPOINT}"
AWS_ACCESS_KEY_ID="$SRC_AWS_ACCESS_KEY_ID" \
AWS_SECRET_ACCESS_KEY="$SRC_AWS_SECRET_ACCESS_KEY" \
  aws s3 sync "s3://${SRC_BUCKET}" "/tmp/marrow-photos-sync" \
    --endpoint-url "$SRC_ENDPOINT" --region "$SRC_REGION"

AWS_ACCESS_KEY_ID="$DST_AWS_ACCESS_KEY_ID" \
AWS_SECRET_ACCESS_KEY="$DST_AWS_SECRET_ACCESS_KEY" \
  aws s3 sync "/tmp/marrow-photos-sync" "s3://${DST_BUCKET}" \
    --endpoint-url "$DST_ENDPOINT" --region "$DST_REGION"

echo "==> Spot-check destination"
AWS_ACCESS_KEY_ID="$DST_AWS_ACCESS_KEY_ID" \
AWS_SECRET_ACCESS_KEY="$DST_AWS_SECRET_ACCESS_KEY" \
  aws s3 ls "s3://${DST_BUCKET}/" --endpoint-url "$DST_ENDPOINT" --region "$DST_REGION" | head

echo "Done. Wire BUCKET_NAME / AWS_* on marrow-api to Railway Bucket refs."
