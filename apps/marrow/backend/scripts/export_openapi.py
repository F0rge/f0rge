"""Export OpenAPI schema JSON for frontend codegen."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Backend package root (apps/marrow/backend).
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

# Avoid loading a real DB engine at import time during export.
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://health:health@localhost:5432/health")
os.environ.setdefault("JWT_SECRET", "openapi-export-only-secret-32b")

from app.main import app  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "openapi.json"
FRONTEND_OUT = Path(__file__).resolve().parents[1].parent / "frontend" / "openapi.json"


def main() -> None:
    schema = app.openapi()
    payload = json.dumps(schema, indent=2) + "\n"
    OUT.write_text(payload, encoding="utf-8")
    FRONTEND_OUT.write_text(payload, encoding="utf-8")
    print(f"Wrote {OUT} and {FRONTEND_OUT}")


if __name__ == "__main__":
    main()
    sys.exit(0)
