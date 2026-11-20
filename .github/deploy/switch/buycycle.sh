#!/usr/bin/env bash
# One-time switch of Buycycle (Pi) to Releases by cd.yml. Order of use: 3 of 6.
# This releases what runs today (apps/buycycle/Dockerfile), not the Rust rewrite.
#   .github/deploy/switch/buycycle.sh
APP=buycycle
TITLE="Buycycle: switch the Pi to image Releases"
SERVICES=("buycycle|buycycle|xi0qwpbyl2d8gf8u3xl13jkv|8095,8096|8095:8095,8096:8096")
DATA_VOLUME=xi0qwpbyl2d8gf8u3xl13jkv-buycycle-data
BACKUP_DIR=buycycle-backups
# Buycycle is the last Pi App, so the repository-wide Coolify secrets of the old path go too.
OLD_SECRETS=(COOLIFY_WEBHOOK_BUYCYCLE COOLIFY_BASE_URL COOLIFY_TOKEN)
OLD_VARIABLES=(BUYCYCLE_RELEASE_REQUESTER_APP_ID BUYCYCLE_RELEASE_REQUESTER_APP_SLUG BUYCYCLE_RELEASE_REQUESTER_BOT_ID BUYCYCLE_RELEASE_REQUEST_PR_NUMBER)

backup_notes() {
  note "Do the switch outside 06:00 to 08:00 local time, when the daily scrape writes to this volume."
}

service_notes() {
  step "Persistent Storage → Add Volume Mount: Name buycycle-data, Destination Path /data,"
  step "  Source Path: the folder of the existing volume. On the Pi:"
  cmd "docker volume inspect -f '{{.Mountpoint}}' $DATA_VOLUME"
  step "Scheduled Tasks: add the old application's task again (Name buycycle-tracker, same Command and Frequency)."
  note "The old and new applications share a name. That is fine: a Release only looks at Docker Image applications."
}

retire() {
  warn "The data still lives in the old application's volume. Deleting that volume deletes Buycycle's database."
  step "Coolify → Keys & Tokens → API Tokens: revoke the old GitHub token once dk, envmon and buycycle all release through cd.yml."
  note "Only delete COOLIFY_BASE_URL and COOLIFY_TOKEN below if dk and envmon are already switched."
}

source "$(dirname "$0")/_switch.sh"
switch_pi
