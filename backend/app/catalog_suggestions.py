from __future__ import annotations

from app.seed_data import (
    DEFAULT_MEDICATIONS,
    DEFAULT_SYMPTOMS,
    DEFAULT_SUPPLEMENTS,
    DEFAULT_TRACKERS,
    SPLIT_VITAMIN_D_K2,
)


def curated_supplements() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for key, label in DEFAULT_SUPPLEMENTS:
        if key == "vitamin_d_k2":
            continue
        rows.append((key, label))
    rows.extend(SPLIT_VITAMIN_D_K2)
    return rows


def supplement_allowlist() -> frozenset[str]:
    return frozenset(key for key, _ in curated_supplements())


def medication_allowlist() -> frozenset[str]:
    return frozenset(key for key, _ in DEFAULT_MEDICATIONS)


def symptom_allowlist() -> frozenset[str]:
    return frozenset(key for key, _ in DEFAULT_SYMPTOMS)


def tracker_allowlist() -> frozenset[str]:
    return frozenset(name for name, *_ in DEFAULT_TRACKERS)


def tracker_seed_by_name() -> dict[str, tuple[str, str, str | None, int]]:
    return {
        name: (kind, icon, unit, position) for name, kind, icon, unit, position in DEFAULT_TRACKERS
    }


def key_label_rows(items: list[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"key": key, "label": label} for key, label in items]


def tracker_suggestion_rows() -> list[dict[str, str | None]]:
    return [
        {
            "name": name,
            "kind": kind,
            "icon": icon,
            "unit": unit,
        }
        for name, kind, icon, unit, _position in DEFAULT_TRACKERS
    ]
