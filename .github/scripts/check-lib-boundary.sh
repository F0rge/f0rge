#!/usr/bin/env bash
set -euo pipefail
# libs/backend must never import from apps/ — shared libs stay app-agnostic.
! grep -rn "from apps\.\|import apps\." libs/backend/ --include='*.py'
