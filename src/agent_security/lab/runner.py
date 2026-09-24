"""第 01 讲 Prompt Injection 实验的命令行 Runner。"""

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Sequence
from uuid import uuid4

from agent_security.agent import DeterministicReplayRuntime
from agent_security.audit import AuditLogger
from agent_security.tools import (
    FetchWebpageTool,
    ReadFileTool,
    SendDiagnosticTool,
    ToolExecutor,
    ToolRegistry,
)

from .server import LocalLabServer


def run_case(
    case_name: str,
    repository_root: Path,
    output_dir: Optional[Path] = None,
    provider: str = "replay",
    model: Optional[str] = None,
) -> Dict[str, Any]:
    lab_root = repository_root / "labs" / "lesson_01_prompt_injection"
    case_path = lab_root / "cases" / (case_name + ".json")
    case_data = json.loads(case_path.read_text(encoding="utf-8"))

    if output_dir is None:
        output_dir = repository_root / ".lab-output"
    output_dir.mkdir(parents=True, exist_ok=True)

    audit_path = output_dir / "audit.jsonl"
    diagnostic_path = output_dir / "diagnostic.jsonl"
    for path in (audit_path, diagnostic_path):
        if path.exists():
            path.unlink()

    pages_root = lab_root / "fixtures" / "pages"
    workspace_template_path = (
        lab_root / "fixtures" / "workspace" / "demo-config.template.json"
    )
    workspace_data = json.loads(workspace_template_path.read_text(encoding="utf-8"))
    runtime_canary = "COURSE-CANARY-%s" % uuid4().hex
    workspace_data["canary"] = runtime_canary
    workspace_root = output_dir / "runtime-workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "demo-config.json").write_text(
        json.dumps(workspace_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with LocalLabServer(pages_root) as server:
        audit = AuditLogger(audit_path)
        registry = ToolRegistry()
        registry.register(FetchWebpageTool())
        registry.register(ReadFileTool(workspace_root))
        registry.register(SendDiagnosticTool(server.base_url + "/diagnostic"))

        executor = ToolExecutor(registry, audit)
        if provider == "replay":
            replay_path = lab_root / "replay" / (case_name + ".json")
            replay_steps = json.loads(replay_path.read_text(encoding="utf-8"))
            agent = DeterministicReplayRuntime(executor, replay_steps)
        elif provider == "deepseek":
            from agent_security.agent.deepseek_runtime import DeepSeekResponsesAgentRuntime

            if not model:
                raise ValueError("live mode requires --model or DEEPSEEK_MODEL")
            agent = DeepSeekResponsesAgentRuntime.from_environment(model, executor)
        else:
            raise ValueError("unknown model provider: %s" % provider)
        page_url = server.base_url + "/pages/" + str(case_data["page"])
        result = agent.run(str(case_data["task"]), page_url)

        with diagnostic_path.open("w", encoding="utf-8") as stream:
            for diagnostic in server.diagnostics:
                stream.write(json.dumps(diagnostic, ensure_ascii=False) + "\n")

        return {
            "case": case_name,
            "provider": provider,
            "model": model,
            "task": case_data["task"],
            "answer": result.answer,
            "tool_calls": [call.name for call in result.tool_calls],
            "diagnostics_received": list(server.diagnostics),
            "runtime_canary": runtime_canary,
            "audit_path": str(audit_path),
            "diagnostic_path": str(diagnostic_path),
        }


def load_project_environment(repository_root: Path) -> None:
    """从项目根目录的 .env 文件加载可选的 Live 模式配置。"""

    try:
        from dotenv import load_dotenv
    except ImportError as error:
        raise RuntimeError(
            "live mode requires optional dependencies: "
            "python -m pip install -e '.[deepseek]'"
        ) from error

    load_dotenv(repository_root / ".env")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("normal", "attack"), default="attack")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--provider",
        choices=("replay", "deepseek"),
        default="replay",
        help="replay is deterministic; deepseek performs a live-model observation",
    )
    parser.add_argument(
        "--model",
        default=None,
    )
    args = parser.parse_args(argv)

    repository_root = Path.cwd()
    if not (repository_root / "labs" / "lesson_01_prompt_injection").is_dir():
        parser.error("run this command from the repository root")
    selected_model = args.model
    if args.provider == "deepseek":
        try:
            load_project_environment(repository_root)
        except RuntimeError as error:
            parser.error(str(error))
        if not os.environ.get("DEEPSEEK_API_KEY"):
            parser.error(
                "deepseek provider requires DEEPSEEK_API_KEY in the repository-root .env"
            )
        selected_model = selected_model or os.environ.get("DEEPSEEK_MODEL")
        if not selected_model:
            parser.error(
                "deepseek provider requires --model or DEEPSEEK_MODEL in .env"
            )

    summary = run_case(
        args.case,
        repository_root,
        args.output_dir,
        provider=args.provider,
        model=selected_model,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
