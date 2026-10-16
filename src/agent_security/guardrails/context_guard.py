"""检查来源边界、来源标签伪造和跨段风险组合。"""

import hashlib

from .models import (
    ContextSegment,
    GuardrailAction,
    GuardrailEvent,
    GuardrailPolicyConfig,
    GuardrailStage,
    SegmentInspection,
)


EXPECTED_BOUNDARIES = {
    "system": ("trusted", "instruction"),
    "user": ("user_controlled", "instruction"),
    "webpage": ("untrusted", "data"),
    "pdf": ("untrusted", "data"),
    "email": ("untrusted", "data"),
    "rag_document": ("untrusted", "data"),
    "tool_result": ("untrusted", "data"),
    "documentation": ("untrusted", "data"),
}
class ContextGuard:
    def __init__(self, policy: GuardrailPolicyConfig) -> None:
        self.policy = policy

    def inspect(self, inspections: tuple[SegmentInspection, ...]) -> GuardrailEvent:
        segments = tuple(item.segment for item in inspections)
        integrity_failures = self._integrity_failures(segments)
        if integrity_failures:
            return GuardrailEvent(
                stage=GuardrailStage.CONTEXT,
                guard_name="ContextGuard",
                action=GuardrailAction.BLOCK,
                reason_code="context_metadata_integrity_failed",
                evidence=tuple(integrity_failures[: self.policy.max_event_evidence]),
                details=(("segment_count", str(len(segments))),),
            )

        categories_by_segment = {
            item.segment.id: {finding.category for finding in item.result.assessment.findings}
            for item in inspections
        }
        present_categories = set().union(*categories_by_segment.values())
        active_segments = {
            segment_id
            for segment_id, categories in categories_by_segment.items()
            if categories
        }
        for configured in self.policy.cross_segment_combinations:
            required = frozenset(configured)
            contributing = {
                segment_id
                for segment_id, categories in categories_by_segment.items()
                if categories & required
            }
            if required.issubset(present_categories) and len(contributing) >= 2:
                return GuardrailEvent(
                    stage=GuardrailStage.CONTEXT,
                    guard_name="ContextGuard",
                    action=GuardrailAction.BLOCK,
                    reason_code="cross_segment_risk_chain",
                    evidence=tuple(sorted(required)),
                    details=(
                        ("contributing_segments", ",".join(sorted(contributing))),
                        ("segments_with_findings", str(len(active_segments))),
                    ),
                )

        spoofed = tuple(
            item.id
            for item in segments
            if item.trust == "untrusted"
            and any(marker.casefold() in item.content.casefold() for marker in self.policy.spoof_markers)
        )
        if spoofed:
            return GuardrailEvent(
                stage=GuardrailStage.CONTEXT,
                guard_name="ContextGuard",
                action=GuardrailAction.FLAG,
                reason_code="source_label_spoofing",
            evidence=spoofed[: self.policy.max_event_evidence],
                details=(("program_metadata_retained", "true"),),
            )

        return GuardrailEvent(
            stage=GuardrailStage.CONTEXT,
            guard_name="ContextGuard",
            action=GuardrailAction.PASS,
            reason_code="context_boundaries_preserved",
            evidence=(),
            details=(("segment_count", str(len(segments))),),
        )

    @staticmethod
    def _integrity_failures(segments: tuple[ContextSegment, ...]) -> list[str]:
        failures: list[str] = []
        ids = [item.id for item in segments]
        if len(ids) != len(set(ids)):
            failures.append("duplicate_segment_id")
        for segment in segments:
            actual = hashlib.sha256(segment.content.encode("utf-8")).hexdigest()
            if actual != segment.content_sha256:
                failures.append(segment.id + ":content_hash_mismatch")
            expected = EXPECTED_BOUNDARIES.get(segment.source)
            if expected is None:
                failures.append(segment.id + ":unknown_source")
            elif (segment.trust, segment.intended_role) != expected:
                failures.append(segment.id + ":external_boundary_mismatch")
        return failures
