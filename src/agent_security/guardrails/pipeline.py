"""编排 Input、Context、Tool Proposal 与 Output 四层检查。"""

from agent_security.content_pipeline.models import ContentEnvelope
from agent_security.prompt_firewall.firewall import PromptFirewall
from agent_security.prompt_firewall.models import FirewallDecision

from .context_guard import ContextGuard
from .models import (
    GuardrailAction,
    GuardrailEvent,
    GuardrailPolicyConfig,
    GuardrailScenario,
    GuardrailStage,
    GuardrailTrace,
    PipelineOutcome,
    SegmentInspection,
    StageRecord,
    StageStatus,
)
from .output_guard import OutputGuard
from .tool_proposal_guard import ToolProposalGuard


STAGES = tuple(GuardrailStage)
DECISION_ACTION = {
    FirewallDecision.ALLOW: GuardrailAction.PASS,
    FirewallDecision.FLAG: GuardrailAction.FLAG,
    FirewallDecision.BLOCK: GuardrailAction.BLOCK,
}


class GuardrailPipeline:
    def __init__(
        self,
        input_guard: PromptFirewall,
        policy: GuardrailPolicyConfig,
    ) -> None:
        self.input_guard = input_guard
        self.policy = policy
        self.context_guard = ContextGuard(policy)
        self.tool_guard = ToolProposalGuard(policy)
        self.output_guard = OutputGuard(policy)

    def run(self, scenario: GuardrailScenario) -> GuardrailTrace:
        records: list[StageRecord] = []
        inspections = tuple(self._inspect_segment(item) for item in scenario.segments)
        input_event = self._input_event(inspections)
        records.append(self._executed(input_event))
        if input_event.action is GuardrailAction.BLOCK:
            return self._blocked(scenario.id, records, GuardrailStage.INPUT)

        context_event = self.context_guard.inspect(inspections)
        records.append(self._executed(context_event))
        if context_event.action is GuardrailAction.BLOCK:
            return self._blocked(scenario.id, records, GuardrailStage.CONTEXT)

        tool_call = scenario.replay.tool_call
        if tool_call is None:
            records.append(self._not_applicable(GuardrailStage.TOOL_PROPOSAL))
        else:
            tool_event = self.tool_guard.inspect(
                scenario.task_contract,
                tool_call,
                scenario.segments,
            )
            records.append(self._executed(tool_event))
            if tool_event.action is GuardrailAction.BLOCK:
                return self._blocked(scenario.id, records, GuardrailStage.TOOL_PROPOSAL)

        if scenario.replay.output_text is None:
            records.append(self._not_applicable(GuardrailStage.OUTPUT))
            return self._complete(scenario.id, records, None)
        output_event, output_text = self.output_guard.inspect(
            scenario.replay.output_text,
            scenario.replay.protected_values,
            scenario.output_mode,
        )
        records.append(self._executed(output_event))
        if output_event.action is GuardrailAction.BLOCK:
            return self._blocked(scenario.id, records, GuardrailStage.OUTPUT)
        return self._complete(scenario.id, records, output_text)

    def _inspect_segment(self, segment) -> SegmentInspection:
        envelope = ContentEnvelope(
            id=segment.id,
            source_type=segment.source,
            source_ref="guardrail-replay/" + segment.id,
            media_type=segment.media_type,
            trust=segment.trust,
            intended_role=segment.intended_role,
            parser=segment.parser,
            content=segment.content,
            source_sha256=segment.content_sha256,
            content_sha256=segment.content_sha256,
            transformations=("guardrail_replay",),
            metadata=(("transport", segment.transport),),
        )
        result = self.input_guard.inspect(envelope)
        return SegmentInspection(segment, result, DECISION_ACTION[result.decision])

    def _input_event(self, inspections: tuple[SegmentInspection, ...]) -> GuardrailEvent:
        actions = {item.action for item in inspections}
        action = (
            GuardrailAction.BLOCK
            if GuardrailAction.BLOCK in actions
            else GuardrailAction.FLAG
            if GuardrailAction.FLAG in actions
            else GuardrailAction.PASS
        )
        categories = sorted(
            {
                finding.category
                for item in inspections
                for finding in item.result.assessment.findings
            }
        )
        decisions = ",".join(
            "%s:%s" % (item.segment.id, item.action.value) for item in inspections
        )
        reason = {
            GuardrailAction.PASS: "all_segments_allowed",
            GuardrailAction.FLAG: "segment_risk_flagged",
            GuardrailAction.BLOCK: "segment_blocked_by_prompt_firewall",
        }[action]
        return GuardrailEvent(
            stage=GuardrailStage.INPUT,
            guard_name="PromptFirewall",
            action=action,
            reason_code=reason,
            evidence=tuple(categories[: self.policy.max_event_evidence]),
            details=(("segment_decisions", decisions),),
        )

    @staticmethod
    def _executed(event: GuardrailEvent) -> StageRecord:
        return StageRecord(event.stage, StageStatus.EXECUTED, event.action, (event,))

    @staticmethod
    def _not_applicable(stage: GuardrailStage) -> StageRecord:
        return StageRecord(stage, StageStatus.NOT_APPLICABLE, None, ())

    @staticmethod
    def _not_run(stage: GuardrailStage) -> StageRecord:
        return StageRecord(stage, StageStatus.NOT_RUN, None, ())

    def _blocked(
        self,
        scenario_id: str,
        records: list[StageRecord],
        stage: GuardrailStage,
    ) -> GuardrailTrace:
        completed = {item.stage for item in records}
        records.extend(self._not_run(item) for item in STAGES if item not in completed)
        return GuardrailTrace(
            scenario_id=scenario_id,
            stages=tuple(records),
            outcome=PipelineOutcome.BLOCKED,
            stopped_at=stage,
            output_text=None,
        )

    @staticmethod
    def _complete(
        scenario_id: str,
        records: list[StageRecord],
        output_text: str | None,
    ) -> GuardrailTrace:
        actions = {item.action for item in records if item.action is not None}
        outcome = (
            PipelineOutcome.COMPLETED_REDACTED
            if GuardrailAction.REDACT in actions
            else PipelineOutcome.COMPLETED_WITH_FLAGS
            if GuardrailAction.FLAG in actions
            else PipelineOutcome.COMPLETED
        )
        return GuardrailTrace(scenario_id, tuple(records), outcome, None, output_text)
