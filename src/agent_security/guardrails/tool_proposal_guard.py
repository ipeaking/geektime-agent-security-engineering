"""执行前检查确定性 Replay 中的工具提议。"""

from agent_security.models import ToolCall

from .models import (
    ContextSegment,
    GuardrailAction,
    GuardrailEvent,
    GuardrailPolicyConfig,
    GuardrailStage,
    TaskContract,
)


class ToolProposalGuard:
    def __init__(self, policy: GuardrailPolicyConfig) -> None:
        self.known_tools = set(policy.known_tools)
        self.sensitive_tools = set(policy.sensitive_tools)

    def inspect(
        self,
        contract: TaskContract,
        tool_call: ToolCall,
        segments: tuple[ContextSegment, ...],
    ) -> GuardrailEvent:
        tool_name = tool_call.name
        details = (("tool_name", tool_name), ("task_type", contract.task_type))
        if tool_name not in self.known_tools:
            return self._block("unknown_tool", details)
        if tool_name == "send_diagnostic" and tool_name not in contract.allowed_tools:
            return self._block("outbound_action_not_authorized", details)
        if tool_name not in contract.allowed_tools:
            if tool_name in self.sensitive_tools and any(item.trust == "untrusted" for item in segments):
                return self._block(
                    "unauthorized_sensitive_tool_with_untrusted_context",
                    details,
                )
            reason = "tool_not_required_by_task" if tool_name == "read_file" else "tool_not_allowed_by_task"
            return self._block(reason, details)
        return GuardrailEvent(
            stage=GuardrailStage.TOOL_PROPOSAL,
            guard_name="ToolProposalGuard",
            action=GuardrailAction.PASS,
            reason_code="tool_allowed_by_task_contract",
            evidence=(tool_name,),
            details=details,
        )

    @staticmethod
    def _block(reason: str, details: tuple[tuple[str, str], ...]) -> GuardrailEvent:
        return GuardrailEvent(
            stage=GuardrailStage.TOOL_PROPOSAL,
            guard_name="ToolProposalGuard",
            action=GuardrailAction.BLOCK,
            reason_code=reason,
            evidence=(dict(details)["tool_name"],),
            details=details,
        )
