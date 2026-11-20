#!/usr/bin/env bash
# One-time switch of Marrow (Railway) to Releases by cd.yml. Order of use: 5 of 6.
# Run before 2026-12-01: Railway stops reading railway.toml that day.
#   .github/deploy/switch/marrow.sh
APP=marrow
TITLE="Marrow: switch Railway to image Releases (before 2026-12-01)"
RAILWAY_PROJECT=Marrow
FROM_REPO=1
DEADLINE=2026-12-01
# Only the deleted smoke and Fly workflows read these.
OLD_SECRETS=(SMOKE_EMAIL SMOKE_PASSWORD FLY_API_TOKEN)

switch_notes() {
  say "marrow-api, marrow-worker and marrow-mcp all run the marrow-backend image, each with its own start command."
  note "marrow-api goes first because it runs the migrations as its pre-deploy command."
  note "marrow-worker and marrow-mcp get no health check path (MCP has no plain GET endpoint); the Release clears any set."
}

source "$(dirname "$0")/_switch.sh"
switch_railway
