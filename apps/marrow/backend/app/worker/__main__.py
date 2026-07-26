from __future__ import annotations

# python -m app.worker
# Runs embedding + meal-analysis workers in one process (Fly worker process).

import asyncio
import logging
import sys

from app.embedding_pipeline.worker import run as run_embedding
from app.meal_analysis_pipeline.worker import run as run_meal_analysis


def _configure_logging() -> None:
    logging.basicConfig(
        format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "msg": "%(message)s"}',
        level=logging.INFO,
        stream=sys.stdout,
    )


async def run_all() -> None:
    await asyncio.gather(run_embedding(), run_meal_analysis())


def main() -> None:
    _configure_logging()
    asyncio.run(run_all())


if __name__ == "__main__":
    main()
