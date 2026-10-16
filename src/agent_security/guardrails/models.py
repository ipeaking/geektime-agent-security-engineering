"""多层 Guardrails 的不可变领域对象。"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Tuple

from agent_security.models import ToolCall
from agent_security.prompt_firewall.models import GuardResult


class GuardrailStage(str, Enum):
    INPUT = "INPUT"
    CONTEXT = "CONTEXT"
    TOOL_PROPOSAL = "TOOL_PROPOSAL"
    OUTPUT = "OUTPUT"


class GuardrailAction(str, Enum):
    PASS = "PASS"
    FLAG = "FLAG"
    BLOCK = "BLOCK"
    REDACT = "REDACT"


class StageStatus(str, Enum):
    EXECUTED = "EXECUTED"
    NOT_RUN = "NOT_RUN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PipelineOutcome(str, Enum):
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_FLAGS = "COMPLETED_WITH_FLAGS"
    COMPLETED_REDACTED = "COMPLETED_REDACTED"
    BLOCKED = "BLOCKED"


class OutputMode(str, Enum):
    BLOCK = "BLOCK"
    REDACT = "REDACT"


@dataclass(frozen=True)
class GuardrailPolicyConfig:
    version: str
    known_tools: Tuple[str, ...]
    sensitive_tools: Tuple[str, ...]
    cross_segment_combinations: Tuple[Tuple[str, ...], ...]
    spoof_markers: Tuple[str, ...]
    max_event_evidence: int
    max_output_chars: int
    max_protected_values: int
    max_protected_value_chars: int
    redaction_token: str


@dataclass(frozen=True)
class ContextSegment:
    id: str
    source: str
    trust: str
    intended_role: str
    transport: str
    media_type: str
    parser: str
    content: str
    content_sha256: str


@dataclass(frozen=True)
class SegmentInspection:
    segment: ContextSegment
    result: GuardResult
    action: GuardrailAction


@dataclass(frozen=True)
class TaskContract:
    task_type: str
    allowed_tools: Tuple[str, ...]


@dataclass(frozen=True)
class ReplayPlan:
    tool_call: ToolCall | None
    output_text: str | None
    protected_values: Tuple[str, ...]


@dataclass(frozen=True)
class GuardrailEvent:
    stage: GuardrailStage
    guard_name: str
    action: GuardrailAction
    reason_code: str
    evidence: Tuple[str, ...]
    details: Tuple[Tuple[str, str], ...]


@dataclass(frozen=True)
class StageRecord:
    stage: GuardrailStage
    status: StageStatus
    action: GuardrailAction | None
    events: Tuple[GuardrailEvent, ...]


@dataclass(frozen=True)
class ExpectedStage:
    status: StageStatus
    action: GuardrailAction | None


@dataclass(frozen=True)
class ScenarioExpectation:
    stages: Tuple[Tuple[GuardrailStage, ExpectedStage], ...]
    outcome: PipelineOutcome
    stopped_at: GuardrailStage | None

    def stage(self, stage: GuardrailStage) -> ExpectedStage:
        return dict(self.stages)[stage]


@dataclass(frozen=True)
class GuardrailScenario:
    id: str
    title: str
    description: str
    task_contract: TaskContract
    segments: Tuple[ContextSegment, ...]
    replay: ReplayPlan
    output_mode: OutputMode
    expected: ScenarioExpectation


@dataclass(frozen=True)
class GuardrailTrace:
    scenario_id: str
    stages: Tuple[StageRecord, ...]
    outcome: PipelineOutcome
    stopped_at: GuardrailStage | None
    output_text: str | None

    def stage(self, stage: GuardrailStage) -> StageRecord:
        return next(item for item in self.stages if item.stage is stage)


@dataclass(frozen=True)
class ScenarioEvaluation:
    scenario: GuardrailScenario
    trace: GuardrailTrace
    passed: bool
    mismatches: Tuple[str, ...]


@dataclass(frozen=True)
class GuardrailEvaluationReport:
    scenarios: Tuple[ScenarioEvaluation, ...]

    @property
    def passed(self) -> int:
        return sum(item.passed for item in self.scenarios)

    @property
    def total(self) -> int:
        return len(self.scenarios)

    @property
    def strict_passed(self) -> bool:
        return self.passed == self.total


def stable_tool_call(name: str, arguments: Mapping[str, Any], scenario_id: str) -> ToolCall:
    """复用公共 ToolCall，同时消除默认 UUID 带来的非确定性。"""

    return ToolCall(
        name=name,
        arguments=dict(arguments),
        reason="deterministic replay; not a live model proposal",
        call_id=scenario_id + "-CALL-001",
    )
