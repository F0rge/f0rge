"""Stale classify_meal callbacks are skips, not task failures.

A retry used to delete the photo_analyses row. Runs that still held that id
got 404 from complete/fail and the DAG failed. Missing rows now return 410;
404 stays a skip so DAGs deployed before that change also stop failing.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SUPERSEDED_STATUS_CODES = frozenset({410, 404})
_CALLBACK_SUFFIXES = ("/complete", "/fail")


def raise_if_superseded(status_code: int, path: str, detail: str = "") -> None:
    """Raise AirflowSkipException when complete/fail target a gone analysis."""
    if status_code not in SUPERSEDED_STATUS_CODES or not path.endswith(_CALLBACK_SUFFIXES):
        return
    logger.info(
        "Marrow %s returned %s; skipping superseded meal analysis. %s",
        path,
        status_code,
        detail,
    )
    from airflow.exceptions import AirflowSkipException

    raise AirflowSkipException(f"meal analysis superseded ({status_code})")
