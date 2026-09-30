"""确定性生成 Case Catalog、Context Trace 和 Mermaid 图。"""

from pathlib import Path
from typing import Dict, Sequence

from .builder import build_context
from .models import BuiltContext, ExperimentCase


GENERATED_NOTICE = "自动生成，请勿手工修改。"


def render_outputs(
    cases: Sequence[ExperimentCase], lesson_root: Path
) -> Dict[str, str]:
    """返回三个确定性文件的文件名和内容。"""

    built_items = tuple(
        build_context(case, lesson_root)
        for case in sorted(cases, key=lambda item: item.id)
    )
    return {
        "case_catalog.md": _render_catalog(cases),
        "context_traces.md": _render_traces(built_items),
        "context_flow.mmd": _render_flow(),
    }


def _render_catalog(cases: Sequence[ExperimentCase]) -> str:
    lines = [
        "# Context Lab Case Catalog",
        "",
        "> %s" % GENERATED_NOTICE,
        "",
        "| Case | 标题 | Channel | Prompt | Wrapper | 公共 Payload |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in sorted(cases, key=lambda item: item.id):
        lines.append(
            "| %s | %s | %s | %s | %s | %s |"
            % (
                case.id,
                case.title,
                case.channel,
                case.prompt_profile,
                case.wrapper,
                case.payload_fixture or "—",
            )
        )
    lines.extend(
        [
            "",
            "所有注入 Case 使用同一份 Payload；Case 只改变声明的入口、包装方式或 Prompt Profile。",
            "",
        ]
    )
    return "\n".join(lines)


def _render_traces(built_items: Sequence[BuiltContext]) -> str:
    lines = [
        "# Context Lab Context Traces",
        "",
        "> %s Trace 只保存哈希和限长预览，不保存隐藏推理。" % GENERATED_NOTICE,
        "",
    ]
    for built in built_items:
        lines.extend(
            [
                "## %s｜%s" % (built.case.id, built.case.title),
                "",
                "| Item | Source | Trust | Intended Role | Transport | SHA-256 | Preview |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in built.trace.items:
            preview = item.content_preview.replace("|", "\\|")
            lines.append(
                "| %s | %s | %s | %s | %s | `%s` | %s |"
                % (
                    item.id,
                    item.source,
                    item.trust,
                    item.intended_role,
                    item.transport,
                    item.content_sha256,
                    preview,
                )
            )
        lines.append("")
    return "\n".join(lines)


def _render_flow() -> str:
    return "\n".join(
        [
            "%% " + GENERATED_NOTICE,
            "flowchart LR",
            '    S["System Prompt<br/>trusted / instruction"] --> C["Agent Context"]',
            '    U["User Task<br/>user_controlled / instruction"] --> C',
            '    Q["Quoted Material<br/>user_controlled / data"] --> C',
            '    W["Webpage<br/>untrusted / data"] --> C',
            '    T["Tool Result<br/>untrusted / tool_output"] --> C',
            '    C --> M["Model Decision"]',
            '    M --> P["ToolCall Proposal"]',
            '    P --> O["Observation Executor<br/>stop before sensitive side effect"]',
            "",
        ]
    )
