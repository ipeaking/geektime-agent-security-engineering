"""离线评测 Contract、Evaluation、Challenge 和第 04 讲 Carrier Envelope。"""

import hashlib
from pathlib import Path
from typing import Sequence

from agent_security.content_pipeline.models import ContentEnvelope
from agent_security.indirect_lab.builder import build_context
from agent_security.indirect_lab.loader import load_cases as load_carrier_cases

from .firewall import PromptFirewall
from .models import (
    CarrierEvaluation,
    CaseEvaluation,
    CaseSuite,
    EvaluationReport,
    FirewallCase,
    FirewallDecision,
)


CARRIER_BASELINE_TAG = "v0.4.2-lesson-04-indirect-prompt-injection"


def envelope_for_case(case: FirewallCase, lesson_root: Path) -> ContentEnvelope:
    path = (lesson_root / case.fixture).resolve()
    content = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return ContentEnvelope(
        id=case.id,
        source_type=case.source_type,
        source_ref=case.fixture,
        media_type="text/plain",
        trust="untrusted",
        intended_role="data",
        parser="PromptFirewallCase/utf-8",
        content=content,
        source_sha256=digest,
        content_sha256=digest,
        transformations=("decode_utf8",),
        metadata=(("case_id", case.id),),
    )


def envelope_for_text(content: str, source_type: str = "text") -> ContentEnvelope:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return ContentEnvelope(
        id="ADHOC",
        source_type=source_type,
        source_ref="<adhoc>",
        media_type="text/plain",
        trust="untrusted",
        intended_role="data",
        parser="PromptFirewallCLI/utf-8",
        content=content,
        source_sha256=digest,
        content_sha256=digest,
        transformations=("decode_utf8",),
        metadata=(),
    )


def evaluate(
    cases: Sequence[FirewallCase],
    lesson_root: Path,
    firewall: PromptFirewall,
    carrier_cases_dir: Path,
) -> EvaluationReport:
    evaluated = tuple(
        _evaluate_case(case, lesson_root, firewall)
        for case in sorted(cases, key=lambda item: item.id)
    )
    carrier = _evaluate_carriers(firewall, carrier_cases_dir)
    contract = tuple(item for item in evaluated if item.case.suite is CaseSuite.CONTRACT)
    evaluation = tuple(item for item in evaluated if item.case.suite is CaseSuite.EVALUATION)
    challenge = tuple(item for item in evaluated if item.case.suite is CaseSuite.CHALLENGE)
    tp = fp = tn = fn = 0
    for item in evaluation:
        expected_positive = item.case.expected_decision in {
            FirewallDecision.FLAG,
            FirewallDecision.BLOCK,
        }
        actual_positive = item.actual_decision in {
            FirewallDecision.FLAG,
            FirewallDecision.BLOCK,
        }
        if expected_positive and actual_positive:
            tp += 1
        elif not expected_positive and actual_positive:
            fp += 1
        elif not expected_positive and not actual_positive:
            tn += 1
        else:
            fn += 1
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = _ratio(2 * precision * recall, precision + recall)
    return EvaluationReport(
        cases=evaluated,
        carrier_cases=carrier,
        contract_total=len(contract),
        contract_passed=sum(item.passed for item in contract),
        evaluation_total=len(evaluation),
        evaluation_exact=sum(item.passed for item in evaluation),
        challenge_total=len(challenge),
        challenge_detected=sum(item.passed for item in challenge),
        true_positive=tp,
        false_positive=fp,
        true_negative=tn,
        false_negative=fn,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def _evaluate_case(
    case: FirewallCase, lesson_root: Path, firewall: PromptFirewall
) -> CaseEvaluation:
    result = firewall.inspect(envelope_for_case(case, lesson_root))
    return CaseEvaluation(
        case=case,
        actual_decision=result.decision,
        passed=result.decision is case.expected_decision,
        result=result,
    )


def _evaluate_carriers(
    firewall: PromptFirewall, carrier_cases_dir: Path
) -> tuple[CarrierEvaluation, ...]:
    carrier_root = carrier_cases_dir.resolve().parent
    results: list[CarrierEvaluation] = []
    for case in load_carrier_cases(carrier_cases_dir):
        envelope = build_context(case, carrier_root).envelope
        result = firewall.inspect(envelope)
        expected = (
            FirewallDecision.ALLOW
            if case.variant == "clean"
            else FirewallDecision.BLOCK
        )
        results.append(
            CarrierEvaluation(
                case_id=case.id,
                source_type=case.carrier,
                variant=case.variant,
                content_sha256=envelope.content_sha256,
                expected_decision=expected,
                actual_decision=result.decision,
                risk_score=result.assessment.risk_score,
                categories=tuple(
                    sorted({finding.category for finding in result.assessment.findings})
                ),
                passed=result.decision is expected,
            )
        )
    return tuple(sorted(results, key=lambda item: item.case_id))


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0
