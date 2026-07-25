"""Circular-shift permutation null for signals tier calibration.

Run: uv --project apps/marrow/backend run python -m scripts.signals_permutation_null
"""

from __future__ import annotations

import argparse
import datetime
from pathlib import Path

import numpy as np

from app.services.signals.baseline import WARMUP_DAYS, compute_baseline_residuals
from app.services.signals.effects import estimate_all_effects

NULL_DRAWS = 200  # §Layer 3 — permutation null draws
P_ESTABLISHED_MAX = 0.05
P_EMERGING_MAX = 0.20


def _synthetic_null_rows(n_days: int, rng: np.random.Generator) -> tuple[list[dict], list[str]]:
    start = datetime.date(2025, 1, 1)
    columns = [
        "date",
        "schema_version",
        "overall",
        "sick",
        "photo_count",
        "ingredient_count",
        "had_alcohol",
        "histamine_load_sum",
        "hm_sleep_hours",
        "gluten_exposure",
        "dairy_exposure",
        "hm_steps",
        "wx_temp_mean",
        "caffeine_servings",
        "supp_magnesium",
        "supp_vitamin_d",
    ]
    rows: list[dict] = []
    for i in range(n_days):
        d = start + datetime.timedelta(days=i)
        overall = 3.4 + 0.003 * i + rng.normal(0, 0.45)
        rows.append(
            {
                "date": d.isoformat(),
                "schema_version": 4,
                "overall": overall,
                "sick": False,
                "photo_count": 1,
                "ingredient_count": 3,
                "had_alcohol": bool(i % 7 == 5),
                "histamine_load_sum": float(rng.uniform(0, 5)),
                "hm_sleep_hours": float(rng.uniform(5, 9)),
                "gluten_exposure": bool(i % 4 == 0),
                "dairy_exposure": bool(i % 5 == 0),
                "hm_steps": float(rng.integers(1000, 12000)),
                "wx_temp_mean": float(rng.uniform(5, 25)),
                "caffeine_servings": float(rng.integers(0, 4)),
                "supp_magnesium": bool(i % 3 == 0),
                "supp_vitamin_d": bool(i % 5 == 1),
            }
        )
    return rows, columns


def _circular_shift_exposures(
    rows: list[dict], columns: list[str], rng: np.random.Generator
) -> list[dict]:
    """Shift exposure columns; overall/residual relationship destroyed, autocorrelation preserved."""
    exposure_cols = [
        c
        for c in columns
        if c
        not in {
            "date",
            "schema_version",
            "overall",
            "sick",
            "photo_count",
            "ingredient_count",
        }
    ]
    shifted = [dict(r) for r in rows]
    n = len(shifted)
    if n < 2:
        return shifted
    offset = int(rng.integers(1, n))
    for col in exposure_cols:
        series = [r.get(col) for r in shifted]
        rotated = series[offset:] + series[:offset]
        for i, val in enumerate(rotated):
            shifted[i][col] = val
    return shifted


def run_permutation_null(
    *,
    draws: int = NULL_DRAWS,
    bootstrap_n: int = 400,
    seed: int = 4242,
) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    n_days = WARMUP_DAYS + 92
    base_rows, columns = _synthetic_null_rows(n_days, rng)

    established_hits = 0
    emerging_hits = 0
    feature_evals = 0

    for draw in range(draws):
        draw_rng = np.random.default_rng(seed + draw + 1)
        null_rows = _circular_shift_exposures(base_rows, columns, draw_rng)
        baseline = compute_baseline_residuals(null_rows, columns)
        effects = estimate_all_effects(
            null_rows, columns, baseline, bootstrap_n=bootstrap_n, rng=draw_rng
        )
        for effect in effects:
            feature_evals += 1
            if effect.tier == "established":
                established_hits += 1
            if effect.tier in ("established", "emerging"):
                emerging_hits += 1

    p_established = established_hits / feature_evals if feature_evals else 0.0
    p_emerging = emerging_hits / feature_evals if feature_evals else 0.0
    return {
        "draws": float(draws),
        "feature_evals": float(feature_evals),
        "p_established": p_established,
        "p_emerging": p_emerging,
        "established_hits": float(established_hits),
        "emerging_hits": float(emerging_hits),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Signals permutation-null calibration")
    parser.add_argument("--draws", type=int, default=NULL_DRAWS)
    parser.add_argument("--bootstrap-n", type=int, default=400)
    parser.add_argument("--seed", type=int, default=4242)
    args = parser.parse_args()

    stats = run_permutation_null(
        draws=args.draws,
        bootstrap_n=args.bootstrap_n,
        seed=args.seed,
    )
    print("Signals permutation null calibration")
    print(f"  draws: {int(stats['draws'])}")
    print(f"  feature evals: {int(stats['feature_evals'])}")
    print(
        f"  P(established): {stats['p_established']:.3f} "
        f"({int(stats['established_hits'])} / {int(stats['feature_evals'])})"
    )
    print(
        f"  P(emerging):  {stats['p_emerging']:.3f} "
        f"({int(stats['emerging_hits'])} / {int(stats['feature_evals'])})"
    )
    print(f"  thresholds: P(established) ≤ {P_ESTABLISHED_MAX}, P(emerging) ≤ {P_EMERGING_MAX}")
    ok = stats["p_established"] <= P_ESTABLISHED_MAX and stats["p_emerging"] <= P_EMERGING_MAX
    print(f"  pass: {ok}")

    doc_path = Path(__file__).resolve().parent.parent / "docs" / "signals_null_calibration.md"
    doc_path.write_text(
        "\n".join(
            [
                "# Signals permutation-null calibration",
                "",
                "Recorded output from `scripts/signals_permutation_null.py`.",
                "",
                f"- **draws:** {int(stats['draws'])}",
                f"- **bootstrap B per feature:** {args.bootstrap_n} (null harness; production B=2000)",
                f"- **seed:** {args.seed}",
                f"- **feature evals:** {int(stats['feature_evals'])}",
                f"- **P(established):** {stats['p_established']:.3f} ({int(stats['established_hits'])} / {int(stats['feature_evals'])})",
                f"- **P(emerging):** {stats['p_emerging']:.3f} ({int(stats['emerging_hits'])} / {int(stats['feature_evals'])})",
                f"- **required:** P(established) ≤ {P_ESTABLISHED_MAX}, P(emerging) ≤ {P_EMERGING_MAX}",
                f"- **pass:** {ok}",
                "",
                "Tier floors raised per null: ESTABLISHED_F=5, ESTABLISHED_THETA=0.25 (was 4/0.20).",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {doc_path}")


if __name__ == "__main__":
    main()
