from __future__ import annotations

import datetime
from dataclasses import dataclass, field

import numpy as np

# Layer 1 constants — see apps/marrow/backend/docs/signals_method.md §Layer 1
EWMA_HALF_LIFE_DAYS = 21  # §Layer 1 — rolling personal level L(t)
EWMA_ALPHA = 1.0 - 2.0 ** (-1.0 / EWMA_HALF_LIFE_DAYS)  # ≈ 0.0325
WEEKDAY_SHRINK_PRIOR = 10  # §Layer 1 — W(d) prior k
TREND_WINDOW_DAYS = 56  # §Layer 1 — trailing slope window for T(t)
TREND_CAP_POINTS_PER_DAY = 0.02  # §Layer 1 — |T| cap
WARMUP_DAYS = 28  # §Layer 1 — excluded from estimation
CONFOUNDED_TREND_CORR = 0.6  # §Layer 1 — confounded-with-trend threshold
MIN_SCHEMA_VERSION = 4  # Part B — estimate on schema_version >= 4 only


@dataclass
class BaselineDiagnostics:
    days_total: int
    days_v4: int
    days_usable: int
    warmup_days: int
    drop_reasons: dict[str, int] = field(default_factory=dict)


@dataclass
class BaselineResult:
    dates: list[str]
    overall: list[float | None]
    y_hat: list[float | None]
    residuals: list[float | None]
    L: list[float | None]
    W: list[float | None]
    T: list[float | None]
    diagnostics: BaselineDiagnostics
    confounded_with_trend: list[str] = field(default_factory=list)


def _parse_date(date_val: str | datetime.date) -> datetime.date:
    if isinstance(date_val, datetime.date):
        return date_val
    return datetime.date.fromisoformat(str(date_val))


def weekday_shrinkage_factor(n_d: int) -> float:
    """Shrinkage n_d/(n_d + k); k=WEEKDAY_SHRINK_PRIOR (signals_method.md §Layer 1)."""
    if n_d <= 0:
        return 0.0
    return n_d / (n_d + WEEKDAY_SHRINK_PRIOR)


def _weekday_offset(n_d: int, mean_d: float, overall_mean: float) -> float:
    """Shrunk day-of-week offset; see signals_method.md §Layer 1 W(d)."""
    if n_d <= 0:
        return 0.0
    return weekday_shrinkage_factor(n_d) * (mean_d - overall_mean)


def _ewma_level(prior_overalls: list[float], init_level: float) -> float:
    """EWMA of observed overall values; half-life EWMA_HALF_LIFE_DAYS."""
    level = init_level
    for y in prior_overalls:
        level = EWMA_ALPHA * y + (1.0 - EWMA_ALPHA) * level
    return level


def _trend_slope(prior_overalls: list[float]) -> float:
    """Trailing linear slope over up to TREND_WINDOW_DAYS prior days, capped."""
    window = prior_overalls[-TREND_WINDOW_DAYS:]
    n = len(window)
    if n < 2:
        return 0.0
    x = np.arange(n, dtype=float)
    y = np.asarray(window, dtype=float)
    slope = float(np.polyfit(x, y, 1)[0])
    return float(np.clip(slope, -TREND_CAP_POINTS_PER_DAY, TREND_CAP_POINTS_PER_DAY))


def _fit_covariate_coeffs(
    prior_residuals: list[float],
    prior_design: list[list[float]],
    n_params: int,
) -> list[float]:
    """OLS on prior days: adjusted outcome ~ covariates (no intercept)."""
    if n_params == 0:
        return []
    if len(prior_residuals) < 2 or not prior_design:
        return [0.0] * n_params
    y = np.asarray(prior_residuals, dtype=float)
    x = np.asarray(prior_design, dtype=float)
    if x.ndim != 2 or x.shape[0] != y.shape[0]:
        return [0.0] * n_params
    if x.shape[0] <= x.shape[1]:
        return [0.0] * n_params
    coeffs, _, _, _ = np.linalg.lstsq(x, y, rcond=None)
    return [float(c) for c in coeffs]


def _coerce_bool(value: object) -> float:
    if value is True or value == 1:
        return 1.0
    return 0.0


def _regime_and_coverage_columns(columns: list[str]) -> list[str]:
    cols: list[str] = []
    for col in columns:
        if col.startswith("tx_") and col.endswith("_active"):
            cols.append(col)
    for col in ("photo_count", "ingredient_count"):
        if col in columns:
            cols.append(col)
    return cols


def _candidate_exposure_columns(columns: list[str]) -> list[str]:
    """Columns eligible for confounded-with-trend screening."""
    skip = {
        "date",
        "schema_version",
        "period_of_day",
        "overall",
        "photo_count",
        "ingredient_count",
        "sick",
    }
    exposures: list[str] = []
    for col in columns:
        if col in skip:
            continue
        if col.startswith("tx_") and col.endswith("_active"):
            continue
        exposures.append(col)
    return exposures


def _series_corr(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3 or len(a) != len(b):
        return None
    arr_a = np.asarray(a, dtype=float)
    arr_b = np.asarray(b, dtype=float)
    if np.std(arr_a) == 0.0 or np.std(arr_b) == 0.0:
        return None
    return float(np.corrcoef(arr_a, arr_b)[0, 1])


def _compute_lwt(
    prior_overalls: list[float],
    prior_dow_lists: list[list[float]],
    dow: int,
    init_level: float,
) -> tuple[float, float, float]:
    l_val = _ewma_level(prior_overalls, init_level) if prior_overalls else init_level
    if prior_overalls:
        overall_mean = float(np.mean(prior_overalls))
        dow_vals = prior_dow_lists[dow]
        n_d = len(dow_vals)
        mean_d = float(np.mean(dow_vals)) if dow_vals else overall_mean
        w_val = _weekday_offset(n_d, mean_d, overall_mean)
    else:
        w_val = 0.0
    t_val = _trend_slope(prior_overalls)
    return l_val, w_val, t_val


def compute_baseline_residuals(
    rows: list[dict],
    columns: list[str],
) -> BaselineResult:
    """Personal-baseline residualisation (Layer 1); no leakage — day t uses only days < t."""
    sorted_rows = sorted(rows, key=lambda r: _parse_date(r["date"]))
    regime_cols = _regime_and_coverage_columns(columns)
    n_covariates = 1 + len(regime_cols)  # sick + regime/coverage

    drop_reasons: dict[str, int] = {
        "legacy_schema": 0,
        "missing_overall": 0,
        "warmup": 0,
    }

    v4_rows: list[dict] = []
    for row in sorted_rows:
        schema = row.get("schema_version")
        if schema is None or schema < MIN_SCHEMA_VERSION:
            if row.get("overall") is not None:
                drop_reasons["legacy_schema"] += 1
            continue
        overall = row.get("overall")
        if overall is None:
            drop_reasons["missing_overall"] += 1
            continue
        v4_rows.append(row)

    v4_overalls = [float(r["overall"]) for r in v4_rows]
    init_level = float(np.mean(v4_overalls[:WARMUP_DAYS])) if v4_overalls else 0.0

    dates: list[str] = []
    overall_out: list[float | None] = []
    y_hat_out: list[float | None] = []
    residuals_out: list[float | None] = []
    l_out: list[float | None] = []
    w_out: list[float | None] = []
    t_out: list[float | None] = []
    trend_series: list[float] = []
    usable_positions: list[int] = []

    prior_overalls: list[float] = []
    prior_dow_lists: list[list[float]] = [[] for _ in range(7)]
    history_l: list[float] = []
    history_w: list[float] = []
    history_t: list[float] = []

    for v4_pos, row in enumerate(v4_rows):
        overall = float(row["overall"])
        date_obj = _parse_date(row["date"])
        dow = date_obj.weekday()

        l_val, w_val, t_val = _compute_lwt(prior_overalls, prior_dow_lists, dow, init_level)

        prior_adjusted: list[float] = []
        prior_design: list[list[float]] = []
        for p_idx, p_row in enumerate(v4_rows[:v4_pos]):
            p_adj = float(p_row["overall"]) - history_l[p_idx] - history_w[p_idx] - history_t[p_idx]
            prior_adjusted.append(p_adj)
            prior_design.append(
                [_coerce_bool(p_row.get("sick"))]
                + [_coerce_bool(p_row.get(c)) for c in regime_cols]
            )

        coeffs = _fit_covariate_coeffs(prior_adjusted, prior_design, n_covariates)
        cov_vec = [_coerce_bool(row.get("sick"))] + [_coerce_bool(row.get(c)) for c in regime_cols]
        cov_contrib = sum(c * v for c, v in zip(coeffs, cov_vec))

        y_hat = l_val + w_val + t_val + cov_contrib
        residual = overall - y_hat

        is_warmup = v4_pos < WARMUP_DAYS
        if is_warmup:
            drop_reasons["warmup"] += 1

        dates.append(str(row["date"]))
        overall_out.append(overall)
        l_out.append(l_val)
        w_out.append(w_val)
        t_out.append(t_val)
        y_hat_out.append(y_hat)
        residuals_out.append(residual)
        trend_series.append(t_val)
        history_l.append(l_val)
        history_w.append(w_val)
        history_t.append(t_val)
        if not is_warmup:
            usable_positions.append(v4_pos)

        prior_overalls.append(overall)
        prior_dow_lists[dow].append(overall)

    days_v4 = len(v4_rows)
    days_usable = max(0, days_v4 - WARMUP_DAYS)

    confounded: list[str] = []
    for col in _candidate_exposure_columns(columns):
        exposure_vals: list[float] = []
        t_vals: list[float] = []
        for pos in usable_positions:
            row = v4_rows[pos]
            val = row.get(col)
            if val is None:
                continue
            if isinstance(val, bool):
                exposure_vals.append(1.0 if val else 0.0)
            elif isinstance(val, (int, float)):
                exposure_vals.append(float(val))
            else:
                continue
            t_vals.append(trend_series[pos])
        if len(exposure_vals) < 3:
            continue
        corr = _series_corr(exposure_vals, t_vals)
        if corr is not None and abs(corr) >= CONFOUNDED_TREND_CORR:
            confounded.append(col)

    diagnostics = BaselineDiagnostics(
        days_total=len(sorted_rows),
        days_v4=days_v4,
        days_usable=days_usable,
        warmup_days=WARMUP_DAYS,
        drop_reasons=drop_reasons,
    )

    return BaselineResult(
        dates=dates,
        overall=overall_out,
        y_hat=y_hat_out,
        residuals=residuals_out,
        L=l_out,
        W=w_out,
        T=t_out,
        diagnostics=diagnostics,
        confounded_with_trend=sorted(confounded),
    )
