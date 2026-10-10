"""Prompt Firewall 的不可变领域对象。"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from agent_security.content_pipeline.models import ContentEnvelope


class FirewallDecision(str, Enum):
    ALLOW = "ALLOW"
    FLAG = "FLAG"
    BLOCK = "BLOCK"


class FirewallMode(str, Enum):
    OBSERVE = "observe"
    ENFORCE = "enforce"


class ScanStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


class DecisionReason(str, Enum):
    SCORE_BELOW_FLAG = "score_below_flag"
    SCORE_AT_OR_ABOVE_FLAG = "score_at_or_above_flag"
    SCORE_AT_OR_ABOVE_BLOCK = "score_at_or_above_block"
    CONTENT_LENGTH_EXCEEDED = "content_length_exceeded"


class CaseSuite(str, Enum):
    CONTRACT = "CONTRACT"
    EVALUATION = "EVALUATION"
    CHALLENGE = "CHALLENGE"


class IntentLabel(str, Enum):
    BENIGN = "BENIGN"
    MALICIOUS = "MALICIOUS"
    UNKNOWN = "UNKNOWN"


class PatternType(str, Enum):
    LITERAL = "literal"
    BOUNDED_TERMS = "bounded_terms"


@dataclass(frozen=True)
class FirewallRule:
    id: str
    category: str
    severity: str
    weight: int
    enabled: bool
    pattern_type: PatternType
    description: str
    explanation: str
    patterns: Tuple[str, ...] = ()
    leading_terms: Tuple[str, ...] = ()
    target_terms: Tuple[str, ...] = ()
    max_gap_chars: int = 0


@dataclass(frozen=True)
class CombinationRule:
    id: str
    required_categories: Tuple[str, ...]
    score: int
    explanation: str


@dataclass(frozen=True)
class AdmissionPolicyConfig:
    version: str
    flag_threshold: int
    block_threshold: int
    max_score: int
    max_content_chars: int
    max_evidence_per_rule: int
    max_evidence_chars: int
    combinations: Tuple[CombinationRule, ...]


@dataclass(frozen=True)
class RuleSet:
    version: str
    rules: Tuple[FirewallRule, ...]


@dataclass(frozen=True)
class NormalizedContent:
    original_sha256: str
    normalized_sha256: str
    text: str
    transformations: Tuple[str, ...]


@dataclass(frozen=True)
class GuardFinding:
    rule_id: str
    category: str
    severity: str
    weight: int
    evidence: str
    evidence_sha256: str
    normalized_start: int
    normalized_end: int
    explanation: str


@dataclass(frozen=True)
class ScoreContribution:
    contribution_id: str
    contribution_type: str
    category: str | None
    rule_id: str | None
    score: int
    explanation: str


@dataclass(frozen=True)
class AppliedCombination:
    combination_id: str
    required_categories: Tuple[str, ...]
    score: int
    explanation: str


@dataclass(frozen=True)
class RiskAssessment:
    findings: Tuple[GuardFinding, ...]
    base_score: int
    combination_score: int
    risk_score: int
    score_contributions: Tuple[ScoreContribution, ...]
    applied_combinations: Tuple[AppliedCombination, ...]
    scan_status: ScanStatus


@dataclass(frozen=True)
class GuardResult:
    decision: FirewallDecision
    decision_reason: DecisionReason
    assessment: RiskAssessment
    source_type: str
    content_sha256: str
    normalized_sha256: str
    normalization_transformations: Tuple[str, ...]
    ruleset_version: str
    admission_policy_version: str


@dataclass(frozen=True)
class FirewallOutcome:
    forward_to_model: bool
    flagged: bool
    envelope: ContentEnvelope | None
    guard_result: GuardResult


@dataclass(frozen=True)
class FirewallCase:
    id: str
    title: str
    suite: CaseSuite
    intent_label: IntentLabel
    expected_decision: FirewallDecision
    source_type: str
    fixture: str
    description: str
    tags: Tuple[str, ...]


@dataclass(frozen=True)
class CaseEvaluation:
    case: FirewallCase
    actual_decision: FirewallDecision
    passed: bool
    result: GuardResult


@dataclass(frozen=True)
class CarrierEvaluation:
    case_id: str
    source_type: str
    variant: str
    content_sha256: str
    expected_decision: FirewallDecision
    actual_decision: FirewallDecision
    risk_score: int
    categories: Tuple[str, ...]
    passed: bool


@dataclass(frozen=True)
class EvaluationReport:
    cases: Tuple[CaseEvaluation, ...]
    carrier_cases: Tuple[CarrierEvaluation, ...]
    contract_total: int
    contract_passed: int
    evaluation_total: int
    evaluation_exact: int
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    precision: float
    recall: float
    f1: float

    @property
    def strict_passed(self) -> bool:
        return self.contract_total == self.contract_passed and all(
            item.passed for item in self.carrier_cases
        )
