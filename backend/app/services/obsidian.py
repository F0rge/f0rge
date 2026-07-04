from __future__ import annotations

import datetime
import logging
import os
import tempfile
from typing import Optional, Sequence

from app.config import settings
from app.models.entry import Entry
from app.models.health_metrics import HealthMetric
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.models.treatment import Treatment
from app.schemas.weather import WeatherDailySummary
from app.services.diet_flags import (
    compute_effective_counts,
    compute_signal_from_analyses,
    parse_diet_risk_csv,
)

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

BRISTOL_LABELS = {
    1: "Type 1 - separate hard lumps",
    2: "Type 2 - lumpy sausage",
    3: "Type 3 - sausage with cracks",
    4: "Type 4 - smooth sausage (normal)",
    5: "Type 5 - soft blobs",
    6: "Type 6 - mushy / fluffy",
    7: "Type 7 - liquid",
}

STOOL_STATUS_LABELS = {
    "normal": "Normal",
    "abnormal": "Abnormal",
    "none": "No movement today",
}

FODMAP_ABBREV = {
    "oligos": "F:O",
    "fructose": "F:Fr",
    "polyols": "F:P",
    "lactose": "F:L",
}


def _format_active_treatments(
    treatments: list[Treatment],
    as_of: datetime.date,
) -> str:
    if not treatments:
        return "None"
    parts = []
    for t in treatments:
        day_num = (as_of - t.start_date).days + 1
        suffix = f"day {day_num}, {t.group_name}" if t.group_name else f"day {day_num}"
        parts.append(f"{t.name} ({suffix})")
    return ", ".join(parts)


def _format_ingredient(ing: PhotoIngredient) -> str:
    """Format a single ingredient with dietary annotations.

    FODMAP markers:
      - `high` levels emit the standard abbreviation (e.g. ``F:L``).
      - `moderate` levels emit a ``?`` suffix (e.g. ``F:L?``) to flag
        "be cautious — moderate, not high".
      - For a given FODMAP category, `high` takes precedence over
        `moderate` (we only emit one marker per category per ingredient).
    """
    parts: list[str] = []
    if ing.histamine_score is not None:
        parts.append(f"H:{ing.histamine_score}")
    if ing.contains_dairy:
        parts.append("Dairy")
    if ing.contains_gluten:
        parts.append("Gluten")
    for field, abbrev in FODMAP_ABBREV.items():
        val = getattr(ing, f"fodmap_{field}", None)
        if val == "high":
            parts.append(abbrev)
        elif val == "moderate":
            parts.append(f"{abbrev}?")
    annotation = f" ({', '.join(parts)})" if parts else ""
    return f"{ing.name}{annotation}"


def _dietary_flags_line(analysis: PhotoAnalysis) -> str:
    """Build the 'Dietary flags: ...' summary for an analysis.

    Only considers visible ingredients (those the user confirmed in the UI).
    Inferred/hidden ingredients (visible=false) are excluded so the vault
    matches what the user reviewed on screen.

    For each FODMAP category, `high` takes precedence over `moderate`:
    if any visible ingredient is `high`, emit the bare label
    (e.g. ``FODMAP-Lactose``). Otherwise, if any is `moderate`, emit
    a `(moderate)`-suffixed label (e.g. ``FODMAP-Lactose (moderate)``).
    """
    visible = [i for i in analysis.ingredients if i.visible]
    flags: list[str] = []
    max_h = max(
        (i.histamine_score for i in visible if i.histamine_score is not None),
        default=None,
    )
    if max_h is not None and max_h >= 1:
        flags.append(f"Histamine {max_h}")
    if any(i.contains_dairy for i in visible):
        flags.append("Dairy")
    if any(i.contains_gluten for i in visible):
        flags.append("Gluten")
    for field, label in (
        ("oligos", "FODMAP-Oligos"),
        ("fructose", "FODMAP-Fructose"),
        ("polyols", "FODMAP-Polyols"),
        ("lactose", "FODMAP-Lactose"),
    ):
        attr = f"fodmap_{field}"
        if any(getattr(i, attr, None) == "high" for i in visible):
            flags.append(label)
        elif any(getattr(i, attr, None) == "moderate" for i in visible):
            flags.append(f"{label} (moderate)")
    return f"Dietary flags: {', '.join(flags)}" if flags else ""


def _compute_dietary_tags(
    confirmed: list[PhotoAnalysis],
) -> tuple[dict[str, str], list[str]]:
    """Return (frontmatter_fields, extra_tags) from confirmed analyses.

    Only aggregates visible ingredients (those the user confirmed in the UI).
    Inferred/hidden ingredients (visible=false) are excluded so frontmatter
    fields and tags reflect exactly what the user reviewed on screen.
    """
    fm: dict[str, str] = {}
    tags: list[str] = []

    if not confirmed:
        return fm, tags

    fm["food-photos"] = str(len(confirmed))
    dishes = [a.dish_name for a in confirmed if a.dish_name]
    if dishes:
        fm["dishes"] = f'"{", ".join(dishes)}"'

    all_ingredients = [i for a in confirmed for i in a.ingredients if i.visible]

    max_h = max(
        (i.histamine_score for i in all_ingredients if i.histamine_score is not None),
        default=None,
    )
    if max_h is not None:
        fm["max-histamine"] = str(max_h)
        if max_h >= 1:
            tags.append(f"histamine-{max_h}")

    # For each FODMAP category, prefer `high` over `moderate` — never tag both.
    for field, high_tag, mod_tag in (
        ("oligos", "fodmap-high-oligos", "fodmap-moderate-oligos"),
        ("fructose", "fodmap-high-fructose", "fodmap-moderate-fructose"),
        ("polyols", "fodmap-high-polyols", "fodmap-moderate-polyols"),
        ("lactose", "fodmap-high-lactose", "fodmap-moderate-lactose"),
    ):
        attr = f"fodmap_{field}"
        if any(getattr(i, attr, None) == "high" for i in all_ingredients):
            tags.append(high_tag)
        elif any(getattr(i, attr, None) == "moderate" for i in all_ingredients):
            tags.append(mod_tag)

    if any(i.contains_gluten for i in all_ingredients):
        tags.append("contains-gluten")
    if any(i.contains_dairy for i in all_ingredients):
        tags.append("contains-dairy")

    return fm, tags


def _format_supplements(supplements_str: str) -> str:
    if not supplements_str:
        return "None"
    taken = [s.strip() for s in supplements_str.split(",") if s.strip()]
    labels = [SUPPLEMENT_LABELS.get(s, s) for s in taken]
    return ", ".join(labels) if labels else "None"


def _format_medications(medications: list[dict], med_labels: dict[str, str]) -> str:
    """Summary-table cell for logged medications.

    ``med_labels`` covers every catalog row (active and archived) so a
    historical entry referencing an archived medication still renders its
    label instead of falling back to the raw key.
    """
    if not medications:
        return "None"
    parts = []
    for med in medications:
        label = med_labels.get(med.get("key", ""), med.get("key", "?"))
        detail = med.get("dose") or ""
        if med.get("reason"):
            detail = f"{detail} for {med['reason']}" if detail else f"for {med['reason']}"
        parts.append(f"{label} ({detail})" if detail else label)
    return ", ".join(parts)


def _format_symptoms(
    filtered_symptoms: dict,
    active_sym_labels: dict,
) -> str:
    if not filtered_symptoms:
        return "None today"
    parts = [f"{active_sym_labels[k]} {v}/10" for k, v in sorted(filtered_symptoms.items())]
    return ", ".join(parts)


def _stool_summary(entry: Entry) -> str:
    status = getattr(entry, "stool_status", None)
    bristol = getattr(entry, "bristol_type", None)
    if status == "none":
        return "No movement today"
    if status == "normal":
        return "Normal"
    if status == "abnormal":
        if bristol is not None:
            return f"Abnormal ({BRISTOL_LABELS.get(bristol, f'Bristol {bristol}')})"
        if entry.stool_type:
            return f"Abnormal ({entry.stool_type})"
        return "Abnormal"
    # Fallback for v1 entries that pre-date stool_status.
    if entry.stool_normal is True:
        return "Normal"
    if entry.stool_normal is False:
        suffix = f" ({entry.stool_type})" if entry.stool_type else ""
        return f"Abnormal{suffix}"
    return "Unknown"


def _diet_provenance_lines(
    photo_flags: set[str],
    user_added: set[str],
) -> list[str]:
    """Build the ``diet-risk-provenance:`` YAML block for vault frontmatter.

    Iteration order is alphabetical for stable vault diffs.
    """
    effective = photo_flags | user_added
    if not effective:
        return []
    lines = ["diet-risk-provenance:"]
    for flag in sorted(effective):
        in_photos = flag in photo_flags
        in_manual = flag in user_added
        if in_photos and in_manual:
            provenance = "both"
        elif in_photos:
            provenance = "photos"
        else:
            provenance = "manual"
        lines.append(f"  - {flag}: {provenance}")
    return lines


def _render_markdown(
    entry: Entry,
    photos: Sequence[Photo],
    analyses: dict[int, PhotoAnalysis],
    active_sym_labels: dict[str, str],
    active_treatments: list[Treatment],
    health: Optional[HealthMetric],
    weather: Optional[WeatherDailySummary],
    med_labels: Optional[dict[str, str]] = None,
) -> str:
    """Render the Obsidian markdown file for one daily entry.

    All data is pre-fetched by the async caller and passed in as plain objects.
    This function performs NO database access — safe to run in a thread pool.
    """
    date_str = entry.date.isoformat()
    sick_str = "true" if entry.sick else "false"
    hot_shower_str = "true" if getattr(entry, "hot_shower", False) else "false"
    schema_version = getattr(entry, "schema_version", 1) or 1
    stool_status = getattr(entry, "stool_status", None)
    bristol_type = getattr(entry, "bristol_type", None)
    entry_time = getattr(entry, "entry_time", None)
    period_of_day = getattr(entry, "period_of_day", None)

    # Diet signal — compute from pre-fetched analyses, not entry.photos[*].analysis,
    # because the latter would trigger ORM lazy loads inside asyncio.to_thread and
    # raise MissingGreenlet. See obsidian_prefetch._fetch_obsidian_deps.
    _user_added_flags = parse_diet_risk_csv(getattr(entry, "diet_risk", None))
    _photo_signal = compute_signal_from_analyses(analyses.values())
    _effective_flags = sorted(_photo_signal.flags | _user_added_flags)
    _effective_str = ", ".join(_effective_flags) if _effective_flags else "normal"
    _eff_counts = compute_effective_counts(_photo_signal, _user_added_flags)

    dietary_fm, dietary_tags = _compute_dietary_tags(list(analyses.values()))

    # Symptoms: filter to active catalog keys only
    symptoms = getattr(entry, "symptoms_json", {}) or {}
    filtered_symptoms = {k: v for k, v in symptoms.items() if k in active_sym_labels}

    # Medications: NOT filtered to active catalog keys -- an archived medication
    # must still render correctly on historical entries that logged it.
    medications = getattr(entry, "medications_json", []) or []
    _med_labels = med_labels or {}

    tag_lines = [
        "tags:",
        "  - daily-check-in",
        "  - symptom-log",
    ]
    for t in dietary_tags:
        tag_lines.append(f"  - {t}")

    # Frontmatter — keep deterministic field order so vault diffs stay clean.
    lines = [
        "---",
        "created-by: health-tracker",
        f"created: {date_str}",
        "modified-by: health-tracker",
        f"modified: {date_str}",
        f"schema-version: {schema_version}",
        f"entry-time: {entry_time.isoformat() if entry_time else ''}",
        f"period-of-day: {period_of_day or ''}",
        *tag_lines,
        f"overall: {entry.overall}",
        f"bloating: {entry.bloating}",
        f"stool-status: {stool_status or ''}",
        f"bristol-type: {bristol_type if bristol_type is not None else ''}",
        f"stool-normal: {'' if entry.stool_normal is None else ('true' if entry.stool_normal else 'false')}",
        f"stool-type: {entry.stool_type or ''}",
        f"joint-pain: {entry.joint_pain}",
        f"neuro: {entry.neuro}",
        f"sleep-quality: {entry.sleep_quality}",
        f"stress: {entry.stress}",
        f"diet-risk: {_effective_str}",
        f"diet-histamine-load: {_eff_counts['histamine_load']}",
        f"diet-fodmap-count: {_eff_counts['fodmap_count']}",
        f"diet-gluten-count: {_eff_counts['gluten_count']}",
        f"diet-dairy-count: {_eff_counts['dairy_count']}",
        *_diet_provenance_lines(_photo_signal.flags, _user_added_flags),
        f"supplements: {entry.supplements}",
        # Symptom severity lines (sorted by key for stable vault diffs)
        *[f"sym-{k}: {v}" for k, v in sorted(filtered_symptoms.items())],
        f"symptoms-count: {len(filtered_symptoms)}",
        f"sick: {sick_str}",
        f"hot-shower: {hot_shower_str}",
    ]
    # Omit alcohol/caffeine keys entirely when zero or absent — cleaner vault diffs.
    alcohol_units = getattr(entry, "alcohol_units", None)
    caffeine_servings = getattr(entry, "caffeine_servings", None)
    if alcohol_units is not None and alcohol_units > 0:
        lines.append(f"alcohol-units: {alcohol_units}")
        lines.append("had-alcohol: true")
    if caffeine_servings is not None and caffeine_servings > 0:
        lines.append(f"caffeine-servings: {caffeine_servings}")
        lines.append("had-caffeine: true")
    lines.extend(
        [
            f"active-treatments: [{', '.join(t.normalized_name for t in active_treatments)}]",
        ]
    )
    for key, val in dietary_fm.items():
        lines.append(f"{key}: {val}")
    lines.extend(
        [
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
            f"| Stool | {_stool_summary(entry)} |",
            f"| Joint pain | {JOINT_PAIN_LABELS.get(entry.joint_pain, str(entry.joint_pain))} |",
            f"| Neuro | {NEURO_LABELS.get(entry.neuro, str(entry.neuro))} |",
            f"| Sleep quality | {SLEEP_LABELS.get(entry.sleep_quality, str(entry.sleep_quality))} |",
            f"| Stress | {STRESS_LABELS.get(entry.stress, str(entry.stress))} |",
            f"| Diet risk | {_effective_str} |",
            f"| Supplements | {_format_supplements(entry.supplements)} |",
            f"| Medications | {_format_medications(medications, _med_labels)} |",
            f"| Symptoms | {_format_symptoms(filtered_symptoms, active_sym_labels)} |",
            f"| Sick | {sick_str} |",
            f"| Hot shower (full body) | {hot_shower_str} |",
            f"| Active treatments | {_format_active_treatments(active_treatments, entry.date)} |",
            f"| Logged at | {entry_time.isoformat() if entry_time else 'unknown'} ({period_of_day or 'unknown'}) |",
        ]
    )
    # Omit alcohol/caffeine rows when zero or absent — same as frontmatter policy.
    if alcohol_units is not None and alcohol_units > 0:
        lines.append(f"| Alcohol | {alcohol_units} unit(s) |")
    if caffeine_servings is not None and caffeine_servings > 0:
        lines.append(f"| Caffeine | {caffeine_servings} serving(s) |")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            entry.notes if entry.notes else "No notes recorded.",
            "",
        ]
    )

    if medications:
        lines.append("## Medications")
        lines.append("")
        for med in medications:
            label = _med_labels.get(med.get("key", ""), med.get("key", "?"))
            detail_parts = []
            if med.get("dose"):
                detail_parts.append(med["dose"])
            if med.get("reason"):
                detail_parts.append(f"for {med['reason']}")
            detail = f" ({', '.join(detail_parts)})" if detail_parts else ""
            time_suffix = f" — {med['time']}" if med.get("time") else ""
            lines.append(f"- {label}{detail}{time_suffix}")
        lines.append("")

    if photos:
        lines.append("## Photos")
        lines.append("")
        for photo in photos:
            # Render meal_time as HH:MM (24-hour, local) inline with the embed.
            meal_time = getattr(photo, "meal_time", None)
            time_suffix = f" ({meal_time.strftime('%H:%M')})" if meal_time is not None else ""
            lines.append(f"![[attachments/{photo.filename}]]{time_suffix}")
            if photo.label:
                lines.append(f"*{photo.label}*")
            analysis = analyses.get(photo.id)
            if analysis:
                conf_pct = round(analysis.dish_confidence * 100) if analysis.dish_confidence else 0
                lines.append(f"**{analysis.dish_name}** ({conf_pct}%)")
                # Only render ingredients the user saw in the UI (visible=true).
                visible_ings = [i for i in analysis.ingredients if i.visible]
                if visible_ings:
                    ing_parts = [_format_ingredient(i) for i in visible_ings]
                    lines.append(f"Ingredients: {', '.join(ing_parts)}")
                flags_line = _dietary_flags_line(analysis)
                if flags_line:
                    lines.append(flags_line)
            lines.append("")

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
            lines.append(f"| Deep sleep | {health.sleep_deep_min} min ({deep_pct}%) |")
        if health.sleep_rem_min is not None:
            rem_pct = health.sleep_rem_pct if health.sleep_rem_pct is not None else "N/A"
            lines.append(f"| REM sleep | {health.sleep_rem_min} min ({rem_pct}%) |")
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
            lines.append(f"| Pressure delta (24h) | {weather.pressure_delta_24h} hPa |")
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
    entry: Entry,
    photos: Optional[Sequence[Photo]],
    analyses: dict[int, PhotoAnalysis],
    active_sym_labels: dict[str, str],
    active_treatments: list[Treatment],
    health: Optional[HealthMetric],
    weather: Optional[WeatherDailySummary],
    med_labels: Optional[dict[str, str]] = None,
) -> None:
    """Write/replace the Obsidian daily check-in file for the given entry.

    All data is passed in as pre-fetched plain objects — no DB access here.
    Safe to run in asyncio.to_thread().
    """
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

    content = _render_markdown(
        entry,
        photos,
        analyses,
        active_sym_labels,
        active_treatments,
        health,
        weather,
        med_labels=med_labels,
    )
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
