"""生成不包含合成敏感值的确定性 Tool Risk 报告。"""

import json

from .models import ToolRiskReport


def render_outputs(report: ToolRiskReport) -> dict[str, str]:
    return {
        "tool_catalog.md": _tools(report),
        "risk_matrix.md": _matrix(report),
        "replay_traces.md": _traces(report),
        "evaluation_results.json": _json(report),
        "tool_risk_flow.mmd": _mermaid(),
    }


def _tools(report: ToolRiskReport) -> str:
    lines = [
        "# Tool Catalog",
        "",
        "| Tool | Effect | Implementation |",
        "| --- | --- | --- |",
    ]
    for item in report.tools:
        lines.append("| %s | %s | synthetic in-memory |" % (item.name, item.effect.value))
    lines.extend(
        [
            "",
            "> 所有工具都由 SyntheticToolEnvironment 实现，不访问真实文件、邮箱、数据库或 Shell。",
            "",
        ]
    )
    return "\n".join(lines)


def _matrix(report: ToolRiskReport) -> str:
    lines = [
        "# Tool Risk Matrix",
        "",
        "| Scenario | Proposed | Executed | Effects | Canary at Sink | 验收 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in report.runs:
        lines.append(
            "| %s | %s | %s | %s | %s | %s |"
            % (
                item.scenario.id,
                ", ".join(item.proposed_tools) or "-",
                ", ".join(item.executed_tools) or "-",
                ", ".join(event.effect.value for event in item.events) or "-",
                "yes" if item.canary_reached_sink else "no",
                "PASS" if item.passed else "FAIL",
            )
        )
    lines.extend(["", "通过：%d/%d。" % (report.passed, report.total), ""])
    return "\n".join(lines)


def _traces(report: ToolRiskReport) -> str:
    lines = ["# Replay Traces", ""]
    for item in report.runs:
        lines.extend(
            [
                "## " + item.scenario.id,
                "",
                "- Fixture SHA-256 retained: `yes`",
                "- Proposed tools: `%s`" % (", ".join(item.proposed_tools) or "none"),
                "- Executed tools: `%s`" % (", ".join(item.executed_tools) or "none"),
                "- Canary reached synthetic sink: `%s`"
                % ("yes" if item.canary_reached_sink else "no"),
                "- Events:",
            ]
        )
        if item.events:
            for event in item.events:
                lines.append(
                    "  - `%s` / `%s` / `%s`"
                    % (event.tool_name, event.effect.value, event.evidence)
                )
        else:
            lines.append("  - none")
        lines.extend(["- Expected result: `%s`" % ("matched" if item.passed else "mismatched"), ""])
    return "\n".join(lines)


def _json(report: ToolRiskReport) -> str:
    payload = {
        "summary": {
            "passed": report.passed,
            "total": report.total,
            "strict_passed": report.strict_passed,
            "external_model_calls": 0,
            "network_calls": 0,
            "real_tool_side_effects": 0,
        },
        "scenarios": [
            {
                "scenario_id": item.scenario.id,
                "proposed_tools": list(item.proposed_tools),
                "executed_tools": list(item.executed_tools),
                "effects": [event.effect.value for event in item.events],
                "canary_reached_sink": item.canary_reached_sink,
                "fixture_sha256_retained": True,
                "passed": item.passed,
                "mismatches": list(item.mismatches),
            }
            for item in report.runs
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _mermaid() -> str:
    return """flowchart LR
    A[Untrusted Content] --> B[Candidate ToolCalls]
    B --> C[Synthetic Tool Executor]
    C --> D[File Read or Write]
    C --> E[Local Outbox]
    C --> F[Synthetic Database]
    C --> G[Shell Recorder]
    D --> H[Observable Effects]
    E --> H
    F --> H
    G --> H
"""
