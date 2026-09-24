"""实验 Agent 使用的 HTTP 页面读取工具。"""

from typing import Any, Dict
from urllib.request import Request, urlopen

from .base import Tool


class FetchWebpageTool(Tool):
    name = "fetch_webpage"
    description = "Fetch an HTTP page and return its content."

    def __init__(self, timeout_seconds: float = 2.0, max_bytes: int = 262_144) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes

    def execute(self, **arguments: Any) -> Dict[str, Any]:
        url = str(arguments["url"])
        request = Request(url, headers={"User-Agent": "agent-security-course-lab/0.1"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read(self.max_bytes + 1)
            if len(body) > self.max_bytes:
                raise ValueError("page exceeds the lab size limit")
            charset = response.headers.get_content_charset() or "utf-8"
            return {
                "url": response.geturl(),
                "status": response.status,
                "content_type": response.headers.get_content_type(),
                "body": body.decode(charset, errors="replace"),
            }
