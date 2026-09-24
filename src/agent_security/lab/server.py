"""用于托管实验页面和接收诊断数据的本机回环 HTTP 服务。"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
from urllib.parse import unquote, urlparse


class LocalLabServer:
    def __init__(self, pages_root: Path) -> None:
        self.pages_root = pages_root.resolve()
        self.diagnostics: List[Dict[str, Any]] = []
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("lab server has not started")
        host, port = self._server.server_address[:2]
        return "http://%s:%s" % (host, port)

    def start(self) -> "LocalLabServer":
        handler = self._build_handler()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._server = None
        self._thread = None

    def __enter__(self) -> "LocalLabServer":
        return self.start()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.stop()

    def _build_handler(self) -> Type[BaseHTTPRequestHandler]:
        pages_root = self.pages_root
        diagnostics = self.diagnostics

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - 标准库处理器 API 的方法名
                route = unquote(urlparse(self.path).path)
                if not route.startswith("/pages/"):
                    self._send_json(404, {"error": "not found"})
                    return

                filename = route[len("/pages/") :]
                target = (pages_root / filename).resolve()
                try:
                    target.relative_to(pages_root)
                except ValueError:
                    self._send_json(400, {"error": "invalid page path"})
                    return

                if not target.is_file():
                    self._send_json(404, {"error": "page not found"})
                    return

                body = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self) -> None:  # noqa: N802 - 标准库处理器 API 的方法名
                if urlparse(self.path).path != "/diagnostic":
                    self._send_json(404, {"error": "not found"})
                    return

                length = int(self.headers.get("Content-Length", "0"))
                if length > 65_536:
                    self._send_json(413, {"error": "payload too large"})
                    return

                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._send_json(400, {"error": "invalid JSON"})
                    return

                diagnostics.append(payload)
                self._send_json(200, {"accepted": True})

            def log_message(self, format: str, *args: object) -> None:
                return

            def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler
