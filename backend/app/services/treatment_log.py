from __future__ import annotations

import datetime
from collections import defaultdict
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.models.treatment import Treatment
from app.models.treatment_log import TreatmentLog
from app.schemas.treatment_log import ProtocolItem, ProtocolResponse, ProtocolToday
from app.tenant import current_user_id, owned_by_user
from app.utils.dates import local_today
from app.utils.streak import compute_streak


class TreatmentLogService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert(
        self, treatment_id: int, date: datetime.date, doses_taken: int
    ) -> TreatmentLog:
        treatment = (
            await self.db.execute(
                select(Treatment).where(
                    owned_by_user(Treatment.user_id),
                    Treatment.id == treatment_id,
                )
            )
        ).scalar_one_or_none()
        if treatment is None:
            raise NotFoundError(f"Treatment {treatment_id} not found.")

        clamped = max(0, min(doses_taken, treatment.doses_per_day or 0))

        existing = (
            await self.db.execute(
                select(TreatmentLog).where(
                    owned_by_user(TreatmentLog.user_id),
                    TreatmentLog.treatment_id == treatment_id,
                    TreatmentLog.date == date,
                )
            )
        ).scalar_one_or_none()

        now = datetime.datetime.utcnow()
        if existing is not None:
            existing.doses_taken = clamped
            existing.updated_at = now
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        log = TreatmentLog(
            user_id=current_user_id(),
            treatment_id=treatment_id,
            date=date,
            doses_taken=clamped,
            updated_at=now,
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def get_protocol(self, on_date: Optional[datetime.date] = None) -> ProtocolResponse:
        target = on_date if on_date is not None else local_today()

        active = await self._active_treatments(target)
        taken_today = await self._log_map_for_date(target, [t.id for t in active])

        items = [
            ProtocolItem(
                id=t.id,
                name=t.name,
                dose=t.dose,
                doses_per_day=t.doses_per_day,
                doses_taken=taken_today.get(t.id, 0),
                day_num=(target - t.start_date).days + 1,
            )
            for t in active
        ]

        dose_tracked = [t for t in active if t.doses_per_day is not None]
        doses_taken_sum = sum(taken_today.get(t.id, 0) for t in dose_tracked)
        doses_planned_sum = sum(t.doses_per_day for t in dose_tracked)
        pct = doses_taken_sum / doses_planned_sum if doses_planned_sum else 0.0

        current_streak, best_streak = await self._compute_streaks(target)

        return ProtocolResponse(
            items=items,
            today=ProtocolToday(
                doses_taken=doses_taken_sum,
                doses_planned=doses_planned_sum,
                pct=pct,
            ),
            streak=current_streak,
            best_streak=best_streak,
        )

    async def _active_treatments(self, on_date: datetime.date) -> list[Treatment]:
        stmt = (
            select(Treatment)
            .where(
                owned_by_user(Treatment.user_id),
                Treatment.start_date <= on_date,
                (Treatment.end_date.is_(None)) | (Treatment.end_date >= on_date),
            )
            .order_by(Treatment.start_date.asc(), Treatment.id.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def _log_map_for_date(
        self, on_date: datetime.date, treatment_ids: list[int]
    ) -> dict[int, int]:
        if not treatment_ids:
            return {}
        stmt = select(TreatmentLog).where(
            owned_by_user(TreatmentLog.user_id),
            TreatmentLog.date == on_date,
            TreatmentLog.treatment_id.in_(treatment_ids),
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return {row.treatment_id: row.doses_taken for row in rows}

    async def _compute_streaks(self, on_date: datetime.date) -> tuple[int, int]:
        dose_tracked = list(
            (
                await self.db.execute(
                    select(Treatment).where(
                        owned_by_user(Treatment.user_id),
                        Treatment.doses_per_day.is_not(None),
                        Treatment.start_date <= on_date,
                    )
                )
            )
            .scalars()
            .all()
        )
        if not dose_tracked:
            return compute_streak([], on_date)

        earliest = min(t.start_date for t in dose_tracked)
        treatment_ids = [t.id for t in dose_tracked]
        logs = (
            (
                await self.db.execute(
                    select(TreatmentLog).where(
                        owned_by_user(TreatmentLog.user_id),
                        TreatmentLog.treatment_id.in_(treatment_ids),
                        TreatmentLog.date >= earliest,
                        TreatmentLog.date <= on_date,
                    )
                )
            )
            .scalars()
            .all()
        )
        taken_by_day: dict[datetime.date, dict[int, int]] = defaultdict(dict)
        for log in logs:
            taken_by_day[log.date][log.treatment_id] = log.doses_taken

        day_completions: list[tuple[datetime.date, int, int]] = []
        day = earliest
        one_day = datetime.timedelta(days=1)
        while day <= on_date:
            active_today = [
                t
                for t in dose_tracked
                if t.start_date <= day and (t.end_date is None or t.end_date >= day)
            ]
            planned = sum(t.doses_per_day for t in active_today)
            taken = sum(taken_by_day[day].get(t.id, 0) for t in active_today)
            day_completions.append((day, planned, taken))
            day += one_day

        return compute_streak(day_completions, on_date)
