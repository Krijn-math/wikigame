#!/usr/bin/env python3
"""
Static file server with one extra endpoint:
  POST /save-schedule   body: { "file": "march_2026_schedule.json", "data": {...} }
  → writes to data/schedule/<file>

Usage:
  python server.py          # serves on http://localhost:8000
  python server.py 9000     # custom port
"""

import hashlib
import json
import re
import sys
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path

SCHEDULE_DIR = Path("data/schedule")
ADMINS_FILE  = Path("admins.txt")
ALLOWED_PATTERN = r"^[a-z]+_\d{4}_schedule\.json$"


def check_credentials(username: str, password: str) -> bool:
    if not ADMINS_FILE.exists():
        return False
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    for line in ADMINS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(":", 1)
        if len(parts) == 2 and parts[0] == username and parts[1] == pw_hash:
            return True
    return False


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/login":
            self._handle_login()
            return
        if self.path != "/save-schedule":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            payload = json.loads(body)
            filename = payload["file"]
            data     = payload["data"]
        except (json.JSONDecodeError, KeyError):
            self.send_error(400, "Bad request")
            return

        if not re.match(ALLOWED_PATTERN, filename):
            self.send_error(400, "Invalid filename")
            return

        dest = SCHEDULE_DIR / filename
        dest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  Saved {dest}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def _handle_login(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length))
            username = payload["username"]
            password = payload["password"]
        except (json.JSONDecodeError, KeyError):
            self.send_error(400, "Bad request")
            return

        if check_credentials(username, password):
            self._json_response(200, {"ok": True})
        else:
            self._json_response(401, {"ok": False})

    def _json_response(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, fmt, *args):
        # Suppress noisy GET logs, keep POST logs
        if args and str(args[0]).startswith("POST"):
            super().log_message(fmt, *args)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"Serving on http://localhost:{port}")
    HTTPServer(("", port), Handler).serve_forever()
