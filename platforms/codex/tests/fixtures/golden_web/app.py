"""Local-only frontend/API/SQLite fixture for Full Team integration tests."""

from __future__ import annotations

from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import threading
from typing import Optional, Type


MAX_BODY = 4096
MAX_EMAIL_LENGTH = 254


def is_valid_email(value: str) -> bool:
    """Validate the fixture email in bounded linear time."""

    if not 3 <= len(value) <= MAX_EMAIL_LENGTH:
        return False
    if any(character.isspace() for character in value):
        return False
    local, separator, domain = value.partition("@")
    if not separator or not local or "@" in domain:
        return False
    dot = domain.find(".", 1)
    return dot != -1 and dot < len(domain) - 1


class GoldenWebApp:
    def __init__(self, runtime_root: Path):
        self.runtime_root = runtime_root
        self.database = runtime_root / "golden.sqlite3"
        self.server: Optional[ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def __enter__(self) -> "GoldenWebApp":
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS users ("
                "id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE)"
            )
            connection.commit()
        handler = self._handler()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=5)

    @property
    def base_url(self) -> str:
        if self.server is None:
            raise RuntimeError("fixture is not running")
        return "http://127.0.0.1:%d" % self.server.server_address[1]

    def count_users(self) -> int:
        with closing(sqlite3.connect(self.database)) as connection:
            row = connection.execute("SELECT COUNT(*) FROM users").fetchone()
        return int(row[0])

    def _handler(self) -> Type[BaseHTTPRequestHandler]:
        database = self.database
        index = Path(__file__).with_name("index.html")
        script = Path(__file__).with_name("app.js")

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:
                return

            def security_headers(self) -> None:
                self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Cache-Control", "no-store")

            def respond(self, status: int, payload: bytes, content_type: str) -> None:
                self.send_response(status)
                self.security_headers()
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def json_response(self, status: int, payload: dict) -> None:
                self.respond(
                    status,
                    json.dumps(payload, sort_keys=True).encode("utf-8"),
                    "application/json; charset=utf-8",
                )

            def do_GET(self) -> None:
                if self.path == "/":
                    self.respond(200, index.read_bytes(), "text/html; charset=utf-8")
                elif self.path == "/app.js":
                    self.respond(
                        200, script.read_bytes(), "text/javascript; charset=utf-8"
                    )
                elif self.path == "/api/health":
                    self.json_response(200, {"status": "ok"})
                else:
                    self.json_response(404, {"message": "Not found"})

            def do_POST(self) -> None:
                if self.path != "/api/signup":
                    self.json_response(404, {"message": "Not found"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = -1
                if length < 1 or length > MAX_BODY:
                    self.json_response(413, {"message": "Invalid request size"})
                    return
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self.json_response(400, {"message": "Invalid JSON"})
                    return
                email = payload.get("email") if isinstance(payload, dict) else None
                if not isinstance(email, str) or not is_valid_email(email):
                    self.json_response(400, {"message": "Enter a valid email"})
                    return
                try:
                    with closing(sqlite3.connect(database)) as connection:
                        connection.execute(
                            "INSERT INTO users(email) VALUES (?)", (email.lower(),)
                        )
                        connection.commit()
                except sqlite3.IntegrityError:
                    self.json_response(409, {"message": "Account already exists"})
                    return
                self.json_response(201, {"message": "Account created"})

        return Handler
