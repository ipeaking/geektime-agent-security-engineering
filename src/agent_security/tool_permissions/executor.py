"""将权限检查和下层委托绑定在同一个入口。"""

import json
from typing import Any, Protocol

from agent_security.models import ToolCall

from .models import (
    PermissionExecution,
    PermissionOutcome,
    SubjectContext,
    TaskContract,
)
from .policy import PermissionRequestBuilder, ToolPermissionPolicyEngine


class ToolDelegate(Protocol):
    def execute(self, tool_name: str, arguments: dict[str, Any]) -> object: ...


class RecordingToolDelegate:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> object:
        self.calls.append((tool_name, arguments))
        return {"recorded": True}


class PolicyEnforcedToolExecutor:
    def __init__(
        self,
        builder: PermissionRequestBuilder,
        policy_engine: ToolPermissionPolicyEngine,
        delegate: ToolDelegate,
    ) -> None:
        self._builder = builder
        self._policy_engine = policy_engine
        self._delegate = delegate

    def execute(
        self,
        call: ToolCall,
        subject: SubjectContext,
        task: TaskContract,
    ) -> PermissionExecution:
        request = self._builder.build(call, subject, task)
        decision = self._policy_engine.decide(request)
        delegated = decision.outcome is PermissionOutcome.ALLOW
        if delegated:
            arguments = json.loads(decision.request.arguments_json)
            self._delegate.execute(decision.request.tool_name, arguments)
        return PermissionExecution(decision, delegated)
