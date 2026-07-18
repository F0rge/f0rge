#!/usr/bin/env bash
set -euo pipefail
# @nxlv/python flips to workspace mode when a root uv.lock exists — never create one.
test ! -f uv.lock
