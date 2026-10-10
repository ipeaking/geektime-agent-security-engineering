"""第 05 讲 Prompt Firewall 命令行入口。"""

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from .config import FirewallConfigError, load_cases, load_policy, load_rules
from .evaluator import envelope_for_case, envelope_for_text, evaluate
from .firewall import PromptFirewall
from .models import FirewallCase, GuardResult
from .renderer import render_outputs


DEFAULT_LESSON_ROOT = Path("labs/lesson_05_prompt_firewall")
DEFAULT_RULES = DEFAULT_LESSON_ROOT / "config" / "rules.toml"
DEFAULT_POLICY = DEFAULT_LESSON_ROOT / "config" / "policy.toml"
DEFAULT_CASES_DIR = DEFAULT_LESSON_ROOT / "cases"
DEFAULT_OUTPUT_DIR = DEFAULT_LESSON_ROOT / "generated"
DEFAULT_CARRIER_CASES = Path("labs/lesson_04_indirect_prompt_injection/cases")


def _load(args: argparse.Namespace):
    ruleset = load_rules(args.rules)
    policy = load_policy(args.policy)
    cases = load_cases(args.cases_dir, args.cases_dir.resolve().parent)
    return ruleset, policy, cases, PromptFirewall(ruleset, policy)


def _validate(args: argparse.Namespace) -> int:
    ruleset, policy, cases, _ = _load(args)
    print(
        "Prompt Firewall 配置有效：%d 条规则，%d 个组合，%d 个 Case。"
        % (len(ruleset.rules), len(policy.combinations), len(cases))
    )
    return 0


def _scan(args: argparse.Namespace) -> int:
    _, _, cases, firewall = _load(args)
    if args.case:
        selected = [case for case in cases if case.id == args.case]
        if not selected:
            raise FirewallConfigError("unknown case id: %s" % args.case)
        envelope = envelope_for_case(selected[0], args.cases_dir.resolve().parent)
    else:
        content = args.file.read_text(encoding="utf-8")
        envelope = envelope_for_text(content, args.source_type)
    print(json.dumps(_result_payload(firewall.inspect(envelope)), ensure_ascii=False, indent=2))
    return 0


def _evaluate(args: argparse.Namespace) -> int:
    ruleset, _, cases, firewall = _load(args)
    report = evaluate(
        cases,
        args.cases_dir.resolve().parent,
        firewall,
        args.carrier_cases_dir,
    )
    print(
        "Contract %d/%d；Evaluation %d/%d；Carrier %d/%d；Challenge %d/%d；Evaluation Precision %.3f；Recall %.3f；F1 %.3f。"
        % (
            report.contract_passed,
            report.contract_total,
            report.evaluation_exact,
            report.evaluation_total,
            sum(item.passed for item in report.carrier_cases),
            len(report.carrier_cases),
            report.challenge_detected,
            report.challenge_total,
            report.precision,
            report.recall,
            report.f1,
        )
    )
    if args.strict and not report.strict_passed:
        return 1
    return 0


def _render(args: argparse.Namespace) -> int:
    ruleset, _, cases, firewall = _load(args)
    report = evaluate(
        cases,
        args.cases_dir.resolve().parent,
        firewall,
        args.carrier_cases_dir,
    )
    outputs = render_outputs(cases, ruleset, report)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in outputs.items():
        (args.output_dir / filename).write_text(content, encoding="utf-8")
    print("Prompt Firewall 已生成 %d 个确定性文件。" % len(outputs))
    return 0


def _check(args: argparse.Namespace) -> int:
    ruleset, _, cases, firewall = _load(args)
    report = evaluate(
        cases,
        args.cases_dir.resolve().parent,
        firewall,
        args.carrier_cases_dir,
    )
    outputs = render_outputs(cases, ruleset, report)
    stale = [
        filename
        for filename, expected in outputs.items()
        if not (args.output_dir / filename).is_file()
        or (args.output_dir / filename).read_text(encoding="utf-8") != expected
    ]
    if stale:
        print("Prompt Firewall generated files are stale.")
        print("Run: make prompt-firewall-render")
        print("Stale: %s" % ", ".join(stale))
        return 1
    if not report.strict_passed:
        print("Prompt Firewall strict contracts failed.")
        return 1
    print("Prompt Firewall 生成文件与配置一致，严格契约通过。")
    return 0


def _demo(args: argparse.Namespace) -> int:
    _, _, cases, firewall = _load(args)
    by_id = {case.id: case for case in cases}
    for case_id in ("PF-CONTRACT-001", "PF-CONTRACT-005", "PF-CONTRACT-003"):
        case = by_id[case_id]
        result = firewall.inspect(envelope_for_case(case, args.cases_dir.resolve().parent))
        print("%s %s score=%d" % (case.id, result.decision.value, result.assessment.risk_score))
    return 0


def _result_payload(result: GuardResult) -> dict[str, object]:
    return {
        "decision": result.decision.value,
        "decision_reason": result.decision_reason.value,
        "scan_status": result.assessment.scan_status.value,
        "base_score": result.assessment.base_score,
        "combination_score": result.assessment.combination_score,
        "risk_score": result.assessment.risk_score,
        "source_type": result.source_type,
        "content_sha256": result.content_sha256,
        "normalized_sha256": result.normalized_sha256,
        "ruleset_version": result.ruleset_version,
        "admission_policy_version": result.admission_policy_version,
        "findings": [
            {
                "rule_id": item.rule_id,
                "category": item.category,
                "severity": item.severity,
                "weight": item.weight,
                "evidence": item.evidence,
                "evidence_sha256": item.evidence_sha256,
                "normalized_start": item.normalized_start,
                "normalized_end": item.normalized_end,
                "explanation": item.explanation,
            }
            for item in result.assessment.findings
        ],
        "score_contributions": [
            {
                "id": item.contribution_id,
                "type": item.contribution_type,
                "category": item.category,
                "rule_id": item.rule_id,
                "score": item.score,
                "explanation": item.explanation,
            }
            for item in result.assessment.score_contributions
        ],
        "applied_combinations": [
            {
                "combination_id": item.combination_id,
                "required_categories": list(item.required_categories),
                "score": item.score,
                "explanation": item.explanation,
            }
            for item in result.assessment.applied_combinations
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(command: argparse.ArgumentParser) -> None:
        command.add_argument("--rules", type=Path, default=DEFAULT_RULES)
        command.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
        command.add_argument("--cases-dir", type=Path, default=DEFAULT_CASES_DIR)

    validate_parser = subparsers.add_parser("validate", help="校验规则、策略与 Case")
    add_common(validate_parser)
    validate_parser.set_defaults(handler=_validate)

    scan_parser = subparsers.add_parser("scan", help="扫描一个 Case 或文本文件")
    add_common(scan_parser)
    source = scan_parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--case")
    source.add_argument("--file", type=Path)
    scan_parser.add_argument("--source-type", default="text")
    scan_parser.set_defaults(handler=_scan)

    evaluate_parser = subparsers.add_parser("evaluate", help="运行离线评测")
    add_common(evaluate_parser)
    evaluate_parser.add_argument("--carrier-cases-dir", type=Path, default=DEFAULT_CARRIER_CASES)
    evaluate_parser.add_argument("--strict", action="store_true")
    evaluate_parser.set_defaults(handler=_evaluate)

    render_parser = subparsers.add_parser("render", help="生成确定性报告")
    add_common(render_parser)
    render_parser.add_argument("--carrier-cases-dir", type=Path, default=DEFAULT_CARRIER_CASES)
    render_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    render_parser.set_defaults(handler=_render)

    check_parser = subparsers.add_parser("check", help="检查生成报告是否过期")
    add_common(check_parser)
    check_parser.add_argument("--carrier-cases-dir", type=Path, default=DEFAULT_CARRIER_CASES)
    check_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    check_parser.set_defaults(handler=_check)

    demo_parser = subparsers.add_parser("demo", help="显示 ALLOW、FLAG、BLOCK 示例")
    add_common(demo_parser)
    demo_parser.set_defaults(handler=_demo)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (FirewallConfigError, OSError, UnicodeError) as error:
        print("Prompt Firewall 失败：%s" % error)
        return 2
