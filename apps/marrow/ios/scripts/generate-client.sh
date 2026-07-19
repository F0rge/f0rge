#!/usr/bin/env bash
# Regenerate the checked-in OpenAPI Swift client from the backend contract.
# Usage: ./scripts/generate-client.sh [path/to/openapi.json]
set -euo pipefail

cd "$(dirname "$0")/.."
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"

SPEC="${1:-../backend/openapi.json}"
TMP_SPEC="$(mktemp -t marrow-openapi-XXXXXX).json"
trap 'rm -f "$TMP_SPEC"' EXIT

# swift-openapi-generator 1.13.0 does not understand Pydantic's nullable pattern
# anyOf: [T, {type: null}] and silently drops such properties. Strip the null
# branch — the properties are already optional via the schema's `required` list.
python3 - "$SPEC" "$TMP_SPEC" <<'PY'
import json
import sys

NULL_SCHEMA = {"type": "null"}


def strip_nullable_anyof(node):
    if isinstance(node, dict):
        any_of = node.get("anyOf")
        if isinstance(any_of, list) and NULL_SCHEMA in any_of:
            rest = [branch for branch in any_of if branch != NULL_SCHEMA]
            if len(rest) == 1:
                del node["anyOf"]
                if "$ref" in rest[0]:
                    # $ref with siblings (title etc.) trips strict parsers; keep the ref only.
                    node.clear()
                merged = {**node, **rest[0]}
                node.clear()
                node.update(merged)
            else:
                node["anyOf"] = rest
        for value in node.values():
            strip_nullable_anyof(value)
    elif isinstance(node, list):
        for value in node:
            strip_nullable_anyof(value)


with open(sys.argv[1]) as f:
    spec = json.load(f)
strip_nullable_anyof(spec)
with open(sys.argv[2], "w") as f:
    json.dump(spec, f)
PY

swift run --package-path codegen swift-openapi-generator generate \
  "$TMP_SPEC" \
  --config codegen/openapi-generator-config.yaml \
  --output-directory Marrow/Generated
