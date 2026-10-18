"""第 08 讲 Tool Permission System 命令行入口。"""

import argparse
from pathlib import Path
from typing import Optional, Sequence

from .config import (
    ToolPermissionConfigError,
    load_policy,
    load_scenarios,
    load_subjects,
    load_tasks,
    load_tools,
)
from .evaluator import evaluate
from .renderer import render_outputs


DEFAULT_ROOT = Path("labs/lesson_08_tool_permissions")
DEFAULT_CONFIG = DEFAULT_ROOT / "config"
DEFAULT_SCENARIOS = DEFAULT_ROOT / "scenarios"
DEFAULT_OUTPUT = DEFAULT_ROOT / "generated"


def _load(args: argparse.Namespace):
    tools = load_tools(args.config_dir / "tools.toml")
    subjects = load_subjects(args.config_dir / "subjects.toml")
    tasks = load_tasks(args.config_dir / "tasks.toml", tools)
    policy = load_policy(args.config_dir / "policy.toml")
    scenarios = load_scenarios(args.scenarios_dir, subjects, tasks)
    return tools, subjects, tasks, policy, scenarios


def _report(args: argparse.Namespace):
    tools, subjects, tasks, policy, scenarios = _load(args)
    return evaluate(scenarios, tools, subjects, tasks, policy)


def _validate(args: argparse.Namespace) -> int:
    tools, subjects, tasks, policy, scenarios = _load(args)
    print(
        "Tool Permission 配置有效：%d 个工具，%d 个主体，%d 个任务，%d 个 Scenario；策略 %s。"
        % (len(tools), len(subjects), len(tasks), len(scenarios), policy.version)
    )
    return 0


def _evaluate(args: argparse.Namespace) -> int:
    report = _report(args)
    print("Tool Permission Scenario %d/%d 与精确期望一致。" % (report.passed, report.total))
    return 0 if report.strict_passed or not args.strict else 1


def _render(args: argparse.Namespace) -> int:
    outputs = render_outputs(_report(args))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        (args.output_dir / name).write_text(content, encoding="utf-8")
    print("Tool Permission 已生成 %d 个确定性文件。" % len(outputs))
    return 0


def _check(args: argparse.Namespace) -> int:
    report = _report(args)
    outputs = render_outputs(report)
    stale = [
        name
        for name, content in outputs.items()
        if not (args.output_dir / name).is_file()
        or (args.output_dir / name).read_text(encoding="utf-8") != content
    ]
    if stale:
        print("Tool Permission 生成文件已过期：%s" % ", ".join(stale))
        return 1
    if not report.strict_passed:
        print("Tool Permission 精确 Scenario 契约失败。")
        return 1
    print("Tool Permission 生成文件与 Scenario 一致，精确契约通过。")
    return 0


def _demo(args: argparse.Namespace) -> int:
    for item in _report(args).runs:
        print(
            "%s %s reason=%s delegated=%s"
            % (
                item.scenario.id,
                item.execution.decision.outcome.value,
                item.execution.decision.reason_code,
                "yes" if item.execution.delegated else "no",
            )
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    def common(command: argparse.ArgumentParser) -> None:
        command.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG)
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
    except (ToolPermissionConfigError, OSError, UnicodeError, ValueError) as error:
        print("Tool Permission 失败：%s" % error)
        return 2
