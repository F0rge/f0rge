#!/bin/sh
set -eu
exec /usr/bin/python3 /opt/f0rge/apps/buycycle/ops/collect.py --config /etc/buycycle/collector.json
