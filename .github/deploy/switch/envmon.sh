#!/usr/bin/env bash
# One-time switch of the environment monitor (Pi) to Releases by cd.yml. Order of use: 1 of 4.
#   .github/deploy/switch/envmon.sh
APP=envmon
TITLE="Environment monitor: switch the Pi to image Releases"
SERVICES=(
  "environment-monitor-backend|environment-monitor-backend|x408g80c0cggs4okgok4cc0o|5001|5001:5001"
  "environment-monitor-frontend|environment-monitor-frontend|zk8s00gk0g88cc08gkswkc44|5000|5000:5000"
)
DATA_VOLUME=environment-monitor_sensor_data
BACKUP_DIR=sensor-backups
OLD_SECRETS=(COOLIFY_WEBHOOK_ENVMON_BACKEND COOLIFY_WEBHOOK_ENVMON_FRONTEND)

backup_notes() {
  note "Same volume and folder as the nightly backup; this is one extra copy taken right before the switch."
}

# The frontend's nginx proxies /api/ to http://em-backend:5001 and re-resolves that name every 10 s.
# On 2026-11-20 the old backend got the name from Coolify's Network Aliases field; both old
# applications sit on Coolify's only destination network, "coolify". The new ones must match.
service_notes() {
  if [[ "$1" == environment-monitor-frontend ]]; then
    note "Nothing extra here: it reaches the backend as em-backend over the coolify network, which every application on this server joins."
    return 0
  fi
  warn "This one needs three extra settings, all copied from the old application:"
  step "General → Network Aliases: em-backend   (the frontend's nginx calls the backend by this name)"
  step "General → Custom Docker Options, character for character (sensor access):"
  cmd "--privileged --device=/dev/i2c-1:/dev/i2c-1 -v /dev:/dev -v environment-monitor_sensor_data:/app/data"
  step "Persistent Storage → Add → Directory Mount (this is what really mounts the database; Coolify ignores the -v above):"
  cmd "Source Path: /mnt/nvme/var/lib/docker/volumes/environment-monitor_sensor_data/_data   Destination Path: /app/data"
  note "Without these the frontend shows no data, the sensor is missing, and the backend starts on an empty database."
  note "The old and new applications share a name. That is fine: a Release only looks at Docker Image applications."
}

source "$(dirname "$0")/_switch.sh"
switch_pi
