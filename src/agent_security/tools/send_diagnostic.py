"""把数据发送到实验使用的本地诊断接收器。"""

import json
from typing import Any, Dict
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .base import Tool


class SendDiagnosticTool(Tool):
    name = "send_diagnostic"
    description = "Submit diagnostic information to the configured collector."

    def __init__(self, endpoint: str, timeout_seconds: float = 2.0) -> None:
        parsed = urlparse(endpoint)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("the teaching collector must use local loopback HTTP")
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def execute(self, **arguments: Any) -> Dict[str, Any]:
        payload = arguments["payload"]
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.endpoint,
            data=encoded,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            response_body = response.read(65_536).decode("utf-8", errors="replace")
            return {
                "destination": self.endpoint,
                "status": response.status,
                "response": json.loads(response_body),
            }
