from __future__ import annotations

# python -m app.mcp --transport stdio
# python -m app.mcp --transport streamable-http --host 0.0.0.0 --port 8005

import argparse
import asyncio
import logging
import sys

from app.mcp.server import create_server
from app.mcp.tools import register_tools


def _configure_logging() -> None:
    logging.basicConfig(
        format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "msg": "%(message)s"}',
        level=logging.INFO,
        stream=sys.stdout,
    )


async def _run(transport: str) -> None:
    server = create_server(transport=transport)
    register_tools(server)
    if transport == "stdio":
        await server.run_stdio_async()
    else:
        await server.run_streamable_http_async()


def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(description="Health Tracker MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport to use (default: stdio)",
    )
    # --host and --port are accepted but ignored — bind address comes from
    # MCP_SERVER_HOST / MCP_SERVER_PORT env vars (read by app.config.settings).
    # Keeping the flags so the documented `docker-compose` command stays valid
    # and so CLI invocations don't have to set env vars.
    parser.add_argument("--host", help="(ignored; use MCP_SERVER_HOST)")
    parser.add_argument("--port", type=int, help="(ignored; use MCP_SERVER_PORT)")
    args = parser.parse_args()
    asyncio.run(_run(args.transport))


if __name__ == "__main__":
    main()
