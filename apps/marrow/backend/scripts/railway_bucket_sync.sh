#!/usr/bin/env bash
# Sync photos from a source S3-compatible bucket to Railway Bucket.
#
# Requires AWS CLI v2 and separately scoped source/destination bucket credentials.
#
# Usage:
#   export SRC_AWS_ACCESS_KEY_ID=... SRC_AWS_SECRET_ACCESS_KEY=... SRC_BUCKET=f0rge-marrow-dev-photos
#   export SRC_ENDPOINT=...          # Exact S3 endpoint for the source bucket
#   export DST_AWS_ACCESS_KEY_ID=... DST_AWS_SECRET_ACCESS_KEY=... DST_BUCKET=...
#   ./apps/marrow/backend/scripts/railway_bucket_sync.sh
set -euo pipefail

: "${SRC_AWS_ACCESS_KEY_ID:?}"
: "${SRC_AWS_SECRET_ACCESS_KEY:?}"
: "${SRC_BUCKET:?}"
: "${SRC_ENDPOINT:?Set SRC_ENDPOINT to the source S3 endpoint}"
: "${DST_AWS_ACCESS_KEY_ID:?}"
: "${DST_AWS_SECRET_ACCESS_KEY:?}"
: "${DST_BUCKET:?}"

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
