"""将 GuardResult 映射为 observe 或 enforce 模式的准入结果。"""

from agent_security.content_pipeline.models import ContentEnvelope

from .firewall import PromptFirewall
from .models import FirewallDecision, FirewallMode, FirewallOutcome


class PromptFirewallMiddleware:
    def __init__(self, firewall: PromptFirewall) -> None:
        self.firewall = firewall

    def process(self, envelope: ContentEnvelope, mode: FirewallMode | str) -> FirewallOutcome:
        selected_mode = FirewallMode(mode)
        result = self.firewall.inspect(envelope)
        blocked = result.decision is FirewallDecision.BLOCK
        forward = selected_mode is FirewallMode.OBSERVE or not blocked
        return FirewallOutcome(
            forward_to_model=forward,
            flagged=result.decision is not FirewallDecision.ALLOW,
            envelope=envelope if forward else None,
            guard_result=result,
        )
