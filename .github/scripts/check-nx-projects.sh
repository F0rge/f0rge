#!/usr/bin/env bash
# Fail if any apps/** or libs/** tree with package.json or pyproject.toml
# lacks a sibling project.json with a platform: tag.
# Exception: marrow-ios (Swift; no platform:py/ts — not on Linux CI).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

exceptions=(
  "apps/marrow/ios"
)

is_exception() {
  local dir="$1"
  local ex
  for ex in "${exceptions[@]}"; do
    if [[ "$dir" == "$ex" ]]; then
      return 0
    fi
  done
  return 1
}

fail=0
# Directories that declare a Node or Python project root.
while IFS= read -r -d '' manifest; do
  dir="$(dirname "$manifest")"
  # Skip nested package.json under node_modules / .venv / dist / .next
  case "$dir" in
    */node_modules|*/node_modules/*|*/.venv|*/.venv/*|*/dist|*/dist/*|*/.next|*/.next/*)
      continue
      ;;
  esac
  # Only apps/ and libs/
  case "$dir" in
    apps/*|libs/*) ;;
    *) continue ;;
  esac

  if is_exception "$dir"; then
    # Still require project.json for known exceptions
    if [[ ! -f "$dir/project.json" ]]; then
      echo "ERROR: $dir is an Nx exception but missing project.json"
      fail=1
    fi
    continue
  fi

  if [[ ! -f "$dir/project.json" ]]; then
    echo "ERROR: $dir has $(basename "$manifest") but no project.json"
    fail=1
    continue
  fi

  if ! grep -qE '"platform:(py|ts)"' "$dir/project.json"; then
    echo "ERROR: $dir/project.json missing platform:py or platform:ts tag (CI would ignore it)"
    fail=1
  fi
done < <(find apps libs \( -name package.json -o -name pyproject.toml \) -print0 2>/dev/null)

# Root package.json is the workspace root — not an Nx project.
if [[ $fail -ne 0 ]]; then
  echo "Nx project registration check failed. See .cursor/rules/nx.mdc"
  exit 1
fi
echo "Nx project registration check OK"
