"""生成稳定、无时间戳的 Prompt Firewall 报告。"""

import json
from collections import Counter, defaultdict
from typing import Sequence

from .evaluator import CARRIER_BASELINE_TAG
from .models import (
    CaseSuite,
    EvaluationReport,
    FirewallCase,
    GuardResult,
    RuleSet,
)


GENERATED_NOTICE = "自动生成，请勿手工修改。"


def render_outputs(
    cases: Sequence[FirewallCase],
    ruleset: RuleSet,
    report: EvaluationReport,
) -> dict[str, str]:
    return {
        "case_catalog.md": _render_catalog(cases),
        "evaluation_report.md": _render_evaluation(report),
        "evaluation_results.json": _render_json(report),
        "rule_coverage.md": _render_rule_coverage(ruleset, report),
        "firewall_pipeline.mmd": _render_pipeline(),
    }


def _render_catalog(cases: Sequence[FirewallCase]) -> str:
    lines = [
        "# Prompt Firewall Case Catalog",
        "",
        "> %s" % GENERATED_NOTICE,
        "",
        "| Case | 标题 | Suite | Intent | Expected | Source Type | Fixture | Tags |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case in sorted(cases, key=lambda item: item.id):
        lines.append(
            "| %s | %s | %s | %s | %s | %s | `%s` | %s |"
            % (
                case.id,
                case.title,
                case.suite.value,
                case.intent_label.value,
                case.expected_decision.value,
                case.source_type,
                case.fixture,
                ", ".join(case.tags),
            )
        )
    lines.extend(["", "Intent 只描述场景；Expected 才是内容准入期望。", ""])
    return "\n".join(lines)


def _render_evaluation(report: EvaluationReport) -> str:
    decisions = Counter(item.actual_decision.value for item in report.cases)
    challenge = [item for item in report.cases if item.case.suite is CaseSuite.CHALLENGE]
    confusion = _decision_confusion(report)
    lines = [
        "# Prompt Firewall Evaluation Report",
        "",
        "> %s 风险分数是规则工程分值，不是恶意概率。" % GENERATED_NOTICE,
        "",
        "## Summary",
        "",
        "- Cases: %d" % len(report.cases),
        "- Contract: %d/%d passed" % (report.contract_passed, report.contract_total),
        "- Evaluation exact decisions: %d/%d"
        % (report.evaluation_exact, report.evaluation_total),
        "- Decisions: ALLOW=%d, FLAG=%d, BLOCK=%d"
        % (decisions["ALLOW"], decisions["FLAG"], decisions["BLOCK"]),
        "- High-risk detection: TP=%d, FP=%d, TN=%d, FN=%d"
        % (
            report.true_positive,
            report.false_positive,
            report.true_negative,
            report.false_negative,
        ),
        "- Precision=%.3f, Recall=%.3f, F1=%.3f"
        % (report.precision, report.recall, report.f1),
        "",
        "这些指标只描述固定课程样本，不代表未知输入上的泛化能力或生产准确率。",
        "",
        "## Evaluation Decision Confusion Matrix",
        "",
        "只统计 EVALUATION；行是期望决策，列是实际决策。",
        "",
        "| Expected \\ Actual | ALLOW | FLAG | BLOCK |",
        "| --- | ---: | ---: | ---: |",
        *[
            "| %s | %d | %d | %d |"
            % (
                expected,
                confusion[expected]["ALLOW"],
                confusion[expected]["FLAG"],
                confusion[expected]["BLOCK"],
            )
            for expected in ("ALLOW", "FLAG", "BLOCK")
        ],
        "",
        "## Case Results",
        "",
        "| Case | Suite | Expected | Actual | Score | Scan | Categories | Pass |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for item in report.cases:
        categories = sorted({finding.category for finding in item.result.assessment.findings})
        lines.append(
            "| %s | %s | %s | %s | %d | %s | %s | %s |"
            % (
                item.case.id,
                item.case.suite.value,
                item.case.expected_decision.value,
                item.actual_decision.value,
                item.result.assessment.risk_score,
                item.result.assessment.scan_status.value,
                ", ".join(categories) or "—",
                "yes" if item.passed else "no",
            )
        )
    lines.extend(
        [
            "",
            "## Challenge Results",
            "",
            "Challenge 不进入构建 Gate。",
            "",
            "| Case | Expected | Actual | Score | Rules | Result |",
            "| --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for item in challenge:
        lines.append(
            "| %s | %s | %s | %d | %s | %s |"
            % (
                item.case.id,
                item.case.expected_decision.value,
                item.actual_decision.value,
                item.result.assessment.risk_score,
                ", ".join(
                    sorted({finding.rule_id for finding in item.result.assessment.findings})
                )
                or "—",
                "detected" if item.passed else "missed",
            )
        )
    lines.extend(
        [
            "",
            "## Lesson 04 Carrier Integration",
            "",
            "- Baseline: `%s`" % CARRIER_BASELINE_TAG,
            "",
            "| Carrier Case | Type | Variant | Expected | Actual | Score | Categories | Pass |",
            "| --- | --- | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for item in report.carrier_cases:
        lines.append(
            "| %s | %s | %s | %s | %s | %d | %s | %s |"
            % (
                item.case_id,
                item.source_type,
                item.variant,
                item.expected_decision.value,
                item.actual_decision.value,
                item.risk_score,
                ", ".join(item.categories) or "—",
                "yes" if item.passed else "no",
            )
        )
    lines.append("")
    return "\n".join(lines)


def _render_json(report: EvaluationReport) -> str:
    payload = {
        "summary": {
            "case_count": len(report.cases),
            "contract_total": report.contract_total,
            "contract_passed": report.contract_passed,
            "evaluation_total": report.evaluation_total,
            "evaluation_exact": report.evaluation_exact,
            "true_positive": report.true_positive,
            "false_positive": report.false_positive,
            "true_negative": report.true_negative,
            "false_negative": report.false_negative,
            "precision": round(report.precision, 6),
            "recall": round(report.recall, 6),
            "f1": round(report.f1, 6),
            "strict_passed": report.strict_passed,
            "evaluation_decision_confusion": _decision_confusion(report),
        },
        "cases": [_case_json(item) for item in report.cases],
        "carrier_integration": [
            {
                "case_id": item.case_id,
                "source_type": item.source_type,
                "variant": item.variant,
                "content_sha256": item.content_sha256,
                "expected_decision": item.expected_decision.value,
                "actual_decision": item.actual_decision.value,
                "risk_score": item.risk_score,
                "categories": list(item.categories),
                "passed": item.passed,
            }
            for item in report.carrier_cases
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _decision_confusion(report: EvaluationReport) -> dict[str, dict[str, int]]:
    decisions = ("ALLOW", "FLAG", "BLOCK")
    matrix = {expected: {actual: 0 for actual in decisions} for expected in decisions}
    for item in report.cases:
        if item.case.suite is CaseSuite.EVALUATION:
            matrix[item.case.expected_decision.value][item.actual_decision.value] += 1
    return matrix


def _case_json(item) -> dict[str, object]:
    result: GuardResult = item.result
    return {
        "case_id": item.case.id,
        "suite": item.case.suite.value,
        "intent_label": item.case.intent_label.value,
        "expected_decision": item.case.expected_decision.value,
        "actual_decision": item.actual_decision.value,
        "passed": item.passed,
        "decision_reason": result.decision_reason.value,
        "base_score": result.assessment.base_score,
        "combination_score": result.assessment.combination_score,
        "risk_score": result.assessment.risk_score,
        "scan_status": result.assessment.scan_status.value,
        "findings": [
            {
                "rule_id": finding.rule_id,
                "category": finding.category,
                "severity": finding.severity,
                "weight": finding.weight,
                "evidence": finding.evidence,
                "evidence_sha256": finding.evidence_sha256,
                "normalized_start": finding.normalized_start,
                "normalized_end": finding.normalized_end,
                "explanation": finding.explanation,
            }
            for finding in result.assessment.findings
        ],
        "score_contributions": [
            {
                "id": contribution.contribution_id,
                "type": contribution.contribution_type,
                "category": contribution.category,
                "rule_id": contribution.rule_id,
                "score": contribution.score,
                "explanation": contribution.explanation,
            }
            for contribution in result.assessment.score_contributions
        ],
        "applied_combinations": [
            {
                "id": combination.combination_id,
                "required_categories": list(combination.required_categories),
                "score": combination.score,
                "explanation": combination.explanation,
            }
            for combination in result.assessment.applied_combinations
        ],
    }


def _render_rule_coverage(ruleset: RuleSet, report: EvaluationReport) -> str:
    hits: dict[str, set[str]] = defaultdict(set)
    for item in report.cases:
        for finding in item.result.assessment.findings:
            hits[finding.rule_id].add(item.case.id)
    lines = [
        "# Prompt Firewall Rule Coverage",
        "",
        "> %s" % GENERATED_NOTICE,
        "",
        "| Rule | Category | Weight | Case Count | Cases |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for rule in sorted(ruleset.rules, key=lambda item: item.id):
        case_ids = sorted(hits.get(rule.id, set()))
        lines.append(
            "| %s | %s | %d | %d | %s |"
            % (rule.id, rule.category, rule.weight, len(case_ids), ", ".join(case_ids) or "—")
        )
    lines.append("")
    return "\n".join(lines)


def _render_pipeline() -> str:
    return "\n".join(
        [
            "%% " + GENERATED_NOTICE,
            "flowchart LR",
            '    E["ContentEnvelope"] --> N["Normalizer"]',
            '    N --> D["Rule Detectors"]',
            '    D --> S["Risk Scorer"]',
            '    S --> R["RiskAssessment"]',
            '    R --> P["ContentAdmissionPolicy"]',
            '    P --> G["GuardResult"]',
            '    G --> M["PromptFirewallMiddleware"]',
            '    M -->|ALLOW| A["Original Content → Agent Context"]',
            '    M -->|FLAG| F["Original Content + program-side flag"]',
            '    M -->|BLOCK| B["Blocked result + audit event"]',
            "",
        ]
    )
