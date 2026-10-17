"""python -m buycycle_mcp — streamable HTTP on port 8097. Refuses to start without a token."""

from __future__ import annotations

import sys

from buycycle_mcp.server import build_runtime


def main() -> None:
    server, host, port = build_runtime()
    print(f"buycycle mcp listening on {host}:{port}/mcp", file=sys.stderr)
    server.run(transport="streamable-http", host=host, port=port, streamable_http_path="/mcp")


if __name__ == "__main__":
    main()
