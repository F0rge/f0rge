#!/usr/bin/env bash
# One-time switch of the dk tag printer (Pi) to Releases by cd.yml. Order of use: 1 of 5.
#   .github/deploy/switch/dk.sh
APP=dk
TITLE="dk tag printer: switch the Pi to image Releases"
SERVICES=(
  "dk-tag-printer-backend|daskasas-backend|pskswsc8c0044ggo40go4og0|8000|8002:8000"
  "dk-tag-printer-frontend|daskasas-frontend|f080ossg88ows8k8csw40c4s|3000|3002:3000"
)
OLD_SECRETS=(COOLIFY_WEBHOOK_DASKASAS_BACKEND COOLIFY_WEBHOOK_DASKASAS_FRONTEND COOLIFY_WEBHOOK_DK_BACKEND COOLIFY_WEBHOOK_DK_FRONTEND COOLIFY_BASE_URL COOLIFY_TOKEN)

retire() {
  step "Coolify → Keys & Tokens → API Tokens: revoke the old GitHub token once dk and envmon both release through cd.yml."
  note "Only delete COOLIFY_BASE_URL and COOLIFY_TOKEN below if envmon is already switched."
}

source "$(dirname "$0")/_switch.sh"
switch_pi
