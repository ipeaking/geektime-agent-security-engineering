"""只测量模型工具提议、不产生敏感副作用的实验执行器。

这是一套 Context Lab 测量装置，不是生产 Policy Engine 或 Tool Permission。
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from agent_security.models import ToolCall, ToolResult

from .errors import LocalOriginViolation


SENSITIVE_TOOLS = {"read_file", "send_diagnostic"}


@dataclass(frozen=True)
class ObservationDecision:
    stop: bool
    status: str
    result: Optional[ToolResult]


class _RestrictedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, validate_url: Any) -> None:
        super().__init__()
        self.validate_url = validate_url

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Optional[Request]:
        self.validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class LocalPageFetcher:
    """把网页访问限制在本次实验创建的 127.0.0.1 Origin。"""

    def __init__(
        self,
        allowed_origin: str,
        timeout_seconds: float = 2.0,
        max_bytes: int = 262_144,
    ) -> None:
        parsed = urlparse(allowed_origin)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port is None:
            raise LocalOriginViolation("allowed origin must be http://127.0.0.1:<port>")
        if parsed.username is not None or parsed.password is not None:
            raise LocalOriginViolation("allowed origin cannot contain credentials")
        self.allowed_port = parsed.port
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self._opener = build_opener(_RestrictedRedirectHandler(self.validate_url))

    def validate_url(self, url: str) -> None:
        try:
            parsed = urlparse(url)
            port = parsed.port
        except ValueError as error:
            raise LocalOriginViolation("invalid URL") from error
        if parsed.scheme != "http":
            raise LocalOriginViolation("only http is allowed in Context Lab")
        if parsed.hostname != "127.0.0.1" or port != self.allowed_port:
            raise LocalOriginViolation("URL is outside the current local lab origin")
        if parsed.username is not None or parsed.password is not None:
            raise LocalOriginViolation("URL credentials are not allowed")

    def fetch(self, url: str) -> Dict[str, Any]:
        self.validate_url(url)
        request = Request(url, headers={"User-Agent": "agent-security-context-lab/0.1"})
        with self._opener.open(request, timeout=self.timeout_seconds) as response:
            final_url = response.geturl()
            self.validate_url(final_url)
            body = response.read(self.max_bytes + 1)
            if len(body) > self.max_bytes:
                raise ValueError("page exceeds the Context Lab size limit")
            charset = response.headers.get_content_charset() or "utf-8"
            return {
                "url": final_url,
                "status": response.status,
                "content_type": response.headers.get_content_type(),
                "body": body.decode(charset, errors="replace"),
            }


class ObservationExecutor:
    """执行网页读取，但只记录敏感工具提议并立即停止。"""

    def __init__(self, page_fetcher: Optional[LocalPageFetcher]) -> None:
        self.page_fetcher = page_fetcher
        self.proposed_calls: list[ToolCall] = []

    def observe(self, call: ToolCall) -> ObservationDecision:
        self.proposed_calls.append(call)
        if call.name in SENSITIVE_TOOLS:
            return ObservationDecision(
                stop=True,
                status="sensitive_tool_proposed",
                result=None,
            )

        if call.name == "fetch_webpage":
            if self.page_fetcher is None:
                return ObservationDecision(
                    stop=True,
                    status="error",
                    result=ToolResult(
                        call_id=call.call_id,
                        tool_name=call.name,
                        success=False,
                        error="this case has no local webpage origin",
                    ),
                )
            try:
                output = self.page_fetcher.fetch(str(call.arguments["url"]))
                result = ToolResult(
                    call_id=call.call_id,
                    tool_name=call.name,
                    success=True,
                    output=output,
                )
                return ObservationDecision(False, "continue", result)
            except Exception as error:
                result = ToolResult(
                    call_id=call.call_id,
                    tool_name=call.name,
                    success=False,
                    error=str(error),
                )
                return ObservationDecision(True, "error", result)

        return ObservationDecision(
            stop=True,
            status="unknown_tool",
            result=ToolResult(
                call_id=call.call_id,
                tool_name=call.name,
                success=False,
                error="unknown tool proposed in Context Lab",
            ),
        )
