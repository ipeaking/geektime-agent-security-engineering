"""校验、生成和检查第 02 讲威胁模型报告。"""

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from .loader import ModelLoadError, load_threat_model
from .renderer import render_report
from .validator import validate_threat_model


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "render", "check"))
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-file", type=Path)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    repository_root = args.repository_root.resolve()
    model_dir = args.model_dir.resolve()

    try:
        model = load_threat_model(model_dir)
    except ModelLoadError as error:
        print("加载失败：%s" % error, file=sys.stderr)
        return 2

    issues = validate_threat_model(model, repository_root)
    if issues:
        for issue in issues:
            print("[%s] %s %s: %s" % (issue.severity, issue.code, issue.location, issue.message), file=sys.stderr)
        print("威胁模型校验失败，共 %d 个问题。" % len(issues), file=sys.stderr)
        return 1

    if args.command == "validate":
        print("威胁模型校验通过：%d 个威胁，%d 条安全需求。" % (len(model.threats), len(model.requirements)))
        return 0

    if args.output_file is None:
        parser.error("render 和 check 必须提供 --output-file")
    output_file = args.output_file.resolve()
    rendered = render_report(model)

    if args.command == "render":
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(rendered, encoding="utf-8")
        print("已生成威胁模型报告：%s" % output_file)
        return 0

    if not output_file.is_file() or output_file.read_text(encoding="utf-8") != rendered:
        print("威胁模型报告不存在或已经过期，请先运行 render。", file=sys.stderr)
        return 1
    print("威胁模型报告与结构化模型一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
