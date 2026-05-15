"""Orchestrator: seed the dietary reference database in correct order."""

from __future__ import annotations

import logging
import time

from scripts.load_sighi import load as load_sighi
from scripts.load_fodmap import load as load_fodmap
from scripts.load_allergens import load as load_allergens
from scripts.build_aliases import load as load_aliases

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    start = time.monotonic()
    log.info("=== Starting dietary database seed ===")

    log.info("--- Step 1/4: SIGHI histamine data ---")
    load_sighi()

    log.info("--- Step 2/4: FODMAP data ---")
    load_fodmap()

    log.info("--- Step 3/4: Allergen flags ---")
    load_allergens()

    log.info("--- Step 4/4: Ingredient aliases ---")
    load_aliases()

    elapsed = time.monotonic() - start
    log.info("=== Dietary database seed complete in %.1fs ===", elapsed)


if __name__ == "__main__":
    main()
