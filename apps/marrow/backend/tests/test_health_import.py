"""Tests for health import payload validation and parsing."""

from __future__ import annotations

from app.schemas.health_metrics import HealthAutoExportPayload
from app.services.health_import import parse_health_auto_export


def test_health_auto_export_payload_accepts_metric_samples() -> None:
    payload = HealthAutoExportPayload.model_validate(
        {
            "data": {
                "metrics": [
                    {
                        "name": "Step Count",
                        "units": "count",
                        "data": [{"qty": 4200, "date": "2026-05-01 12:00:00 +0000"}],
                    }
                ]
            }
        }
    )
    parsed = parse_health_auto_export(payload.model_dump())
    assert "2026-05-01" in parsed
    assert parsed["2026-05-01"].steps == 4200


def test_health_auto_export_payload_rejects_non_object_body() -> None:
    try:
        HealthAutoExportPayload.model_validate(["not", "a", "dict"])
        assert False, "expected validation error"
    except Exception:
        pass
