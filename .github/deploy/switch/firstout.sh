#!/usr/bin/env bash
# One-time switch of Firstout (Railway) to Releases by cd.yml. Order of use: 5 of 5.
# Firstout's services already run images; this moves it to the shared path and its own environment.
#   .github/deploy/switch/firstout.sh
APP=firstout
TITLE="Firstout: switch Railway to the shared Releases"
RAILWAY_PROJECT=Firstout
# Only the deleted Firstout workflows read these; the image build arguments now live in the deploy block.
OLD_VARIABLES=(FIRSTOUT_API_URL FIRSTOUT_BOOTSTRAP_BACKEND_IMAGE FIRSTOUT_CLERK_PUBLISHABLE_KEY FIRSTOUT_TENANT_SUBDOMAINS_ENABLED)

retire() {
  say "The old path kept its token in the GitHub environment firstout-production."
  step "Railway → project Firstout → Settings → Tokens: delete the old token."
  if confirm "Delete GitHub environment firstout-production and its secret now? This cannot be undone."; then
    gh api -X DELETE "repos/$REPO/environments/firstout-production" && done_ "deleted environment firstout-production" ||
      warn "could not delete environment firstout-production"
  else
    SKIPPED+=("delete GitHub environment firstout-production")
  fi
}

source "$(dirname "$0")/_switch.sh"
switch_railway
