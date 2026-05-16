from __future__ import annotations

# python -m app.embedding_pipeline
# Starts the embedding worker process.

import asyncio
import logging
import sys

from app.embedding_pipeline.worker import run


def _configure_logging() -> None:
    logging.basicConfig(
        format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "msg": "%(message)s"}',
        level=logging.INFO,
        stream=sys.stdout,
    )


def main() -> None:
    _configure_logging()
    asyncio.run(run())


if __name__ == "__main__":
    main()
