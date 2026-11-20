#!/usr/bin/env bash
set -euo pipefail
# libs must never import from apps/ — shared libs stay app-agnostic.
if grep -rn "from apps\.\|import apps\." libs/backend/ --include='*.py'; then exit 1; fi
if grep -rn "from ['\"].*apps/" libs/ --include='*.ts' --include='*.tsx' --exclude-dir=node_modules; then exit 1; fi
