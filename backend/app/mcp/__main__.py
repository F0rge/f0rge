from __future__ import annotations

# python -m app.mcp --transport streamable-http --host 0.0.0.0 --port 8005

import argparse
import asyncio
import logging
import sys

from app.mcp.server import create_server
from app.mcp.tools import register_tools


def _configure_logging() -> None:
    # Log to stderr, keeping stdout free — still correct practice for an MCP
    # server even with a single HTTP transport, since nothing should ever mix
    # log lines into a JSON-RPC or SSE stream.
    logging.basicConfig(
        format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "msg": "%(message)s"}',
        level=logging.INFO,
        stream=sys.stderr,
    )


async def _run() -> None:
    server = create_server()
    register_tools(server)
    await server.run_streamable_http_async()


def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(description="Marrow MCP server")
    parser.add_argument(
        "--transport",
        choices=["streamable-http"],
        default="streamable-http",
        help="Transport to use (default and only supported: streamable-http)",
    )
    # --host and --port are accepted but ignored — bind address comes from
    # MCP_SERVER_HOST / MCP_SERVER_PORT env vars (read by app.config.settings).
    # Keeping the flags so the documented `docker-compose` command stays valid
    # and so CLI invocations don't have to set env vars.
    parser.add_argument("--host", help="(ignored; use MCP_SERVER_HOST)")
    parser.add_argument("--port", type=int, help="(ignored; use MCP_SERVER_PORT)")
    parser.parse_args()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
