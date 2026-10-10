"""第 04 讲 Carrier Lab 的命令行入口。"""

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Sequence

from agent_security.content_pipeline.errors import ContentPipelineError
from agent_security.lab.runner import load_project_environment

from .builder import build_context
from .errors import IndirectLabError
from .live_runtime import CarrierLabRuntime
from .loader import load_cases
from .models import CarrierCase
from .observation_executor import CarrierObservationExecutor
from .recorder import ObservationRecorder
from .renderer import render_outputs
from .reporter import load_observations, write_observation_matrix
from .validator import validate_cases


DEFAULT_LESSON_ROOT = Path("labs/lesson_04_indirect_prompt_injection")
DEFAULT_CASES_DIR = DEFAULT_LESSON_ROOT / "cases"
DEFAULT_GENERATED_DIR = DEFAULT_LESSON_ROOT / "generated"
DEFAULT_LIVE_DIR = Path(".lab-output/lesson-04")


def _load_valid_cases(cases_dir: Path) -> tuple[tuple[CarrierCase, ...], int]:
    try:
        cases = load_cases(cases_dir)
    except (IndirectLabError, ContentPipelineError) as error:
        print("Carrier Lab 加载失败：%s" % error)
        return (), 2
    issues = validate_cases(cases, cases_dir.resolve().parent)
    if issues:
        print("Carrier Lab Case 校验失败：")
        for issue in issues:
            print("- %s %s: %s" % (issue.code, issue.location, issue.message))
        return (), 1
    return cases, 0


def _select_cases(
    cases: Sequence[CarrierCase], case_id: Optional[str]
) -> tuple[CarrierCase, ...]:
    if case_id is None:
        return tuple(cases)
    selected = tuple(case for case in cases if case.id == case_id)
    if not selected:
        raise IndirectLabError("unknown case id: %s" % case_id)
    return selected


def _inspect(args: argparse.Namespace) -> int:
    cases, status = _load_valid_cases(args.cases_dir)
    if status:
        return status
    try:
        payload = []
        for case in _select_cases(cases, args.case):
            built = build_context(case, args.cases_dir.resolve().parent)
            payload.append(
                {
                    "case_id": case.id,
                    "title": case.title,
                    "carrier": case.carrier,
                    "variant": case.variant,
                    "source_id": case.source_id,
                    "envelope": {
                        "source_type": built.envelope.source_type,
                        "source_ref": built.envelope.source_ref,
                        "media_type": built.envelope.media_type,
                        "parser": built.envelope.parser,
                        "source_sha256": built.envelope.source_sha256,
                        "content_sha256": built.envelope.content_sha256,
                        "transformations": built.envelope.transformations,
                        "metadata": built.envelope.metadata_dict(),
                    },
                    "context_items": [asdict(item) for item in built.trace.items],
                }
            )
    except (IndirectLabError, ContentPipelineError, OSError) as error:
        print("Carrier Lab 检查失败：%s" % error)
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
    except (IndirectLabError, ContentPipelineError, OSError) as error:
        print("Carrier Lab 生成失败：%s" % error)
        return 2
    print("Carrier Lab 已生成 %d 个确定性文件。" % len(outputs))
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
    except (IndirectLabError, ContentPipelineError, OSError) as error:
        print("Carrier Lab 检查失败：%s" % error)
        return 2
    if stale:
        print("Carrier Lab generated files are stale.")
        print("Run: make carrier-lab-render")
        print("Stale: %s" % ", ".join(stale))
        return 1
    print("Carrier Lab 生成文件与 Case 配置一致。")
    return 0


def _live(args: argparse.Namespace) -> int:
    cases, status = _load_valid_cases(args.cases_dir)
    if status:
        return status
    try:
        selected = _select_cases(cases, args.case)
    except IndirectLabError as error:
        print("Carrier Lab Live 参数错误：%s" % error)
        return 2

    try:
        load_project_environment(Path.cwd())
    except RuntimeError as error:
        print("Carrier Lab Live 配置失败：%s" % error)
        return 2
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("Carrier Lab Live 需要在项目根目录 .env 中配置 DEEPSEEK_API_KEY。")
        return 2
    model = args.model or os.environ.get("DEEPSEEK_MODEL")
    if not model:
        print("Carrier Lab Live 需要 --model 或 .env 中的 DEEPSEEK_MODEL。")
        return 2

    recorder = ObservationRecorder(args.output_dir)
    exit_status = 0
    for case in selected:
        first_index = recorder.next_run_index(case.id)
        for offset in range(args.repeat):
            built = build_context(case, args.cases_dir.resolve().parent)
            executor = CarrierObservationExecutor(built.envelope)
            try:
                runtime = CarrierLabRuntime.from_environment(model, executor)
            except RuntimeError as error:
                print("Carrier Lab Live 依赖加载失败：%s" % error)
                return 2
            observation = runtime.run(built, first_index + offset)
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
            observations, cases, args.output_dir
        )
    except (IndirectLabError, OSError) as error:
        print("Carrier Lab 报告生成失败：%s" % error)
        return 2
    print("观察矩阵已生成：%s" % markdown_path)
    print("观察数据已生成：%s" % csv_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_cases_argument(command: argparse.ArgumentParser) -> None:
        command.add_argument("--cases-dir", type=Path, default=DEFAULT_CASES_DIR)

    inspect_parser = subparsers.add_parser("inspect", help="检查 Case 和 Provenance Trace")
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
        "--input", type=Path, default=DEFAULT_LIVE_DIR / "live_runs.jsonl"
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
