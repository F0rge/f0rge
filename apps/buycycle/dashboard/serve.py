#!/usr/bin/env python3
"""Static server for the dashboards: serves precompressed .gz siblings when the client accepts gzip; short cache for data, long for vendor assets."""

import http.server
import os
import sys


class H(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            path = os.path.join(path, "index.html")
        gz = path + ".gz"
        if (
            "gzip" in self.headers.get("Accept-Encoding", "")
            and os.path.isfile(gz)
            and os.path.isfile(path)
            and os.path.getmtime(gz) >= os.path.getmtime(path) - 5
        ):
            f = open(gz, "rb")
            st = os.fstat(f.fileno())
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(st.st_size))
            self.send_header("Vary", "Accept-Encoding")
            self._cache(path)
            self.end_headers()
            return f
        return super().send_head()

    def end_headers(self):
        if not getattr(self, "_c", False):
            self._cache(self.translate_path(self.path))
        super().end_headers()

    def _cache(self, path):
        self._c = True
        self.send_header("Cache-Control", "public, max-age=604800" if "/vendor/" in self.path else "no-cache")

    def log_message(self, *a):
        pass


port, d = int(sys.argv[1]), sys.argv[2]
http.server.ThreadingHTTPServer(("0.0.0.0", port), lambda *a, **k: H(*a, directory=d, **k)).serve_forever()
