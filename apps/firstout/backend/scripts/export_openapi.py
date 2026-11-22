"""Export the API's OpenAPI document for frontend codegen.

Imports ``app.main`` without a database or Clerk: the settings defaults are
enough to build the schema, so no environment is set here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

from pydantic import BaseModel  # noqa: E402

# A response always carries every field, defaults included, so its schema marks
# them all required; request schemas keep defaulted fields optional. Models that
# differ between the two directions are emitted as `X-Input` / `X-Output`.
# Set on the base before `app` defines any model; it changes the JSON schema only.
# ponytail: routes with response_model_exclude_unset (held-sale resume, ops
# commerce products) omit unset fields, so their generated types overstate them.
BaseModel.model_config["json_schema_serialization_defaults_required"] = True

from app.main import app  # noqa: E402

OUT = _BACKEND_ROOT / "openapi.json"
FRONTEND_OUT = _BACKEND_ROOT.parent / "frontend" / "openapi.json"


def main() -> None:
    payload = json.dumps(app.openapi(), indent=2) + "\n"
    OUT.write_text(payload, encoding="utf-8")
    FRONTEND_OUT.write_text(payload, encoding="utf-8")
    print(f"Wrote {OUT} and {FRONTEND_OUT}")


if __name__ == "__main__":
    main()
