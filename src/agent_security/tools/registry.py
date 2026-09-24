"""工具注册，以及故意缺少安全防护的执行逻辑。"""

from typing import Dict

from agent_security.audit import AuditLogger
from agent_security.models import ToolCall, ToolResult

from .base import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError("tool already registered: %s" % tool.name)
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as error:
            raise KeyError("unknown tool: %s" % name) from error


class ToolExecutor:
    """不经过授权判断，直接执行模型提出的每个动作。

    这种行为是课程故意保留的漏洞，也是后续 Policy Engine
    课程将要修改的主要安全边界。
    """

    def __init__(self, registry: ToolRegistry, audit: AuditLogger) -> None:
        self.registry = registry
        self.audit = audit

    def execute(self, call: ToolCall) -> ToolResult:
        self.audit.record(
            "tool.proposed",
            call_id=call.call_id,
            tool=call.name,
            arguments=call.arguments,
            reason=call.reason,
        )

        tool = self.registry.get(call.name)
        try:
            output = tool.execute(**call.arguments)
            result = ToolResult(
                call_id=call.call_id,
                tool_name=call.name,
                success=True,
                output=output,
            )
            self.audit.record(
                "tool.completed",
                call_id=call.call_id,
                tool=call.name,
                success=True,
                output=output,
            )
            return result
        except Exception as error:  # 执行失败也必须保留在审计轨迹中。
            result = ToolResult(
                call_id=call.call_id,
                tool_name=call.name,
                success=False,
                error=str(error),
            )
            self.audit.record(
                "tool.completed",
                call_id=call.call_id,
                tool=call.name,
                success=False,
                error=str(error),
            )
            return result
