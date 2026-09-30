"""第 03 讲 Context Lab 的命令行入口。"""

import argparse
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Sequence, Tuple

from agent_security.lab.runner import load_project_environment
from agent_security.lab.server import LocalLabServer

from .builder import build_context
from .errors import ContextLabError
from .live_runtime import ContextLabRuntime
from .loader import load_cases
from .models import ExperimentCase
from .observation_executor import LocalPageFetcher, ObservationExecutor
from .recorder import ObservationRecorder
from .renderer import render_outputs
from .reporter import load_observations, write_observation_matrix
from .validator import validate_cases


DEFAULT_LESSON_ROOT = Path("labs/lesson_03_prompt_injection_mechanism")
DEFAULT_CASES_DIR = DEFAULT_LESSON_ROOT / "cases"
DEFAULT_GENERATED_DIR = DEFAULT_LESSON_ROOT / "generated"
DEFAULT_LIVE_DIR = Path(".lab-output/lesson-03")


def _load_valid_cases(cases_dir: Path) -> Tuple[Tuple[ExperimentCase, ...], int]:
    try:
        cases = load_cases(cases_dir)
    except ContextLabError as error:
        print("Context Lab 加载失败：%s" % error)
        return (), 2

    issues = validate_cases(cases, cases_dir.resolve().parent)
    if issues:
        print("Context Lab Case 校验失败：")
        for issue in issues:
            print("- %s %s: %s" % (issue.code, issue.location, issue.message))
        return (), 1
    return cases, 0


def _select_cases(
    cases: Sequence[ExperimentCase], case_id: Optional[str]
) -> Tuple[ExperimentCase, ...]:
    if case_id is None:
        return tuple(cases)
    selected = tuple(case for case in cases if case.id == case_id)
    if not selected:
        raise ContextLabError("unknown case id: %s" % case_id)
    return selected


def _inspect(args: argparse.Namespace) -> int:
    cases, status = _load_valid_cases(args.cases_dir)
    if status:
        return status
    try:
        selected = _select_cases(cases, args.case)
        payload = []
        for case in selected:
            built = build_context(case, args.cases_dir.resolve().parent)
            payload.append(
                {
                    "case_id": case.id,
                    "title": case.title,
                    "channel": case.channel,
                    "prompt_profile": case.prompt_profile,
                    "wrapper": case.wrapper,
                    "context_items": [asdict(item) for item in built.trace.items],
                }
            )
    except ContextLabError as error:
        print("Context Lab 检查失败：%s" % error)
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _render(args: argparse.Namespace) -> int:
    cases, status = _load_valid_cases(args.cases_dir)
    if status:
        return status
    try:
        outputs = render_outputs(cases, args.cases_dir.resolve().parent)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in outputs.items():
            (args.output_dir / filename).write_text(content, encoding="utf-8")
    except (ContextLabError, OSError) as error:
        print("Context Lab 生成失败：%s" % error)
        return 2
    print("Context Lab 已生成 %d 个确定性文件。" % len(outputs))
    return 0


def _check(args: argparse.Namespace) -> int:
    cases, status = _load_valid_cases(args.cases_dir)
    if status:
        return status
    try:
        outputs = render_outputs(cases, args.cases_dir.resolve().parent)
        stale = [
            filename
            for filename, expected in outputs.items()
            if not (args.output_dir / filename).is_file()
            or (args.output_dir / filename).read_text(encoding="utf-8") != expected
        ]
    except (ContextLabError, OSError) as error:
        print("Context Lab 检查失败：%s" % error)
        return 2
    if stale:
        print("Context Lab generated files are stale.")
        print("Run: make context-lab-render")
        print("Stale: %s" % ", ".join(stale))
        return 1
    print("Context Lab 生成文件与 Case 配置一致。")
    return 0


def _live(args: argparse.Namespace) -> int:
    cases, status = _load_valid_cases(args.cases_dir)
    if status:
        return status
    try:
        selected = _select_cases(cases, args.case)
    except ContextLabError as error:
        print("Context Lab Live 参数错误：%s" % error)
        return 2

    repository_root = Path.cwd()
    try:
        load_project_environment(repository_root)
    except RuntimeError as error:
        print("Context Lab Live 配置失败：%s" % error)
        return 2
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("Context Lab Live 需要在项目根目录 .env 中配置 DEEPSEEK_API_KEY。")
        return 2
    model = args.model or os.environ.get("DEEPSEEK_MODEL")
    if not model:
        print("Context Lab Live 需要 --model 或 .env 中的 DEEPSEEK_MODEL。")
        return 2

    recorder = ObservationRecorder(args.output_dir)
    exit_status = 0
    for case in selected:
        first_index = recorder.next_run_index(case.id)
        for offset in range(args.repeat):
            built = build_context(case, args.cases_dir.resolve().parent)
            run_index = first_index + offset
            if built.page_content is None:
                executor = ObservationExecutor(page_fetcher=None)
                try:
                    runtime = ContextLabRuntime.from_environment(model, executor)
                except RuntimeError as error:
                    print("Context Lab Live 依赖加载失败：%s" % error)
                    return 2
                observation = runtime.run(built, run_index)
            else:
                with tempfile.TemporaryDirectory(prefix="context-lab-") as directory:
                    pages_root = Path(directory)
                    (pages_root / "context.html").write_text(
                        built.page_content,
                        encoding="utf-8",
                    )
                    with LocalLabServer(pages_root) as server:
                        fetcher = LocalPageFetcher(server.base_url)
                        executor = ObservationExecutor(page_fetcher=fetcher)
                        try:
                            runtime = ContextLabRuntime.from_environment(model, executor)
                        except RuntimeError as error:
                            print("Context Lab Live 依赖加载失败：%s" % error)
                            return 2
                        observation = runtime.run(
                            built,
                            run_index,
                            page_url=server.base_url + "/pages/context.html",
                        )
            recorder.append(observation)
            print(json.dumps(observation.to_dict(), ensure_ascii=False))
            if observation.status in {"error", "unknown_tool"}:
                exit_status = 1
    print("Live 观察已写入：%s" % recorder.jsonl_path)
    return exit_status


def _report(args: argparse.Namespace) -> int:
    cases, status = _load_valid_cases(args.cases_dir)
    if status:
        return status
    try:
        observations = load_observations(args.input)
        markdown_path, csv_path = write_observation_matrix(
            observations,
            cases,
            args.output_dir,
        )
    except (ContextLabError, OSError) as error:
        print("Context Lab 报告生成失败：%s" % error)
        return 2
    print("观察矩阵已生成：%s" % markdown_path)
    print("观察数据已生成：%s" % csv_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_cases_argument(command: argparse.ArgumentParser) -> None:
        command.add_argument("--cases-dir", type=Path, default=DEFAULT_CASES_DIR)

    inspect_parser = subparsers.add_parser("inspect", help="检查 Case 和 Context Trace")
    add_cases_argument(inspect_parser)
    inspect_parser.add_argument("--case", default=None)
    inspect_parser.set_defaults(handler=_inspect)

    render_parser = subparsers.add_parser("render", help="生成确定性实验材料")
    add_cases_argument(render_parser)
    render_parser.add_argument("--output-dir", type=Path, default=DEFAULT_GENERATED_DIR)
    render_parser.set_defaults(handler=_render)

    check_parser = subparsers.add_parser("check", help="检查生成材料是否过期")
    add_cases_argument(check_parser)
    check_parser.add_argument("--output-dir", type=Path, default=DEFAULT_GENERATED_DIR)
    check_parser.set_defaults(handler=_check)

    live_parser = subparsers.add_parser("live", help="运行真实模型观察")
    add_cases_argument(live_parser)
    live_parser.add_argument("--case", default=None)
    live_parser.add_argument("--repeat", type=int, default=3)
    live_parser.add_argument("--model", default=None)
    live_parser.add_argument("--output-dir", type=Path, default=DEFAULT_LIVE_DIR)
    live_parser.set_defaults(handler=_live)

    report_parser = subparsers.add_parser("report", help="聚合真实模型观察")
    add_cases_argument(report_parser)
    report_parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_LIVE_DIR / "live_runs.jsonl",
    )
    report_parser.add_argument("--output-dir", type=Path, default=DEFAULT_LIVE_DIR)
    report_parser.set_defaults(handler=_report)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "repeat", 1) < 1:
        parser.error("--repeat must be at least 1")
    return int(args.handler(args))
