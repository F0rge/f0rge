from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.insights import InsightsCRUD
from f0rge_core.exceptions import ValidationError
from app.schemas.insights import (
    TrendPoint,
    TrendSeries,
    TreatmentResponseList,
    TreatmentResponseRow,
    TrendsResponse,
)
from app.services.feature_matrix import build_feature_matrix
from app.services.stats import categorize_feature
from app.utils.dates import local_today

# ── private helpers ────────────────────────────────────────────────────────────

_CORE_OUTCOMES: frozenset[str] = frozenset(
    {
        "overall",
        "bloating",
        "sleep_quality",
        "stress",
        "sick",
    }
)

# /trends delta_30d: how far back (in days) "current" is compared against.
TREND_DELTA_WINDOW_DAYS = 30

# Core series always included in /trends (besides sym_*)
_TREND_SERIES_KEYS: list[str] = [
    "overall",
    "bloating",
    "sleep_quality",
    "stress",
    "hm_hrv_mean",
    "hm_sleep_efficiency",
    "hm_resting_hr",
]


def _humanize(col: str) -> str:
    """Convert a feature-matrix column name to a readable label."""
    label = col
    for prefix in ("sym_", "supp_", "hm_", "wx_"):
        if label.startswith(prefix):
            label = label[len(prefix) :]
            break
    if label.startswith("tx_") and label.endswith("_active"):
        label = label[3:-7]
    elif label.startswith("tx_"):
        label = label[3:]

    return label.replace("_", " ").title()


def _rolling_avg_7(values: list[Optional[float]], idx: int) -> Optional[float]:
    """Trailing 7-day average ending at idx (right-aligned, skip Nones)."""
    window = [v for v in values[max(0, idx - 6) : idx + 1] if v is not None]
    if not window:
        return None
    return round(sum(window) / len(window), 4)


def _safe_mean(vals: list[Optional[float]]) -> Optional[float]:
    real = [v for v in vals if v is not None]
    if not real:
        return None
    return round(sum(real) / len(real), 4)


def _coerce_numeric(val: object) -> Optional[float]:
    """Convert a feature-matrix cell to float; booleans → 0/1; strings → None."""
    if val is None:
        return None
    if isinstance(val, bool):
        return float(val)
    if isinstance(val, (int, float)):
        return float(val)
    return None


class InsightsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = InsightsCRUD(db)

    async def _allowed_outcomes(self, columns: Optional[list[str]] = None) -> frozenset[str]:
        """Return the full whitelist of valid outcome column names."""
        if columns is None:
            _, columns = await build_feature_matrix(self.db, None, None)
        sym_cols = frozenset(c for c in columns if c.startswith("sym_"))
        return _CORE_OUTCOMES | sym_cols

    async def compute_trends(
        self,
        start: Optional[datetime.date] = None,
        end: Optional[datetime.date] = None,
    ) -> TrendsResponse:
        rows, columns = await build_feature_matrix(self.db, start, end)

        sym_cols = [c for c in columns if c.startswith("sym_")]
        series_keys = _TREND_SERIES_KEYS + sym_cols

        series_out: list[TrendSeries] = []
        for key in series_keys:
            if key not in columns:
                continue

            raw_values: list[Optional[float]] = [_coerce_numeric(row.get(key)) for row in rows]
            dates: list[str] = [row["date"] for row in rows]

            points: list[TrendPoint] = []
            for i, (date, val) in enumerate(zip(dates, raw_values)):
                points.append(
                    TrendPoint(
                        date=date,
                        value=val,
                        rolling_avg_7=_rolling_avg_7(raw_values, i),
                    )
                )

            # Current = last non-null value
            current: Optional[float] = None
            for v in reversed(raw_values):
                if v is not None:
                    current = v
                    break

            # Rolling avg at latest point
            latest_rolling = points[-1].rolling_avg_7 if points else None

            # delta_30d: compare last non-null with the rolling avg ~30 days ago
            delta_30d: Optional[float] = None
            if len(points) >= TREND_DELTA_WINDOW_DAYS and current is not None:
                ref_rolling = points[-TREND_DELTA_WINDOW_DAYS].rolling_avg_7
                if ref_rolling is not None:
                    delta_30d = round(current - ref_rolling, 4)

            series_out.append(
                TrendSeries(
                    key=key,
                    label=_humanize(key),
                    category=categorize_feature(key),
                    points=points,
                    current=current,
                    rolling_avg_7=latest_rolling,
                    delta_30d=delta_30d,
                )
            )

        return TrendsResponse(series=series_out)

    async def compute_treatment_response(
        self,
        outcome: str,
    ) -> TreatmentResponseList:
        _, columns = await build_feature_matrix(self.db, None, None)
        allowed = await self._allowed_outcomes(columns)
        if outcome not in allowed:
            raise ValidationError(f"unknown outcome: {outcome!r}")

        today = local_today()
        treatments = await self.crud.list_treatments_with_start_date()

        rows_out: list[TreatmentResponseRow] = []

        for tx in treatments:
            start = tx.start_date
            end = tx.end_date

            baseline_start = start - datetime.timedelta(days=30)
            baseline_end = start - datetime.timedelta(days=1)
            during_start = start
            during_end = end if end is not None else today

            # Fetch baseline window
            baseline_rows, _ = await build_feature_matrix(self.db, baseline_start, baseline_end)
            baseline_vals: list[Optional[float]] = [
                _coerce_numeric(r.get(outcome)) for r in baseline_rows
            ]
            baseline_n = sum(1 for v in baseline_vals if v is not None)

            # Skip treatments with insufficient baseline data
            if baseline_n < 5:
                continue

            # Fetch during window
            during_rows, _ = await build_feature_matrix(self.db, during_start, during_end)
            during_vals: list[Optional[float]] = [
                _coerce_numeric(r.get(outcome)) for r in during_rows
            ]
            during_n = sum(1 for v in during_vals if v is not None)

            # Fetch after window (only if treatment has ended)
            after_vals: list[Optional[float]] = []
            after_n = 0
            if end is not None:
                after_start = end + datetime.timedelta(days=1)
                after_end = end + datetime.timedelta(days=30)
                if after_start <= today:
                    after_rows, _ = await build_feature_matrix(self.db, after_start, after_end)
                    after_vals = [_coerce_numeric(r.get(outcome)) for r in after_rows]
                    after_n = sum(1 for v in after_vals if v is not None)

            baseline_mean = _safe_mean(baseline_vals)
            during_mean = _safe_mean(during_vals)
            after_mean = _safe_mean(after_vals) if after_vals else None

            delta: Optional[float] = None
            if during_mean is not None and baseline_mean is not None:
                delta = round(during_mean - baseline_mean, 4)

            rows_out.append(
                TreatmentResponseRow(
                    treatment_id=tx.id,
                    name=tx.name,
                    type=tx.type,
                    start_date=tx.start_date.isoformat(),
                    end_date=tx.end_date.isoformat() if tx.end_date else None,
                    baseline_mean=baseline_mean,
                    during_mean=during_mean,
                    after_mean=after_mean,
                    baseline_n=baseline_n,
                    during_n=during_n,
                    after_n=after_n,
                    delta_during_vs_baseline=delta,
                )
            )

        return TreatmentResponseList(outcome=outcome, rows=rows_out)
