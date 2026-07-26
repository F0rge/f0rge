"""Tests for Airflow meal-analysis trigger + internal stage API."""

from __future__ import annotations

import datetime
import io
import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import BackgroundTasks, UploadFile
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.services.vision_prompt import VisionIngredient, VisionResult
from f0rge_core.exceptions import UnauthorizedError
from f0rge_db.tenant import apply_session_user_id


async def _seed_photo(db: AsyncSession) -> Photo:
    entry = Entry(
        date=datetime.date.today(),
        overall=2,
        bloating=0,
        joint_pain=0,
        neuro=0,
        sleep_quality=2,
        stress=1,
        diet_risk="normal",
        supplements="",
        sick=False,
        hot_shower=False,
        symptoms_json={},
    )
    db.add(entry)
    await db.flush()
    photo = Photo(
        entry_id=entry.id,
        filename="meal-airflow.jpg",
        original_filename="meal-airflow.jpg",
        created_at=datetime.datetime.utcnow(),
    )
    db.add(photo)
    await db.flush()
    await db.refresh(photo)
    return photo


def test_require_internal_token() -> None:
    from app.services.meal_analysis_stage_orchestrator import require_internal_token

    with pytest.raises(UnauthorizedError):
        require_internal_token(None, "")
    with pytest.raises(UnauthorizedError):
        require_internal_token("wrong", "secret")
    require_internal_token("secret", "secret")


async def test_gate_endpoint_requires_token(
    async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "meal_analysis_internal_token", "stage-secret")
    vision = {
        "dish_name": "rice",
        "confidence": 0.9,
        "ingredients": [{"name": "rice", "visible": True, "confidence": 0.9}],
    }
    denied = await async_client.post(
        "/api/v1/internal/meal-analysis/gate",
        json={"vision": vision},
    )
    assert denied.status_code == 401

    ok = await async_client.post(
        "/api/v1/internal/meal-analysis/gate",
        headers={"X-Meal-Analysis-Token": "stage-secret"},
        json={"vision": vision},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "confirmed"


async def test_gate_endpoint_needs_review(
    async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "meal_analysis_internal_token", "stage-secret")
    vision = {
        "dish_name": "mystery",
        "confidence": 0.2,
        "ingredients": [{"name": "x", "visible": True, "confidence": 0.2}],
    }
    resp = await async_client.post(
        "/api/v1/internal/meal-analysis/gate",
        headers={"X-Meal-Analysis-Token": "stage-secret"},
        json={"vision": vision},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "needs_review"


async def test_airflow_client_triggers_dag_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.airflow_client import AirflowClient

    monkeypatch.setattr(settings, "airflow_api_url", "http://airflow.test")
    monkeypatch.setattr(settings, "airflow_username", "airflow")
    monkeypatch.setattr(settings, "airflow_password", "airflow")
    monkeypatch.setattr(settings, "meal_analysis_dag_id", "meal_analysis")

    class _FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
            self.status_code = status_code
            self._payload = payload
            self.text = str(payload)

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(self.text)

        def json(self) -> dict[str, Any]:
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def post(self, path: str, **kwargs: Any) -> _FakeResponse:
            assert path == "/auth/token"
            return _FakeResponse(200, {"access_token": "jwt-token"})

        async def request(self, method: str, path: str, **kwargs: Any) -> _FakeResponse:
            assert method == "POST"
            assert path == "/api/v2/dags/meal_analysis/dagRuns"
            assert kwargs["headers"]["Authorization"] == "Bearer jwt-token"
            body = kwargs["json"]
            assert body["conf"]["photo_id"] == 42
            return _FakeResponse(
                200,
                {"dag_run_id": "manual__1", "state": "queued", "logical_date": None},
            )

    with patch("app.services.airflow_client.httpx.AsyncClient", _FakeAsyncClient):
        result = await AirflowClient().trigger_meal_analysis(
            photo_id=42,
            user_id=uuid.UUID(settings.default_storage_user_id),
        )
    assert result["dag_run_id"] == "manual__1"
    assert result["state"] == "queued"


async def test_schedule_triggers_airflow(
    async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.food_analysis import FoodAnalysisService
    from app.services.food_analysis_orchestrator import FoodAnalysisOrchestrator

    photo = await _seed_photo(async_db)
    monkeypatch.setattr(settings, "airflow_api_url", "http://airflow.test")
    monkeypatch.setattr(settings, "meal_analysis_inline", False)

    trigger = AsyncMock(return_value={"dag_run_id": "r1", "state": "queued"})

    class _StubClient:
        configured = True

        async def trigger_meal_analysis(self, **kwargs: Any) -> dict[str, Any]:
            return await trigger(**kwargs)

    monkeypatch.setattr("app.services.airflow_client.AirflowClient", _StubClient)
    monkeypatch.setattr("app.services.food_analysis.AirflowClient", _StubClient)

    await FoodAnalysisService(async_db, FoodAnalysisOrchestrator()).schedule_for_uploaded_photo(
        user_id=photo.user_id,
        meal_id=photo.meal_id,
        photo_id=photo.id,
    )

    analysis = (
        await async_db.execute(select(PhotoAnalysis).where(PhotoAnalysis.photo_id == photo.id))
    ).scalar_one()
    assert analysis.status == "pending"
    trigger.assert_awaited_once()
    assert trigger.await_args.kwargs["photo_id"] == photo.id


async def test_upload_triggers_airflow_and_creates_pending(
    async_db: AsyncSession, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.food_analysis_orchestrator import FoodAnalysisOrchestrator
    from app.services.meal_tags import MealTagService
    from app.services.photos import PhotoService

    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))
    monkeypatch.setattr(settings, "food_analysis_enabled", True)
    monkeypatch.setattr(settings, "meal_analysis_inline", False)
    monkeypatch.setattr(settings, "airflow_api_url", "http://airflow.test")
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-test")

    async def _creds(_db: Any) -> tuple[str, str]:
        return "sk-test", "test-model"

    monkeypatch.setattr("app.services.llm.factory.resolve_llm_credentials", _creds)

    trigger = AsyncMock(return_value={"dag_run_id": "r2", "state": "queued"})

    class _StubClient:
        configured = True

        async def trigger_meal_analysis(self, **kwargs: Any) -> dict[str, Any]:
            return await trigger(**kwargs)

    monkeypatch.setattr("app.services.airflow_client.AirflowClient", _StubClient)
    monkeypatch.setattr("app.services.food_analysis.AirflowClient", _StubClient)

    day = datetime.date(2026, 7, 26)
    entry = Entry(
        date=day,
        overall=2,
        bloating=0,
        joint_pain=0,
        neuro=0,
        sleep_quality=2,
        stress=1,
        diet_risk="normal",
        supplements="",
        sick=False,
        hot_shower=False,
        symptoms_json={},
    )
    async_db.add(entry)
    await async_db.commit()
    await async_db.refresh(entry)

    img = Image.new("RGB", (8, 8), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    service = PhotoService(async_db, FoodAnalysisOrchestrator(), MealTagService(async_db))
    photo = await service.upload(
        entry_date=day,
        file=UploadFile(filename="x.png", file=buf),
        label=None,
        meal_time=None,
        background_tasks=BackgroundTasks(),
    )

    analysis = (
        await async_db.execute(select(PhotoAnalysis).where(PhotoAnalysis.photo_id == photo.id))
    ).scalar_one()
    assert analysis.status == "pending"
    trigger.assert_awaited()


async def test_legacy_background_path_skips_fresh_analyzing(
    async_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BackgroundTasks path still skips a fresh concurrent analyzing duplicate."""
    import app.config as cfg_mod
    from app.services import food_analysis_orchestrator as fa

    real_maker = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr(fa, "async_session_maker", real_maker)
    monkeypatch.setattr(cfg_mod.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(cfg_mod.settings, "food_analysis_enabled", True)
    monkeypatch.setattr(cfg_mod.settings, "airflow_api_url", "")
    monkeypatch.setattr(cfg_mod.settings, "meal_analysis_inline", False)

    user_id = uuid.UUID(settings.default_storage_user_id)
    async with real_maker() as setup:
        await apply_session_user_id(setup, user_id)
        photo = await _seed_photo(setup)
        setup.add(
            PhotoAnalysis(
                user_id=photo.user_id,
                meal_id=photo.meal_id,
                photo_id=photo.id,
                status="analyzing",
                model_id="test-model",
                updated_at=datetime.datetime.utcnow(),
            )
        )
        await setup.commit()
        photo_id = photo.id
        meal_id = photo.meal_id
        entry_id = photo.entry_id

    try:
        status = await fa.run_staged_pipeline(photo_id, user_id)
        assert status is None

        async with real_maker() as verify:
            await apply_session_user_id(verify, user_id)
            analysis = (
                await verify.execute(
                    select(PhotoAnalysis).where(PhotoAnalysis.photo_id == photo_id)
                )
            ).scalar_one()
        assert analysis.status == "analyzing"
    finally:
        async with real_maker() as cleanup:
            await apply_session_user_id(cleanup, user_id)
            await cleanup.execute(
                PhotoAnalysis.__table__.delete().where(PhotoAnalysis.meal_id == meal_id)
            )
            await cleanup.execute(Photo.__table__.delete().where(Photo.id == photo_id))
            await cleanup.execute(text("DELETE FROM meals WHERE id = :mid"), {"mid": meal_id})
            await cleanup.execute(Entry.__table__.delete().where(Entry.id == entry_id))
            await cleanup.commit()


async def test_inline_path_reclaims_fresh_analyzing(
    async_engine, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Crash mid-LLM leaves analyzing; inline/Airflow reclaim must rerun."""
    import os

    import app.config as cfg_mod
    from app.services import food_analysis_orchestrator as fa

    real_maker = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    monkeypatch.setattr(fa, "async_session_maker", real_maker)

    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(cfg_mod.settings, "photo_dir", str(photo_dir))
    monkeypatch.setattr(cfg_mod.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(cfg_mod.settings, "food_analysis_enabled", True)
    monkeypatch.setattr(cfg_mod.settings, "meal_analysis_inline", True)
    monkeypatch.setattr(cfg_mod.settings, "airflow_api_url", "")

    user_id = uuid.UUID(settings.default_storage_user_id)
    async with real_maker() as setup:
        await apply_session_user_id(setup, user_id)
        photo = await _seed_photo(setup)
        setup.add(
            PhotoAnalysis(
                user_id=photo.user_id,
                meal_id=photo.meal_id,
                photo_id=photo.id,
                status="analyzing",
                model_id="test-model",
                updated_at=datetime.datetime.utcnow(),
            )
        )
        await setup.commit()
        photo_id = photo.id
        meal_id = photo.meal_id
        entry_id = photo.entry_id
        filename = photo.filename

    with open(os.path.join(str(photo_dir), filename), "wb") as f:
        f.write(b"\xff\xd8\xff\xd9")

    class _FakeClient:
        def __init__(self, api_key: str, default_model: str) -> None:
            pass

        async def complete_with_image(self, *args: Any, **kwargs: Any) -> str:
            return (
                '{"dish_name":"Rice","confidence":0.9,'
                '"ingredients":[{"name":"rice","visible":true,"confidence":0.9}]}'
            )

    monkeypatch.setattr("app.services.llm.openrouter.OpenRouterClient", _FakeClient)

    try:
        status = await fa.run_staged_pipeline(photo_id, user_id)
        assert status == "confirmed"

        async with real_maker() as verify:
            await apply_session_user_id(verify, user_id)
            analysis = (
                await verify.execute(
                    select(PhotoAnalysis).where(PhotoAnalysis.photo_id == photo_id)
                )
            ).scalar_one()
        assert analysis.status == "confirmed"
    finally:
        async with real_maker() as cleanup:
            await apply_session_user_id(cleanup, user_id)
            await cleanup.execute(
                PhotoAnalysis.__table__.delete().where(PhotoAnalysis.meal_id == meal_id)
            )
            await cleanup.execute(Photo.__table__.delete().where(Photo.id == photo_id))
            await cleanup.execute(text("DELETE FROM meals WHERE id = :mid"), {"mid": meal_id})
            await cleanup.execute(Entry.__table__.delete().where(Entry.id == entry_id))
            await cleanup.commit()


async def test_fail_stage_marks_analysis(async_engine) -> None:
    from app.services.meal_analysis_stage_orchestrator import MealAnalysisStageOrchestrator

    real_maker = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    user_id = uuid.UUID(settings.default_storage_user_id)
    async with real_maker() as setup:
        await apply_session_user_id(setup, user_id)
        photo = await _seed_photo(setup)
        analysis = PhotoAnalysis(
            user_id=photo.user_id,
            meal_id=photo.meal_id,
            photo_id=photo.id,
            status="analyzing",
            model_id="test-model",
        )
        setup.add(analysis)
        await setup.commit()
        analysis_id = analysis.id
        photo_id = photo.id
        meal_id = photo.meal_id
        entry_id = photo.entry_id

    try:
        async with real_maker() as db:
            from app.schemas.meal_analysis_stages import FailRequest

            await MealAnalysisStageOrchestrator(db).fail(
                FailRequest(
                    user_id=user_id,
                    analysis_id=analysis_id,
                    error_message="boom",
                )
            )

        async with real_maker() as verify:
            await apply_session_user_id(verify, user_id)
            row = (
                await verify.execute(select(PhotoAnalysis).where(PhotoAnalysis.id == analysis_id))
            ).scalar_one()
        assert row.status == "failed"
        assert row.error_message == "boom"
    finally:
        async with real_maker() as cleanup:
            await apply_session_user_id(cleanup, user_id)
            await cleanup.execute(
                PhotoAnalysis.__table__.delete().where(PhotoAnalysis.meal_id == meal_id)
            )
            await cleanup.execute(Photo.__table__.delete().where(Photo.id == photo_id))
            await cleanup.execute(text("DELETE FROM meals WHERE id = :mid"), {"mid": meal_id})
            await cleanup.execute(Entry.__table__.delete().where(Entry.id == entry_id))
            await cleanup.commit()


def test_enrich_payload_roundtrip() -> None:
    vision = VisionResult(
        dish_name="salad",
        confidence=0.8,
        ingredients=[VisionIngredient(name="lettuce", visible=True, confidence=0.8)],
    )
    assert vision.dish_name == "salad"
