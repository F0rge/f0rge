from __future__ import annotations

from app.seed_data import (
    BULK_MEDICATIONS,
    BULK_SUPPLEMENTS,
    BULK_SYMPTOMS,
    BULK_TRACKERS,
    DEFAULT_MEDICATIONS,
    DEFAULT_SYMPTOMS,
    DEFAULT_SUPPLEMENTS,
    DEFAULT_TRACKERS,
    SPLIT_VITAMIN_D_K2,
)

_LEGACY_SEED_TRACKER_NAMES = frozenset(name for name, *_ in DEFAULT_TRACKERS)


def curated_supplements() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for key, label in DEFAULT_SUPPLEMENTS:
        if key == "vitamin_d_k2":
            continue
        rows.append((key, label))
    rows.extend(SPLIT_VITAMIN_D_K2)
    return rows


def _labels_by_key(*item_lists: list[tuple[str, str]]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for items in item_lists:
        for key, label in items:
            labels[key] = label
    return labels


def supplement_allowlist() -> frozenset[str]:
    return frozenset(_labels_by_key(curated_supplements(), BULK_SUPPLEMENTS))


def medication_allowlist() -> frozenset[str]:
    return frozenset(_labels_by_key(DEFAULT_MEDICATIONS, BULK_MEDICATIONS))


def symptom_allowlist() -> frozenset[str]:
    return frozenset(_labels_by_key(DEFAULT_SYMPTOMS, BULK_SYMPTOMS))


def tracker_allowlist() -> frozenset[str]:
    names = [name for name, *_ in DEFAULT_TRACKERS]
    names.extend(name for name, *_ in BULK_TRACKERS)
    return frozenset(names)


def supplement_labels_by_key() -> dict[str, str]:
    return _labels_by_key(curated_supplements(), BULK_SUPPLEMENTS)


def medication_labels_by_key() -> dict[str, str]:
    return _labels_by_key(DEFAULT_MEDICATIONS, BULK_MEDICATIONS)


def symptom_labels_by_key() -> dict[str, str]:
    return _labels_by_key(DEFAULT_SYMPTOMS, BULK_SYMPTOMS)


def tracker_seed_by_name() -> dict[str, tuple[str, str, str | None, int]]:
    rows = list(DEFAULT_TRACKERS) + list(BULK_TRACKERS)
    return {name: (kind, icon, unit, position) for name, kind, icon, unit, position in rows}


def is_legacy_seed_tracker(name: str) -> bool:
    return name in _LEGACY_SEED_TRACKER_NAMES


def key_label_rows(items: list[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"key": key, "label": label} for key, label in items]


def tracker_suggestion_rows() -> list[dict[str, str | None]]:
    return _tracker_rows_from(DEFAULT_TRACKERS)


def bulk_tracker_suggestion_rows() -> list[dict[str, str | None]]:
    return _tracker_rows_from(BULK_TRACKERS)


def _tracker_rows_from(
    trackers: list[tuple[str, str, str, str | None, int]],
) -> list[dict[str, str | None]]:
    return [
        {
            "name": name,
            "kind": kind,
            "icon": icon,
            "unit": unit,
        }
        for name, kind, icon, unit, _position in trackers
    ]
