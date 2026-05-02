from __future__ import annotations

import logging
import os
import tempfile
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.config import settings
from app.models.entry import Entry
from app.models.health_metrics import HealthMetric
from app.models.photo import Photo
from app.services.weather import get_daily_summary

logger = logging.getLogger(__name__)

OVERALL_LABELS = {
    1: "Very Poor",
    2: "Standard",
    3: "Very Good",
}

SUPPLEMENT_LABELS = {
    "nac": "NAC",
    "fish_oil": "Fish Oil",
    "magnesium": "Magnesium",
    "beef_organs": "Beef Organs",
    "allicin": "Allicin",
    "oregano": "Oregano Oil",
    "vitamin_d_k2": "Vitamin D+K2",
    "dao": "DAO Enzyme",
    "creatine": "Creatine",
}

BLOATING_LABELS = {0: "None", 1: "Mild", 2: "Moderate", 3: "Severe"}

JOINT_PAIN_LABELS = {0: "None", 1: "Mild", 2: "Moderate", 3: "Severe"}

NEURO_LABELS = {-1: "Worse than usual", 0: "Baseline", 1: "Better than usual"}

SLEEP_LABELS = {1: "Poor", 2: "OK", 3: "Good"}

STRESS_LABELS = {1: "Low", 2: "Medium", 3: "High"}


def _format_supplements(supplements_str: str) -> str:
    if not supplements_str:
        return "None"
    taken = [s.strip() for s in supplements_str.split(",") if s.strip()]
    labels = [SUPPLEMENT_LABELS.get(s, s) for s in taken]
    return ", ".join(labels) if labels else "None"


def _render_markdown(
    db_session: Session, entry: Entry, photos: Sequence[Photo]
) -> str:
    date_str = entry.date.isoformat()
    stool_str = "true" if entry.stool_normal else "false"
    sick_str = "true" if entry.sick else "false"

    lines = [
        "---",
        "created-by: health-tracker",
        f"created: {date_str}",
        "modified-by: health-tracker",
        f"modified: {date_str}",
        "tags:",
        "  - daily-check-in",
        "  - symptom-log",
        f"overall: {entry.overall}",
        f"bloating: {entry.bloating}",
        f"stool-normal: {stool_str}",
        f"stool-type: {entry.stool_type or ''}",
        f"joint-pain: {entry.joint_pain}",
        f"neuro: {entry.neuro}",
        f"sleep-quality: {entry.sleep_quality}",
        f"stress: {entry.stress}",
        f"diet-risk: {entry.diet_risk}",
        f"supplements: {entry.supplements}",
        f"sick: {sick_str}",
        "---",
        "",
        f"# Daily Check-in: {date_str}",
        "",
        "## Summary",
        "",
        "| Category | Value |",
        "|----------|-------|",
        f"| Overall day | {OVERALL_LABELS.get(entry.overall, str(entry.overall))} ({entry.overall}/3) |",
        f"| Bloating | {BLOATING_LABELS.get(entry.bloating, str(entry.bloating))} |",
        f"| Stool | {'Normal' if entry.stool_normal else 'Abnormal' + (' (' + entry.stool_type + ')' if entry.stool_type else '')} |",
        f"| Joint pain | {JOINT_PAIN_LABELS.get(entry.joint_pain, str(entry.joint_pain))} |",
        f"| Neuro | {NEURO_LABELS.get(entry.neuro, str(entry.neuro))} |",
        f"| Sleep quality | {SLEEP_LABELS.get(entry.sleep_quality, str(entry.sleep_quality))} |",
        f"| Stress | {STRESS_LABELS.get(entry.stress, str(entry.stress))} |",
        f"| Diet risk | {entry.diet_risk} |",
        f"| Supplements | {_format_supplements(entry.supplements)} |",
        f"| Sick | {sick_str} |",
        "",
        "## Notes",
        "",
        entry.notes if entry.notes else "No notes recorded.",
        "",
    ]

    if photos:
        lines.append("## Photos")
        lines.append("")
        for photo in photos:
            lines.append(f"![[attachments/{photo.filename}]]")
            if photo.label:
                lines.append(f"*{photo.label}*")
            lines.append("")

    health = None
    weather = None
    try:
        health = (
            db_session.query(HealthMetric)
            .filter(HealthMetric.date == entry.date)
            .one_or_none()
        )
    except Exception:
        logger.exception("Failed to query HealthMetric for %s", date_str)
    try:
        weather = get_daily_summary(db_session, entry.date)
    except Exception:
        logger.exception("Failed to query weather summary for %s", date_str)

    if health:
        lines.append("## Apple Watch Data")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        if health.hrv_mean is not None:
            hrv_std = health.hrv_std if health.hrv_std is not None else "N/A"
            lines.append(f"| HRV | {health.hrv_mean} ms (std {hrv_std}) |")
        if health.resting_hr is not None:
            lines.append(f"| Resting HR | {health.resting_hr} bpm |")
        if health.sleep_hours is not None:
            lines.append(f"| Sleep | {health.sleep_hours} hours |")
        if health.sleep_deep_min is not None:
            deep_pct = health.sleep_deep_pct if health.sleep_deep_pct is not None else "N/A"
            lines.append(
                f"| Deep sleep | {health.sleep_deep_min} min ({deep_pct}%) |"
            )
        if health.sleep_rem_min is not None:
            rem_pct = health.sleep_rem_pct if health.sleep_rem_pct is not None else "N/A"
            lines.append(
                f"| REM sleep | {health.sleep_rem_min} min ({rem_pct}%) |"
            )
        if health.sleep_core_min is not None:
            lines.append(f"| Core sleep | {health.sleep_core_min} min |")
        if health.sleep_awake_min is not None:
            lines.append(f"| Awake in bed | {health.sleep_awake_min} min |")
        if health.sleep_efficiency is not None:
            lines.append(f"| Sleep efficiency | {health.sleep_efficiency}% |")
        if health.sleep_start:
            lines.append(f"| Bedtime | {health.sleep_start} |")
        if health.sleep_end:
            lines.append(f"| Wake time | {health.sleep_end} |")
        if health.steps is not None:
            lines.append(f"| Steps | {health.steps} |")
        if health.spo2 is not None:
            lines.append(f"| SpO2 | {health.spo2}% |")
        if health.active_minutes is not None:
            lines.append(f"| Active energy | {health.active_minutes} kcal |")
        lines.append("")

    if weather:
        lines.append("## Weather (Luxembourg)")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(
            f"| Temperature | {weather.temp_min} - {weather.temp_max} C "
            f"(mean {weather.temp_mean}) |"
        )
        lines.append(f"| Pressure | {weather.pressure_mean} hPa |")
        if weather.pressure_delta_24h is not None:
            lines.append(
                f"| Pressure delta (24h) | {weather.pressure_delta_24h} hPa |"
            )
        lines.append(f"| Humidity | {weather.humidity_mean}% |")
        lines.append(f"| Readings | {weather.reading_count} |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "[[Projects/Health-Diagnostic/Symptoms-Master]] | "
        "[[Projects/Health-Diagnostic/CURRENT-HYPOTHESIS]]"
    )
    lines.append("")
    lines.append("---")
    lines.append("*Logged via health-tracker*")
    lines.append("")

    return "\n".join(lines)


def write_daily_file(
    db_session: Session,
    entry: Entry,
    photos: Optional[Sequence[Photo]] = None,
) -> None:
    if not settings.vault_path:
        return

    if photos is None:
        photos = []

    logs_dir = os.path.join(settings.vault_path, "Daily", "Health-Logs")
    try:
        os.makedirs(logs_dir, exist_ok=True)
    except OSError:
        logger.warning("Vault path not writable: %s", logs_dir)
        return

    content = _render_markdown(db_session, entry, photos)
    target_path = os.path.join(logs_dir, f"{entry.date.isoformat()}.md")

    fd, tmp_path = tempfile.mkstemp(dir=logs_dir, suffix=".md.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, target_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def delete_daily_file(date_str: str) -> None:
    if not settings.vault_path:
        return

    logs_dir = os.path.join(settings.vault_path, "Daily", "Health-Logs")
    target_path = os.path.join(logs_dir, f"{date_str}.md")
    if os.path.exists(target_path):
        os.unlink(target_path)
