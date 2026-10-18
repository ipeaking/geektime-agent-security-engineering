"""生成第 08 讲确定性权限报告。"""

import json

from .models import PermissionReport


def render_outputs(report: PermissionReport) -> dict[str, str]:
    return {
        "tool_manifest.md": _manifest(report),
        "permission_matrix.md": _matrix(report),
        "policy_traces.md": _traces(report),
        "evaluation_results.json": _json(report),
        "permission_flow.mmd": _mermaid(),
    }


def _manifest(report: PermissionReport) -> str:
    lines = [
        "# Tool Permission Manifest",
        "",
        "| Tool | Capabilities | Arguments |",
        "| --- | --- | --- |",
    ]
    for item in report.tools:
        lines.append(
            "| %s | %s | %s |"
            % (
                item.name,
                ", ".join(cap.value for cap in item.capabilities),
                ", ".join(item.required_arguments + item.optional_arguments),
            )
        )
    lines.append("")
    return "\n".join(lines)


def _matrix(report: PermissionReport) -> str:
    lines = [
        "# Tool Permission Matrix",
        "",
        "| Scenario | Subject | Task | Tool | Decision | Reason | Delegated |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in report.runs:
        scenario = item.scenario
        decision = item.execution.decision
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s |"
            % (
                scenario.id,
                scenario.subject_id,
                scenario.task_id,
                scenario.tool_call.name,
                decision.outcome.value,
                decision.reason_code,
                "yes" if item.execution.delegated else "no",
            )
        )
    lines.extend(["", "通过：%d/%d。" % (report.passed, report.total), ""])
    return "\n".join(lines)


def _traces(report: PermissionReport) -> str:
    lines = ["# Policy Traces", ""]
    for item in report.runs:
        lines.extend(["## " + item.scenario.id, ""])
        for check in item.execution.decision.checks:
            lines.append(
                "- `%s`: `%s` (`%s`)"
                % (check.name, check.status.value, check.reason_code)
            )
        lines.extend(
            [
                "- Decision: `%s`" % item.execution.decision.outcome.value,
                "- Delegated: `%s`" % ("yes" if item.execution.delegated else "no"),
                "- Expected result: `%s`" % ("matched" if item.passed else "mismatched"),
                "",
            ]
        )
    return "\n".join(lines)


def _json(report: PermissionReport) -> str:
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
                "subject_id": item.scenario.subject_id,
                "task_id": item.scenario.task_id,
                "tool_name": item.scenario.tool_call.name,
                "decision": item.execution.decision.outcome.value,
                "reason": item.execution.decision.reason_code,
                "delegated": item.execution.delegated,
                "checks": [
                    {
                        "name": check.name,
                        "status": check.status.value,
                        "reason": check.reason_code,
                    }
                    for check in item.execution.decision.checks
                ],
                "passed": item.passed,
            }
            for item in report.runs
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _mermaid() -> str:
    return """flowchart LR
    A[Candidate ToolCall] --> B[PolicyEnforcedToolExecutor]
    C[Trusted Subject] --> B
    D[Task Contract] --> B
    B --> E[Build Immutable Request]
    E --> F[Tool Permission Policy]
    F -->|ALLOW| G[Recording Delegate]
    F -->|DENY| H[Stop]
"""
