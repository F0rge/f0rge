#!/usr/bin/env bash
# Repoint dk tag printer Coolify apps to the f0rge monorepo.
# Requires: COOLIFY_URL, COOLIFY_TOKEN env vars (Coolify API bearer).
# Run once after merging dk into f0rge on main.
set -euo pipefail

COOLIFY_URL="${COOLIFY_URL:?set COOLIFY_URL e.g. https://coolify.taxpilot.lu}"
COOLIFY_TOKEN="${COOLIFY_TOKEN:?set COOLIFY_TOKEN}"

API="${COOLIFY_URL%/}/api/v1"

patch_app() {
  local uuid="$1"
  local dockerfile="$2"
  local watch_paths="$3"
  echo "Patching $uuid …"
  curl -sf -X PATCH "${API}/applications/${uuid}" \
    -H "Authorization: Bearer ${COOLIFY_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$(jq -nc \
      --arg branch "main" \
      --arg dockerfile "/${dockerfile#/}" \
      --arg watch "$watch_paths" \
      --arg gitrepo "git@github.com:F0rge/f0rge.git" \
      '{
        git_repository: $gitrepo,
        git_branch: $branch,
        base_directory: "/",
        dockerfile_location: $dockerfile,
        watch_paths: $watch,
        is_auto_deploy_enabled: false
      }')"
  echo "OK: $uuid"
}

# Backend
patch_app "pskswsc8c0044ggo40go4og0" \
  "apps/dk/tag-printer/backend/Dockerfile" \
  "apps/dk/tag-printer/backend/**"

# Frontend
patch_app "f080ossg88ows8k8csw40c4s" \
  "apps/dk/tag-printer/frontend/Dockerfile" \
  "apps/dk/tag-printer/frontend/**"

echo "Done. Verify Coolify env vars:"
echo "  backend CORS_ORIGINS=https://tags.leo-figueiredo.com"
echo "  frontend NEXT_PUBLIC_API_URL=https://tags-api.leo-figueiredo.com (build-time)"
echo "Set GitHub secrets COOLIFY_BASE_URL, COOLIFY_WEBHOOK_DK_BACKEND, COOLIFY_WEBHOOK_DK_FRONTEND"
