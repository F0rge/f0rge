from __future__ import annotations

# python -m app.worker
# Fly worker process — embedding pipeline (meal analysis is Airflow-orchestrated).

import asyncio
import logging
import sys

from app.embedding_pipeline.worker import run as run_embedding


def _configure_logging() -> None:
    logging.basicConfig(
        format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "msg": "%(message)s"}',
        level=logging.INFO,
        stream=sys.stdout,
    )


def main() -> None:
    _configure_logging()
    asyncio.run(run_embedding())


if __name__ == "__main__":
    main()
