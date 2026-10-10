"""确定性生成 Carrier Lab 的目录、来源 Trace、矩阵与流程图。"""

from pathlib import Path
from typing import Sequence

from .builder import build_context
from .models import BuiltCarrierContext, CarrierCase


GENERATED_NOTICE = "自动生成，请勿手工修改。"


def render_outputs(
    cases: Sequence[CarrierCase], lesson_root: Path
) -> dict[str, str]:
    built_items = tuple(
        build_context(case, lesson_root)
        for case in sorted(cases, key=lambda item: item.id)
    )
    return {
        "case_catalog.md": _render_catalog(cases),
        "provenance_traces.md": _render_traces(built_items),
        "carrier_matrix.md": _render_matrix(built_items),
        "content_pipeline.mmd": _render_flow(),
    }


def _render_catalog(cases: Sequence[CarrierCase]) -> str:
    lines = [
        "# Carrier Lab Case Catalog",
        "",
        "> %s" % GENERATED_NOTICE,
        "",
        "| Case | 标题 | Carrier | Variant | Fixture | 公共 Payload |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in sorted(cases, key=lambda item: item.id):
        lines.append(
            "| %s | %s | %s | %s | `%s` | %s |"
            % (
                case.id,
                case.title,
                case.carrier,
                case.variant,
                case.source_fixture,
                "`%s`" % case.payload_fixture if case.payload_fixture else "—",
            )
        )
    lines.extend(
        [
            "",
            "每种载体包含一个 Clean Case 和一个 Injected Case；四个 Injected Case 共用同一份 Payload。",
            "",
        ]
    )
    return "\n".join(lines)


def _render_traces(built_items: Sequence[BuiltCarrierContext]) -> str:
    lines = [
        "# Carrier Lab Provenance Traces",
        "",
        "> %s Trace 只保存哈希和限长预览，不保存隐藏推理。" % GENERATED_NOTICE,
        "",
    ]
    for built in built_items:
        lines.extend(
            [
                "## %s｜%s" % (built.case.id, built.case.title),
                "",
                "| Item | Source Type | Source Ref | Trust | Role | Parser | Transport | Content SHA-256 | Preview |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in built.trace.items:
            lines.append(
                "| %s | %s | `%s` | %s | %s | %s | %s | `%s` | %s |"
                % (
                    item.id,
                    item.source_type,
                    item.source_ref,
                    item.trust,
                    item.intended_role,
                    item.parser,
                    item.transport,
                    item.content_sha256,
                    item.content_preview.replace("|", "\\|"),
                )
            )
        lines.append("")
    return "\n".join(lines)


def _render_matrix(built_items: Sequence[BuiltCarrierContext]) -> str:
    lines = [
        "# Carrier Lab Deterministic Matrix",
        "",
        "> %s 该矩阵验证内容管线，不包含真实模型结论。" % GENERATED_NOTICE,
        "",
        "| Case | Carrier | Variant | Parser | 正常事实 | Payload | Source Ref |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for built in built_items:
        content = built.envelope.content.casefold()
        facts_present = all(
            fact.casefold() in content for fact in built.case.expected_normal_facts
        )
        lines.append(
            "| %s | %s | %s | %s | %s | %s | `%s` |"
            % (
                built.case.id,
                built.case.carrier,
                built.case.variant,
                built.envelope.parser,
                "present" if facts_present else "missing",
                "present" if built.case.variant == "injected" else "absent",
                built.envelope.source_ref,
            )
        )
    lines.append("")
    return "\n".join(lines)


def _render_flow() -> str:
    return "\n".join(
        [
            "%% " + GENERATED_NOTICE,
            "flowchart LR",
            '    W["Web HTML"] --> A["Content Adapter"]',
            '    P["PDF"] --> A',
            '    E["Email"] --> A',
            '    R["RAG Document"] --> A',
            '    A --> C["ContentEnvelope<br/>content + provenance"]',
            '    C --> T["load_content Tool Result"]',
            '    T --> M["Model"]',
            '    M --> O["ToolCall Proposal"]',
            '    O --> X["Observation Executor<br/>stop before sensitive side effect"]',
            "",
        ]
    )
