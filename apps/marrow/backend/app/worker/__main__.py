from __future__ import annotations

# python -m app.worker
# Runs embedding + meal-analysis workers in one process (Fly worker process).

import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable

from app.embedding_pipeline.worker import run as run_embedding
from app.meal_analysis_pipeline.worker import run as run_meal_analysis

logger = logging.getLogger(__name__)

_RESTART_DELAY_SECONDS = 5.0


def _configure_logging() -> None:
    logging.basicConfig(
        format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "msg": "%(message)s"}',
        level=logging.INFO,
        stream=sys.stdout,
    )


async def _run_supervised(name: str, coro_factory: Callable[[], Awaitable[None]]) -> None:
    """Run a worker loop forever; restart after unexpected exit/crash."""
    while True:
        try:
            await coro_factory()
            logger.error({"event": "worker_loop_exited", "worker": name})
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception({"event": "worker_loop_crashed", "worker": name})
        await asyncio.sleep(_RESTART_DELAY_SECONDS)


async def run_all() -> None:
    await asyncio.gather(
        _run_supervised("embedding", run_embedding),
        _run_supervised("meal_analysis", run_meal_analysis),
    )


def main() -> None:
    _configure_logging()
    asyncio.run(run_all())


if __name__ == "__main__":
    main()
