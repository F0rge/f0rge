from __future__ import annotations

import datetime
import hashlib
import logging
import uuid
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.nia import NiaScheduledRunCRUD, NiaScheduledTaskCRUD
from app.crud.user import UserCRUD
from app.exceptions import NiaCapExceededError, NiaLlmUnconfiguredError
from app.services.nia_caps import check_nia_budget
from app.models.nia import NiaScheduledRun, NiaScheduledTask
from app.schemas.nia import (
    NiaScheduledTaskCreate,
    NiaScheduledTaskResponse,
    NiaScheduledTaskUpdate,
    NiaThreadCreate,
)
from app.services.nia_cadence import (
    CADENCE_PRESETS,
    DEFAULT_TIMEZONE,
    cadence_is_preset,
    is_due,
    next_fire,
    resolve_cron,
    utcnow,
    validate_min_interval,
    validate_timezone,
)
from app.services.nia_run import NiaRunService
from app.services.nia_threads import NiaThreadsService
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

logger = logging.getLogger(__name__)

MAX_ENABLED_TASKS = 10
ADVISORY_LOCK_KEY = 602041


def stored_cadence(cadence: str, cron: Optional[str]) -> str:
    if cadence == "custom":
        if not cron or not cron.strip():
            raise ValidationError("cron is required when cadence is custom")
        return resolve_cron(cron.strip())
    if cadence not in CADENCE_PRESETS:
        raise ValidationError("Unknown cadence")
    resolve_cron(cadence)
    return cadence


def response_cadence(stored: str) -> str:
    if cadence_is_preset(stored):
        return stored
    return "custom"


class NiaScheduleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = NiaScheduledTaskCRUD(db)
        self.run_crud = NiaScheduledRunCRUD(db)
        self.user_crud = UserCRUD(db)
        self.threads = NiaThreadsService(db)
        self.nia_run = NiaRunService(db)

    async def list_tasks(self, user_id: uuid.UUID) -> list[NiaScheduledTaskResponse]:
        rows = await self.crud.list_for_user(user_id)
        return [await self._to_response(row) for row in rows]

    async def create_task(
        self,
        user_id: uuid.UUID,
        data: NiaScheduledTaskCreate,
    ) -> NiaScheduledTaskResponse:
        user = await self.user_crud.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        timezone_name = validate_timezone(data.timezone or DEFAULT_TIMEZONE)
        cadence = stored_cadence(data.cadence, data.cron)
        validate_min_interval(cadence, timezone_name)
        if data.enabled:
            await self._assert_enabled_cap(user_id)
        task = NiaScheduledTask(
            user_id=user_id,
            team_id=user.team_id,
            name=data.name,
            prompt=data.prompt,
            timezone=timezone_name,
            cadence=cadence,
            enabled=data.enabled,
            notify_only_if_changed=data.notify_only_if_changed,
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(task)
        return await self._to_response(task)

    async def get_task(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> NiaScheduledTaskResponse:
        return await self._to_response(await self._owned_or_404(user_id, task_id))

    async def update_task(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        data: NiaScheduledTaskUpdate,
    ) -> NiaScheduledTaskResponse:
        task = await self._owned_or_404(user_id, task_id)
        cadence = task.cadence
        timezone_name = task.timezone
        if data.cadence is not None or data.cron is not None:
            next_cadence = data.cadence or (
                "custom" if not cadence_is_preset(task.cadence) else task.cadence
            )
            cron = (
                data.cron
                if data.cron is not None
                else (task.cadence if not cadence_is_preset(task.cadence) else None)
            )
            cadence = stored_cadence(next_cadence, cron)
        if data.timezone is not None:
            timezone_name = validate_timezone(data.timezone)
        validate_min_interval(cadence, timezone_name)

        enabling = data.enabled is True and not task.enabled
        if enabling:
            await self._assert_enabled_cap(user_id, exclude_id=task.id)

        async with unit_of_work(self.db):
            if data.name is not None:
                task.name = data.name
            if data.prompt is not None:
                task.prompt = data.prompt
            task.timezone = timezone_name
            task.cadence = cadence
            if data.enabled is not None:
                task.enabled = data.enabled
            if data.notify_only_if_changed is not None:
                task.notify_only_if_changed = data.notify_only_if_changed
            await self.db.flush()
        return await self._to_response(task)

    async def delete_task(self, user_id: uuid.UUID, task_id: uuid.UUID) -> None:
        task = await self._owned_or_404(user_id, task_id)
        async with unit_of_work(self.db):
            await self.crud.delete(task)

    async def run_now(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> NiaScheduledTaskResponse:
        task = await self._owned_or_404(user_id, task_id)
        await self._execute_task(task, force=True)
        refreshed = await self._owned_or_404(user_id, task_id)
        return await self._to_response(refreshed)

    async def tick_due_tasks(self) -> int:
        locked = await self._try_advisory_lock()
        if not locked:
            return 0
        ran = 0
        try:
            now = utcnow()
            enabled = await self.crud.list_enabled()
            for task in enabled:
                if not is_due(
                    cadence=task.cadence,
                    timezone_name=task.timezone,
                    enabled=task.enabled,
                    last_run_at=task.last_run_at,
                    now=now,
                ):
                    continue
                claimed = await self._claim_task(task.id, now)
                if claimed is None:
                    continue
                await self._execute_task(claimed, force=False, claimed_at=now)
                ran += 1
        finally:
            await self._advisory_unlock()
        return ran

    async def _claim_task(
        self,
        task_id: uuid.UUID,
        now,
    ) -> Optional[NiaScheduledTask]:
        task = await self.crud.get_for_update_skip_locked(task_id)
        if task is None or not task.enabled:
            return None
        if not is_due(
            cadence=task.cadence,
            timezone_name=task.timezone,
            enabled=task.enabled,
            last_run_at=task.last_run_at,
            now=now,
        ):
            return None
        async with unit_of_work(self.db):
            task.last_run_at = now
            await self.db.flush()
        return task

    async def _execute_task(
        self,
        task: NiaScheduledTask,
        *,
        force: bool,
        claimed_at=None,
    ) -> None:
        started_at = claimed_at or utcnow()
        thread_id: Optional[uuid.UUID] = None
        status = "error"
        error: Optional[str] = None
        output_hash: Optional[str] = None
        try:
            if not settings.openrouter_api_key.strip():
                raise NiaLlmUnconfiguredError()
            await check_nia_budget(self.db, task.user_id)
            title = f"{task.name} — {_local_date_label(started_at, task.timezone)}"
            thread = await self.threads.create_thread(
                task.user_id,
                NiaThreadCreate(title=title),
            )
            thread_id = thread.id
            assistant_text, pending_kind = await self.nia_run.run_prompt(
                user_id=task.user_id,
                thread_id=thread_id,
                prompt=task.prompt,
            )
            output_hash = hashlib.sha256(assistant_text.encode("utf-8")).hexdigest()
            if pending_kind:
                status = "needs_ok"
            elif (
                task.notify_only_if_changed
                and task.last_output_hash
                and task.last_output_hash == output_hash
            ):
                status = "skipped"
            else:
                status = "ok"
        except NiaCapExceededError:
            status = "error"
            error = "nia_cap_exceeded"
            logger.info("nia schedule skip cap user=%s task=%s", task.user_id, task.id)
        except NiaLlmUnconfiguredError:
            status = "error"
            error = "nia_llm_unconfigured"
        except Exception as exc:
            status = "error"
            error = str(getattr(exc, "detail", None) or exc)
            logger.exception("nia schedule run failed task=%s", task.id)

        finished_at = utcnow()
        run_row = NiaScheduledRun(
            task_id=task.id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            thread_id=thread_id,
        )
        async with unit_of_work(self.db):
            current = await self.crud.get_owned(task.id, task.user_id)
            if current is None:
                current = task
            current.last_run_at = started_at
            current.last_status = status
            current.last_error = error
            if output_hash:
                current.last_output_hash = output_hash
            await self.run_crud.add_and_flush(run_row)

        if force and error == "nia_cap_exceeded":
            raise NiaCapExceededError()
        if force and error == "nia_llm_unconfigured":
            raise NiaLlmUnconfiguredError()

    async def _assert_enabled_cap(
        self,
        user_id: uuid.UUID,
        *,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> None:
        count = await self.crud.count_enabled_for_user(user_id, exclude_id=exclude_id)
        if count >= MAX_ENABLED_TASKS:
            raise ConflictError("Maximum of 10 enabled scheduled tasks")

    async def _owned_or_404(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> NiaScheduledTask:
        task = await self.crud.get_owned(task_id, user_id)
        if task is None:
            raise NotFoundError("Scheduled task not found")
        return task

    async def _to_response(self, task: NiaScheduledTask) -> NiaScheduledTaskResponse:
        latest = await self.run_crud.latest_for_task(task.id)
        now = utcnow()
        nxt = None
        if task.enabled:
            nxt = next_fire(task.cadence, task.timezone, now)
            if nxt is not None and nxt.tzinfo is None:
                nxt = nxt.replace(tzinfo=datetime.timezone.utc)
        stored = task.cadence
        preset = cadence_is_preset(stored)
        return NiaScheduledTaskResponse(
            id=task.id,
            name=task.name,
            prompt=task.prompt,
            timezone=task.timezone,
            cadence=response_cadence(stored),
            cron=None if preset else stored,
            enabled=task.enabled,
            notify_only_if_changed=task.notify_only_if_changed,
            last_run_at=task.last_run_at,
            last_status=task.last_status,
            last_error=task.last_error,
            next_run_at=nxt,
            last_thread_id=latest.thread_id if latest else None,
            created_at=task.created_at,
        )

    async def _try_advisory_lock(self) -> bool:
        result = await self.db.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": ADVISORY_LOCK_KEY},
        )
        return bool(result.scalar())

    async def _advisory_unlock(self) -> None:
        await self.db.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": ADVISORY_LOCK_KEY},
        )


def _local_date_label(when, timezone_name: str) -> str:
    from zoneinfo import ZoneInfo

    import datetime as dt

    aware = when.replace(tzinfo=dt.timezone.utc)
    local = aware.astimezone(ZoneInfo(timezone_name))
    return local.date().isoformat()
