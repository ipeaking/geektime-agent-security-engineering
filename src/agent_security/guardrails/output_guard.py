"""对最终文本执行窄范围的合成 Canary 检查。"""

from .models import (
    GuardrailAction,
    GuardrailEvent,
    GuardrailPolicyConfig,
    GuardrailStage,
    OutputMode,
)


class OutputGuard:
    def __init__(self, policy: GuardrailPolicyConfig) -> None:
        self.redaction_token = policy.redaction_token
        self.max_event_evidence = policy.max_event_evidence

    def inspect(
        self,
        output_text: str,
        protected_values: tuple[str, ...],
        mode: OutputMode,
    ) -> tuple[GuardrailEvent, str | None]:
        matches = tuple(value for value in protected_values if value and value in output_text)
        if not matches:
            return (
                GuardrailEvent(
                    stage=GuardrailStage.OUTPUT,
                    guard_name="OutputGuard",
                    action=GuardrailAction.PASS,
                    reason_code="no_synthetic_canary_exposure",
                    evidence=(),
                    details=(("protected_value_count", str(len(protected_values))),),
                ),
                output_text,
            )
        evidence = tuple(
            "[SYNTHETIC_CANARY]" for _ in matches[: self.max_event_evidence]
        )
        if mode is OutputMode.BLOCK:
            return (
                GuardrailEvent(
                    stage=GuardrailStage.OUTPUT,
                    guard_name="OutputGuard",
                    action=GuardrailAction.BLOCK,
                    reason_code="synthetic_canary_exposure",
                    evidence=evidence,
                    details=(("match_count", str(len(matches))),),
                ),
                None,
            )
        redacted = output_text
        for value in matches:
            redacted = redacted.replace(value, self.redaction_token)
        return (
            GuardrailEvent(
                stage=GuardrailStage.OUTPUT,
                guard_name="OutputGuard",
                action=GuardrailAction.REDACT,
                reason_code="synthetic_canary_redacted",
                evidence=evidence,
                details=(("match_count", str(len(matches))),),
            ),
            redacted,
        )
