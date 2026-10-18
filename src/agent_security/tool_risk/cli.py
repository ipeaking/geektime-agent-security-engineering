"""第 07 讲 Tool Risk Lab 命令行入口。"""

import argparse
from pathlib import Path
from typing import Optional, Sequence

from .config import ToolRiskConfigError, load_scenarios, load_tools
from .evaluator import evaluate
from .renderer import render_outputs


DEFAULT_ROOT = Path("labs/lesson_07_tool_risk")
DEFAULT_TOOLS = DEFAULT_ROOT / "config" / "tools.toml"
DEFAULT_SCENARIOS = DEFAULT_ROOT / "scenarios"
DEFAULT_OUTPUT = DEFAULT_ROOT / "generated"


def _load(args: argparse.Namespace):
    tools = load_tools(args.tools)
    scenarios = load_scenarios(args.scenarios_dir, args.lesson_root, tools)
    return tools, scenarios


def _validate(args: argparse.Namespace) -> int:
    tools, scenarios = _load(args)
    print("Tool Risk 配置有效：%d 个工具，%d 个 Scenario。" % (len(tools), len(scenarios)))
    return 0


def _evaluate(args: argparse.Namespace) -> int:
    tools, scenarios = _load(args)
    report = evaluate(scenarios, tools)
    print("Tool Risk Scenario %d/%d 与精确期望一致。" % (report.passed, report.total))
    return 0 if report.strict_passed or not args.strict else 1


def _render(args: argparse.Namespace) -> int:
    tools, scenarios = _load(args)
    outputs = render_outputs(evaluate(scenarios, tools))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        (args.output_dir / name).write_text(content, encoding="utf-8")
    print("Tool Risk Lab 已生成 %d 个确定性文件。" % len(outputs))
    return 0


def _check(args: argparse.Namespace) -> int:
    tools, scenarios = _load(args)
    report = evaluate(scenarios, tools)
    outputs = render_outputs(report)
    stale = [
        name
        for name, content in outputs.items()
        if not (args.output_dir / name).is_file()
        or (args.output_dir / name).read_text(encoding="utf-8") != content
    ]
    if stale:
        print("Tool Risk 生成文件已过期：%s" % ", ".join(stale))
        return 1
    if not report.strict_passed:
        print("Tool Risk 精确 Scenario 契约失败。")
        return 1
    print("Tool Risk 生成文件与 Scenario 一致，精确契约通过。")
    return 0


def _demo(args: argparse.Namespace) -> int:
    tools, scenarios = _load(args)
    for item in evaluate(scenarios, tools).runs:
        print(
            "%s proposed=%d executed=%d effects=%d canary_sink=%s"
            % (
                item.scenario.id,
                len(item.proposed_tools),
                len(item.executed_tools),
                len(item.events),
                "yes" if item.canary_reached_sink else "no",
            )
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    def common(command: argparse.ArgumentParser) -> None:
        command.add_argument("--lesson-root", type=Path, default=DEFAULT_ROOT)
        command.add_argument("--tools", type=Path, default=DEFAULT_TOOLS)
        command.add_argument("--scenarios-dir", type=Path, default=DEFAULT_SCENARIOS)

    for name, handler in (("validate", _validate), ("demo", _demo)):
        command = commands.add_parser(name)
        common(command)
        command.set_defaults(handler=handler)
    evaluation = commands.add_parser("evaluate")
    common(evaluation)
    evaluation.add_argument("--strict", action="store_true")
    evaluation.set_defaults(handler=_evaluate)
    for name, handler in (("render", _render), ("check", _check)):
        command = commands.add_parser(name)
        common(command)
        command.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
        command.set_defaults(handler=handler)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (ToolRiskConfigError, OSError, UnicodeError, ValueError) as error:
        print("Tool Risk Lab 失败：%s" % error)
        return 2
