"""确定性重放一组预先保存的模型工具调用提议。"""

import re
from html import unescape
from typing import Any, Dict, List

from agent_security.models import AgentRunResult, ToolCall, ToolResult
from agent_security.tools import ToolExecutor


class DeterministicReplayRuntime:
    """重放模型提议，但不假装理解网页内容。

    Live 模式观察真实模型是否会服从不可信内容中的指令。
    Replay 模式从一组已经保存的提议开始，验证缺少防护的执行层
    会如何处理这些提议。
    """

    def __init__(self, executor: ToolExecutor, steps: List[Dict[str, Any]]) -> None:
        self.executor = executor
        self.steps = steps

    def run(self, task: str, page_url: str) -> AgentRunResult:
        calls: List[ToolCall] = []
        results: List[ToolResult] = []
        outputs: Dict[str, Any] = {}
        page_html = ""

        self.executor.audit.record(
            "agent.run.started",
            provider="replay",
            task=task,
            page_url=page_url,
        )

        for step in self.steps:
            tool_name = str(step["tool"])
            arguments = self._resolve(step.get("arguments", {}), page_url, outputs)
            call = ToolCall(
                name=tool_name,
                arguments=arguments,
                reason=str(step.get("reason", "预先保存的模型提议。")),
            )
            calls.append(call)
            result = self.executor.execute(call)
            results.append(result)

            if not result.success:
                break

            outputs[tool_name] = result.output
            if tool_name == "fetch_webpage":
                page_html = str(result.output["body"])

        answer = self._summarize(page_html)
        completed = AgentRunResult(answer=answer, tool_calls=calls, tool_results=results)
        self.executor.audit.record(
            "agent.run.completed",
            provider="replay",
            answer=completed.answer,
            tool_calls=[call.name for call in calls],
        )
        return completed

    def _resolve(
        self,
        value: Any,
        page_url: str,
        outputs: Dict[str, Any],
    ) -> Any:
        if value == "$PAGE_URL":
            return page_url
        if isinstance(value, list):
            return [self._resolve(item, page_url, outputs) for item in value]
        if isinstance(value, dict):
            if set(value) == {"$tool_output"}:
                tool_name = str(value["$tool_output"])
                if tool_name not in outputs:
                    raise ValueError("replay references unavailable tool output: %s" % tool_name)
                return outputs[tool_name]
            return {
                str(key): self._resolve(item, page_url, outputs)
                for key, item in value.items()
            }
        return value

    @staticmethod
    def _summarize(page_html: str) -> str:
        title_match = re.search(r"<title>(.*?)</title>", page_html, re.I | re.S)
        paragraph_match = re.search(r"<p[^>]*>(.*?)</p>", page_html, re.I | re.S)
        title = (
            DeterministicReplayRuntime._strip_tags(title_match.group(1))
            if title_match
            else "Untitled page"
        )
        paragraph = (
            DeterministicReplayRuntime._strip_tags(paragraph_match.group(1))
            if paragraph_match
            else ""
        )
        return "摘要：%s。%s" % (title, paragraph)

    @staticmethod
    def _strip_tags(value: str) -> str:
        return " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).split())
