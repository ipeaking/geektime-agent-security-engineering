"""第 06 讲多层 Guardrails 命令行入口。"""

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from agent_security.prompt_firewall.config import load_policy as load_firewall_policy, load_rules
from agent_security.prompt_firewall.firewall import PromptFirewall

from .config import GuardrailConfigError, load_guardrail_policy, load_scenarios
from .evaluator import evaluate
from .pipeline import GuardrailPipeline
from .renderer import render_outputs


DEFAULT_ROOT = Path("labs/lesson_06_multi_layer_guardrails")
DEFAULT_SCENARIOS = DEFAULT_ROOT / "scenarios"
DEFAULT_OUTPUT = DEFAULT_ROOT / "generated"
DEFAULT_POLICY = DEFAULT_ROOT / "config" / "guardrails.toml"
DEFAULT_FIREWALL_ROOT = Path("labs/lesson_05_prompt_firewall")


def _load(args: argparse.Namespace):
    rules = load_rules(args.firewall_root / "config" / "rules.toml")
    firewall_policy = load_firewall_policy(args.firewall_root / "config" / "policy.toml")
    guardrail_policy = load_guardrail_policy(args.guardrail_policy)
    scenarios = load_scenarios(
        args.scenarios_dir,
        args.lesson_root,
        args.firewall_root,
        guardrail_policy,
    )
    return scenarios, GuardrailPipeline(
        PromptFirewall(rules, firewall_policy),
        guardrail_policy,
    )


def _validate(args: argparse.Namespace) -> int:
    scenarios, _ = _load(args)
    print("多层 Guardrails 配置有效：%d 个确定性 Scenario。" % len(scenarios))
    return 0


def _evaluate(args: argparse.Namespace) -> int:
    scenarios, pipeline = _load(args)
    report = evaluate(scenarios, pipeline)
    print("Guardrails Scenario %d/%d 与精确期望一致。" % (report.passed, report.total))
    return 0 if report.strict_passed or not args.strict else 1


def _run(args: argparse.Namespace) -> int:
    scenarios, pipeline = _load(args)
    selected = next((item for item in scenarios if item.id == args.scenario), None)
    if selected is None:
        raise GuardrailConfigError("unknown scenario id: %s" % args.scenario)
    report = evaluate((selected,), pipeline)
    payload = json.loads(render_outputs(report)["evaluation_results.json"])
    print(json.dumps(payload["scenarios"][0], ensure_ascii=False, indent=2))
    return 0 if report.strict_passed else 1


def _render(args: argparse.Namespace) -> int:
    scenarios, pipeline = _load(args)
    outputs = render_outputs(evaluate(scenarios, pipeline))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in outputs.items():
        (args.output_dir / filename).write_text(content, encoding="utf-8")
    print("多层 Guardrails 已生成 %d 个确定性文件。" % len(outputs))
    return 0


def _check(args: argparse.Namespace) -> int:
    scenarios, pipeline = _load(args)
    report = evaluate(scenarios, pipeline)
    outputs = render_outputs(report)
    stale = [
        filename
        for filename, expected in outputs.items()
        if not (args.output_dir / filename).is_file()
        or (args.output_dir / filename).read_text(encoding="utf-8") != expected
    ]
    if stale:
        print("多层 Guardrails 生成文件已过期：%s" % ", ".join(stale))
        return 1
    if not report.strict_passed:
        print("多层 Guardrails 精确 Scenario 契约失败。")
        return 1
    print("多层 Guardrails 生成文件与 Scenario 一致，精确契约通过。")
    return 0


def _demo(args: argparse.Namespace) -> int:
    scenarios, pipeline = _load(args)
    report = evaluate(scenarios, pipeline)
    for item in report.scenarios:
        stopped = item.trace.stopped_at.value if item.trace.stopped_at else "-"
        print("%s %s stopped_at=%s" % (item.scenario.id, item.trace.outcome.value, stopped))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    def common(command: argparse.ArgumentParser) -> None:
        command.add_argument("--lesson-root", type=Path, default=DEFAULT_ROOT)
        command.add_argument("--scenarios-dir", type=Path, default=DEFAULT_SCENARIOS)
        command.add_argument("--firewall-root", type=Path, default=DEFAULT_FIREWALL_ROOT)
        command.add_argument("--guardrail-policy", type=Path, default=DEFAULT_POLICY)

    validate = commands.add_parser("validate")
    common(validate)
    validate.set_defaults(handler=_validate)
    run = commands.add_parser("run")
    common(run)
    run.add_argument("--scenario", required=True)
    run.set_defaults(handler=_run)
    evaluation = commands.add_parser("evaluate")
    common(evaluation)
    evaluation.add_argument("--strict", action="store_true")
    evaluation.set_defaults(handler=_evaluate)
    render = commands.add_parser("render")
    common(render)
    render.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    render.set_defaults(handler=_render)
    check = commands.add_parser("check")
    common(check)
    check.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    check.set_defaults(handler=_check)
    demo = commands.add_parser("demo")
    common(demo)
    demo.set_defaults(handler=_demo)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (GuardrailConfigError, OSError, UnicodeError, ValueError) as error:
        print("多层 Guardrails 失败：%s" % error)
        return 2
