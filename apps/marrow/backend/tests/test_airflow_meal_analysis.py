"""Unit tests for Airflow internal meal-analysis seams."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from f0rge_core.exceptions import UnauthorizedError, ValidationError

from app.schemas.airflow_meal import MealAnalysisCompleteRequest, VisionIngredientIn
from app.services.airflow_meal_analysis import (
    AirflowMealAnalysisService,
    validate_airflow_service_token,
)


def test_validate_airflow_service_token_ok(monkeypatch):
    monkeypatch.setattr(
        "app.services.airflow_meal_analysis.settings.airflow_service_token",
        "secret-token",
    )
    validate_airflow_service_token("Bearer secret-token")


def test_validate_airflow_service_token_rejects(monkeypatch):
    monkeypatch.setattr(
        "app.services.airflow_meal_analysis.settings.airflow_service_token",
        "secret-token",
    )
    with pytest.raises(UnauthorizedError):
        validate_airflow_service_token("Bearer wrong")
    with pytest.raises(UnauthorizedError):
        validate_airflow_service_token(None)


def test_vision_result_parity_with_orchestrator_fixture():
    """Same shape today's parse_vision_response accepts."""
    from app.services.vision_prompt import VisionResult

    fixture = {
        "dish_name": "avocado toast",
        "cuisine": "american",
        "confidence": 0.91,
        "ingredients": [
            {"name": "avocado", "visible": True, "confidence": 0.95},
            {"name": "bread", "visible": True, "confidence": 0.88},
            {"name": "salt", "visible": False, "confidence": 0.4},
        ],
    }
    result = VisionResult.model_validate(fixture)
    assert result.dish_name == "avocado toast"
    assert len(result.ingredients) == 3


@pytest.mark.asyncio
async def test_resolve_rejects_invalid_user_id():
    service = AirflowMealAnalysisService(MagicMock())
    with pytest.raises(ValidationError):
        await service.resolve(1, "not-a-uuid")


@pytest.mark.asyncio
async def test_complete_sets_confirmed(monkeypatch):
    user_id = uuid.uuid4()
    analysis = MagicMock()
    analysis.id = 42
    analysis.photo_id = 7
    analysis.user_id = user_id

    photo = MagicMock()
    photo.id = 7
    photo.entry = MagicMock(date="2026-08-15")
    photo.source_photo_id = None

    db = MagicMock()
    service = AirflowMealAnalysisService(db)
    service.analysis_crud = MagicMock()
    service.analysis_crud.get_by_id = AsyncMock(return_value=analysis)
    service.analysis_crud.save = AsyncMock()
    service.ingredient_crud = MagicMock()
    service.ingredient_crud.delete_for_analysis = AsyncMock()
    service.ingredient_crud.add = MagicMock()
    service.photo_crud = MagicMock()
    service.photo_crud.get_by_id = AsyncMock(return_value=photo)

    monkeypatch.setattr(
        "app.services.airflow_meal_analysis.apply_session_user_id",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.airflow_meal_analysis.invalidate_user_insights_cache",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.airflow_meal_analysis.IngredientLookupService",
        lambda _db: MagicMock(lookup=AsyncMock(return_value=None)),
    )

    with patch("app.services.tag_delivery.TagDeliveryService") as tag_cls:
        tag_cls.return_value.deliver_for_source = AsyncMock()
        body = MealAnalysisCompleteRequest(
            user_id=str(user_id),
            dish_name="salad",
            cuisine="mediterranean",
            confidence=0.8,
            ingredients=[VisionIngredientIn(name="lettuce", visible=True, confidence=0.9)],
        )
        out = await service.complete(42, body)

    assert out["status"] == "confirmed"
    assert analysis.status == "confirmed"
    service.ingredient_crud.add.assert_called_once()
