"""默认拒绝、固定顺序的 Tool Permission Policy。"""

import json
from typing import Any

from agent_security.models import ToolCall

from .models import (
    CheckStatus,
    PermissionDecision,
    PermissionOutcome,
    PermissionPolicy,
    PermissionRequest,
    PolicyCheck,
    SubjectContext,
    TaskContract,
    ToolManifest,
)


class PermissionRequestBuilder:
    def __init__(self, tools: tuple[ToolManifest, ...]) -> None:
        self._tools = {item.name: item for item in tools}

    def build(
        self,
        call: ToolCall,
        subject: SubjectContext,
        task: TaskContract,
    ) -> PermissionRequest:
        manifest = self._tools.get(call.name)
        arguments_json = json.dumps(
            call.arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        error = None if manifest is None else _validate_arguments(manifest, call.arguments)
        return PermissionRequest(
            tool_name=call.name,
            manifest=manifest,
            subject=subject,
            task=task,
            arguments_json=arguments_json,
            validation_error=error,
        )


class ToolPermissionPolicyEngine:
    def __init__(self, policy: PermissionPolicy) -> None:
        self._policy = policy

    def decide(self, request: PermissionRequest) -> PermissionDecision:
        checks: list[PolicyCheck] = []
        failure: str | None = None
        for name in self._policy.check_order:
            if failure is not None:
                checks.append(PolicyCheck(name, CheckStatus.NOT_RUN, "earlier_check_denied"))
                continue
            reason = self._evaluate(name, request)
            if reason is None:
                checks.append(PolicyCheck(name, CheckStatus.SATISFIED, "check_satisfied"))
            else:
                checks.append(PolicyCheck(name, CheckStatus.UNSATISFIED, reason))
                failure = reason
        return PermissionDecision(
            outcome=PermissionOutcome.DENY if failure else PermissionOutcome.ALLOW,
            reason_code=failure or "all_required_checks_satisfied",
            request=request,
            checks=tuple(checks),
        )

    def _evaluate(self, name: str, request: PermissionRequest) -> str | None:
        if name == "request_valid":
            return request.validation_error
        if name == "tool_registered":
            return None if request.manifest is not None else "tool_not_registered"
        if name == "subject_role_allowed":
            return (
                None
                if set(request.subject.roles) & set(request.task.allowed_roles)
                else "subject_role_not_allowed"
            )
        if name == "tool_allowed_by_task":
            return (
                None
                if request.tool_name in request.task.allowed_tools
                else "tool_not_allowed_by_task"
            )
        if name == "capabilities_allowed_by_task":
            if request.manifest is None:
                raise AssertionError("registered tool check must run first")
            return (
                None
                if set(request.manifest.capabilities) <= set(request.task.allowed_capabilities)
                else "capabilities_not_allowed_by_task"
            )
        raise AssertionError("unknown policy check: " + name)


def _validate_arguments(manifest: ToolManifest, arguments: dict[str, Any]) -> str | None:
    allowed = set(manifest.required_arguments) | set(manifest.optional_arguments)
    if not set(manifest.required_arguments) <= set(arguments):
        return "missing_required_arguments"
    if not set(arguments) <= allowed:
        return "unexpected_arguments"
    type_map = dict(manifest.argument_types)
    validators = {
        "string": lambda value: isinstance(value, str),
        "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
        "object": lambda value: isinstance(value, dict),
    }
    if any(not validators[type_map[key]](value) for key, value in arguments.items()):
        return "argument_type_mismatch"
    return None
