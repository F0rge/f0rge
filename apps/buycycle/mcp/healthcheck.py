"""Process is healthy when /mcp answers 401 (auth is on and the port is open)."""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request


def main() -> None:
    port = os.environ.get("BUYCYCLE_MCP_PORT", "8097")
    url = f"http://127.0.0.1:{port}/mcp"
    try:
        urllib.request.urlopen(url, timeout=4)
    except urllib.error.HTTPError as exc:
        sys.exit(0 if exc.code == 401 else 1)
    except Exception:
        sys.exit(1)
    sys.exit(1)


if __name__ == "__main__":
    main()
