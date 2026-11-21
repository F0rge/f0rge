#!/usr/bin/env bash
# One-time switch of the DasKasas storefront (Railway) to Releases by cd.yml. Order of use: 3 of 5.
# Run before 2026-12-01: Railway stops reading railway.toml that day.
#   .github/deploy/switch/daskasas.sh
APP=daskasas
TITLE="DasKasas storefront: switch Railway to image Releases (before 2026-12-01)"
RAILWAY_PROJECT=DasKasas
FROM_REPO=1
DEADLINE=2026-12-01

switch_notes() {
  warn "storefront builds with Railpack today and has no health check."
  say "After the Release it runs the image built from the repository Dockerfile, with the health check from its deploy block."
  step "Open the storefront right after the Release and click through it; this is the service most likely to differ."
  note "The storefront image gets its NEXT_PUBLIC_* values when CI builds it, from daskasas-web's deploy block."
  note "So the NEXT_PUBLIC_* variables on the Railway storefront service do nothing after the switch."
  note "Leave them; deleting them later is optional cleanup. Its other (runtime) variables still matter."
}

source "$(dirname "$0")/_switch.sh"
switch_railway
