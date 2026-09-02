"""Nia scheduled tasks — CRUD, ticker skip, HITL, cap, advisory lock."""

from __future__ import annotations

import datetime
import uuid

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from pydantic_ai import models
from pydantic_ai.models.test import TestModel
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.config import settings
from app.crud.user import UserCRUD
from app.models.nia import NiaScheduledRun, NiaScheduledTask, NiaThread
from app.services.nia_cadence import (
    is_due,
    next_fire,
    previous_fire,
    resolve_cron,
    validate_min_interval,
)
from app.services.nia_schedule import ADVISORY_LOCK_KEY, NiaScheduleService
from app.services.nia_usage import NiaUsageService
from f0rge_core.exceptions import ValidationError

models.ALLOW_MODEL_REQUESTS = False

TEST_MODEL_OUTPUT = "Overdue invoice brief"


class ArgsTestModel(TestModel):
    def __init__(self, tool_name: str, tool_args: dict, **kwargs) -> None:
        self._fixed_tool_name = tool_name
        self._fixed_tool_args = tool_args
        super().__init__(call_tools=[tool_name], **kwargs)

    def gen_tool_args(self, tool_def):
        if tool_def.name == self._fixed_tool_name:
            return self._fixed_tool_args
        return super().gen_tool_args(tool_def)


@pytest.fixture(autouse=True)
def nia_test_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        lambda: TestModel(custom_output_text=TEST_MODEL_OUTPUT, call_tools=[]),
    )


@pytest.fixture(autouse=True)
def openrouter_key_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openrouter_api_key", "test-openrouter-key")


async def _login(client: AsyncClient, email: str, password: str) -> AsyncClient:
    client.cookies.clear()
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return client


def _sku_args(suffix: str) -> dict:
    return {
        "our_ref": f"NIA-SCH-{suffix}",
        "our_barcode": f"NIA-SCH-BAR-{suffix}",
        "name": f"Schedule SKU {suffix}",
        "design": f"Design {suffix}",
        "fabric": f"Fabric {suffix}",
    }


def test_preset_cron_and_min_interval() -> None:
    assert resolve_cron("weekdays_08") == "0 8 * * 1-5"
    validate_min_interval("hourly", "Africa/Johannesburg")
    with pytest.raises(ValidationError, match="15 minutes"):
        validate_min_interval("*/5 * * * *", "Africa/Johannesburg")


def test_next_and_previous_fire_sast() -> None:
    now = datetime.datetime(2026, 9, 2, 6, 5, 0)  # 08:05 SAST
    nxt = next_fire("daily_08", "Africa/Johannesburg", now)
    assert nxt == datetime.datetime(2026, 9, 3, 6, 0, 0)
    prev = previous_fire("daily_08", "Africa/Johannesburg", now)
    assert prev == datetime.datetime(2026, 9, 2, 6, 0, 0)
    assert is_due(
        cadence="daily_08",
        timezone_name="Africa/Johannesburg",
        enabled=True,
        last_run_at=None,
        now=now,
    )
    assert not is_due(
        cadence="daily_08",
        timezone_name="Africa/Johannesburg",
        enabled=False,
        last_run_at=None,
        now=now,
    )
    assert not is_due(
        cadence="daily_08",
        timezone_name="Africa/Johannesburg",
        enabled=True,
        last_run_at=datetime.datetime(2026, 9, 2, 6, 0, 0),
        now=now,
    )


async def test_crud_own_tasks_only(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    created = await owner.post(
        "/api/v1/nia/schedule",
        json={
            "name": "Weekday 8:00 — list overdue invoices and summarise in a new thread",
            "prompt": "List overdue invoices and summarise them.",
            "cadence": "weekdays_08",
            "timezone": "Africa/Johannesburg",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["cadence"] == "weekdays_08"
    assert body["timezone"] == "Africa/Johannesburg"
    assert body["enabled"] is True
    assert body["next_run_at"]
    task_id = body["id"]

    listed = await owner.get("/api/v1/nia/schedule")
    assert listed.status_code == 200
    assert any(row["id"] == task_id for row in listed.json())

    till = await _login(async_client, "till@example.com", settings.seed_till_password)
    other = await till.get(f"/api/v1/nia/schedule/{task_id}")
    assert other.status_code == 404
    till_list = await till.get("/api/v1/nia/schedule")
    assert till_list.status_code == 200
    assert till_list.json() == []

    patched = await owner.patch(
        f"/api/v1/nia/schedule/{task_id}",
        json={"enabled": False},
    )
    assert patched.status_code == 200
    assert patched.json()["enabled"] is False
    assert patched.json()["next_run_at"] is None

    deleted = await owner.delete(f"/api/v1/nia/schedule/{task_id}")
    assert deleted.status_code == 204
    missing = await owner.get(f"/api/v1/nia/schedule/{task_id}")
    assert missing.status_code == 404


async def test_max_ten_enabled_and_fast_cron(
    owner_client: AsyncClient,
) -> None:
    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    for index in range(10):
        resp = await owner.post(
            "/api/v1/nia/schedule",
            json={
                "name": f"Task {index}",
                "prompt": "Summarise overdue invoices.",
                "cadence": "daily_08",
            },
        )
        assert resp.status_code == 201

    eleventh = await owner.post(
        "/api/v1/nia/schedule",
        json={
            "name": "Too many",
            "prompt": "Summarise overdue invoices.",
            "cadence": "daily_08",
        },
    )
    assert eleventh.status_code == 409

    fast = await owner.post(
        "/api/v1/nia/schedule",
        json={
            "name": "Too fast",
            "prompt": "Summarise overdue invoices.",
            "cadence": "custom",
            "cron": "*/5 * * * *",
            "enabled": False,
        },
    )
    assert fast.status_code == 422


async def test_run_now_creates_thread(
    owner_client: AsyncClient,
) -> None:
    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    created = await owner.post(
        "/api/v1/nia/schedule",
        json={
            "name": "Weekday overdue",
            "prompt": "List overdue invoices and summarise.",
            "cadence": "weekdays_08",
        },
    )
    assert created.status_code == 201
    task_id = created.json()["id"]

    ran = await owner.post(f"/api/v1/nia/schedule/{task_id}/run")
    assert ran.status_code == 200
    body = ran.json()
    assert body["last_status"] == "ok"
    assert body["last_thread_id"]

    thread = await owner.get(f"/api/v1/nia/threads/{body['last_thread_id']}")
    assert thread.status_code == 200
    payload = thread.json()
    assert payload["title"].startswith("Weekday overdue")
    messages = payload["messages"]
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == TEST_MODEL_OUTPUT

    threads = await owner.get("/api/v1/nia/threads")
    assert any(row["id"] == body["last_thread_id"] for row in threads.json())


async def test_run_now_hitl_does_not_create_sku(
    owner_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sku_args = _sku_args("HITL")
    monkeypatch.setattr(
        "app.services.nia_run.build_nia_model",
        lambda: ArgsTestModel("run_nia_action", {"action_id": "create_sku", "args": sku_args}),
    )
    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    created = await owner.post(
        "/api/v1/nia/schedule",
        json={
            "name": "Create SKU nightly",
            "prompt": "create sku",
            "cadence": "daily_08",
        },
    )
    assert created.status_code == 201
    task_id = created.json()["id"]

    ran = await owner.post(f"/api/v1/nia/schedule/{task_id}/run")
    assert ran.status_code == 200
    assert ran.json()["last_status"] == "needs_ok"
    thread_id = ran.json()["last_thread_id"]
    thread = await owner.get(f"/api/v1/nia/threads/{thread_id}")
    assistant = next(m for m in thread.json()["messages"] if m["role"] == "assistant")
    assert assistant["content"] == "Nia needs your approval"
    assert assistant["structured_payload"]["kind"] == "needs_ok"

    listed = await owner.get("/api/v1/skus")
    assert listed.status_code == 200
    assert not any(row["our_ref"] == sku_args["our_ref"] for row in listed.json())


async def test_disabled_tick_skips(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.datetime(2026, 9, 2, 6, 5, 0)
    monkeypatch.setattr("app.services.nia_schedule.utcnow", lambda: now)
    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    created = await owner.post(
        "/api/v1/nia/schedule",
        json={
            "name": "Disabled daily",
            "prompt": "Summarise overdue invoices.",
            "cadence": "daily_08",
            "enabled": False,
        },
    )
    assert created.status_code == 201
    task_id = uuid.UUID(created.json()["id"])

    ran = await NiaScheduleService(async_db).tick_due_tasks()
    assert ran == 0
    row = (
        await async_db.execute(sa.select(NiaScheduledTask).where(NiaScheduledTask.id == task_id))
    ).scalar_one()
    assert row.last_status is None
    runs = (
        (
            await async_db.execute(
                sa.select(NiaScheduledRun).where(NiaScheduledRun.task_id == task_id)
            )
        )
        .scalars()
        .all()
    )
    assert runs == []


async def test_tick_runs_due_task(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.datetime(2026, 9, 2, 6, 5, 0)
    monkeypatch.setattr("app.services.nia_schedule.utcnow", lambda: now)
    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    created = await owner.post(
        "/api/v1/nia/schedule",
        json={
            "name": "Due daily",
            "prompt": "Summarise overdue invoices.",
            "cadence": "daily_08",
        },
    )
    assert created.status_code == 201
    task_id = uuid.UUID(created.json()["id"])

    ran = await NiaScheduleService(async_db).tick_due_tasks()
    assert ran == 1
    row = (
        await async_db.execute(sa.select(NiaScheduledTask).where(NiaScheduledTask.id == task_id))
    ).scalar_one()
    assert row.last_status == "ok"
    threads = (
        (await async_db.execute(sa.select(NiaThread).where(NiaThread.title.like("Due daily%"))))
        .scalars()
        .all()
    )
    assert len(threads) == 1


async def test_cap_skip_no_thread(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.datetime(2026, 9, 2, 6, 5, 0)
    monkeypatch.setattr("app.services.nia_schedule.utcnow", lambda: now)
    user_crud = UserCRUD(async_db)
    owner_user = await user_crud.get_by_email("owner@example.com")
    assert owner_user is not None
    usage = NiaUsageService(async_db)
    await usage.record_usage(
        user_id=owner_user.id,
        model="test-model",
        prompt_tokens=50,
        completion_tokens=50,
    )
    cap = await owner_client.patch(
        f"/api/v1/nia/usage/{owner_user.id}",
        json={"nia_monthly_token_cap": 100},
    )
    assert cap.status_code == 200

    owner = await _login(owner_client, "owner@example.com", settings.seed_owner_password)
    created = await owner.post(
        "/api/v1/nia/schedule",
        json={
            "name": "Capped",
            "prompt": "Summarise overdue invoices.",
            "cadence": "daily_08",
        },
    )
    assert created.status_code == 201
    task_id = uuid.UUID(created.json()["id"])

    ran = await NiaScheduleService(async_db).tick_due_tasks()
    assert ran == 1
    row = (
        await async_db.execute(sa.select(NiaScheduledTask).where(NiaScheduledTask.id == task_id))
    ).scalar_one()
    assert row.last_status == "error"
    assert row.last_error == "nia_cap_exceeded"
    threads = (
        (await async_db.execute(sa.select(NiaThread).where(NiaThread.title.like("Capped%"))))
        .scalars()
        .all()
    )
    assert threads == []

    run_now = await owner.post(f"/api/v1/nia/schedule/{task_id}/run")
    assert run_now.status_code == 429


async def test_advisory_lock_skips_second_tick(
    async_engine: AsyncEngine,
    async_db: AsyncSession,
) -> None:
    async with async_engine.connect() as holder:
        await holder.execute(sa.text("SELECT pg_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY})
        try:
            ran = await NiaScheduleService(async_db).tick_due_tasks()
            assert ran == 0
        finally:
            await holder.execute(
                sa.text("SELECT pg_advisory_unlock(:key)"),
                {"key": ADVISORY_LOCK_KEY},
            )


async def test_logged_out_schedule(async_client: AsyncClient) -> None:
    async_client.cookies.clear()
    resp = await async_client.get("/api/v1/nia/schedule")
    assert resp.status_code == 401
