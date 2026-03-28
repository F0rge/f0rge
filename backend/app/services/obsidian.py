from __future__ import annotations

import os
import tempfile
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.config import settings
from app.models.entry import Entry
from app.models.photo import Photo

OVERALL_LABELS = {
    1: "Very Poor",
    2: "Poor",
    3: "Standard",
    4: "Good",
    5: "Very Good",
}

BLOATING_LABELS = {0: "None", 1: "Mild", 2: "Moderate", 3: "Severe"}

JOINT_PAIN_LABELS = {0: "None", 1: "Mild", 2: "Moderate", 3: "Severe"}

NEURO_LABELS = {-1: "Worse than usual", 0: "Baseline", 1: "Better than usual"}

SLEEP_LABELS = {1: "Poor", 2: "OK", 3: "Good"}

STRESS_LABELS = {1: "Low", 2: "Medium", 3: "High"}


def _render_markdown(entry: Entry, photos: Sequence[Photo]) -> str:
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
        f"| Overall day | {OVERALL_LABELS.get(entry.overall, str(entry.overall))} ({entry.overall}/5) |",
        f"| Bloating | {BLOATING_LABELS.get(entry.bloating, str(entry.bloating))} |",
        f"| Stool | {'Normal' if entry.stool_normal else 'Abnormal'} |",
        f"| Joint pain | {JOINT_PAIN_LABELS.get(entry.joint_pain, str(entry.joint_pain))} |",
        f"| Neuro | {NEURO_LABELS.get(entry.neuro, str(entry.neuro))} |",
        f"| Sleep quality | {SLEEP_LABELS.get(entry.sleep_quality, str(entry.sleep_quality))} |",
        f"| Stress | {STRESS_LABELS.get(entry.stress, str(entry.stress))} |",
        f"| Diet risk | {entry.diet_risk} |",
        f"| Supplements | {entry.supplements} |",
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

    lines.append("---")
    lines.append("")
    lines.append("[[02-Symptoms/Symptoms-Master]] | [[CURRENT-HYPOTHESIS]]")
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
    if photos is None:
        photos = []

    logs_dir = os.path.join(settings.vault_path, "02-Symptoms", "Logs")
    os.makedirs(logs_dir, exist_ok=True)

    content = _render_markdown(entry, photos)
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
    logs_dir = os.path.join(settings.vault_path, "02-Symptoms", "Logs")
    target_path = os.path.join(logs_dir, f"{date_str}.md")
    if os.path.exists(target_path):
        os.unlink(target_path)
