#!/bin/sh
set -eu
exec /usr/bin/python3 /opt/f0rge/apps/buycycle/ops/backup.py --config /etc/buycycle/backup.json
