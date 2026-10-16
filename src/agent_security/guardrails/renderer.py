"""从 GuardrailTrace 生成无时间戳、无绝对路径的确定性报告。"""

import json

from .models import (
    GuardrailEvaluationReport,
    GuardrailStage,
    StageRecord,
    StageStatus,
)


def render_outputs(report: GuardrailEvaluationReport) -> dict[str, str]:
    return {
        "scenario_catalog.md": _catalog(report),
        "defense_matrix.md": _matrix(report),
        "guardrail_traces.md": _traces(report),
        "evaluation_results.json": _json(report),
        "guardrail_pipeline.mmd": _mermaid(),
    }


def _catalog(report: GuardrailEvaluationReport) -> str:
    lines = [
        "# Scenario Catalog",
        "",
        "| Scenario | 场景 | Segment | Replay Tool | Output |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for item in report.scenarios:
        scenario = item.scenario
        tool = scenario.replay.tool_call.name if scenario.replay.tool_call else "-"
        output = "yes" if scenario.replay.output_text is not None else "no"
        lines.append(
            "| %s | %s | %d | %s | %s |"
            % (scenario.id, scenario.title, len(scenario.segments), tool, output)
        )
    lines.extend(
        [
            "",
            "> Replay 是确定性测试输入，不代表真实模型曾在这些内容下提出对应工具调用。",
            "",
        ]
    )
    return "\n".join(lines)


def _matrix(report: GuardrailEvaluationReport) -> str:
    lines = [
        "# Defense Matrix",
        "",
        "| Scenario | Input | Context | Tool Proposal | Output | Pipeline | 验收 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in report.scenarios:
        trace = item.trace
        cells = [_stage_cell(trace.stage(stage)) for stage in GuardrailStage]
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s |"
            % (
                item.scenario.id,
                *cells,
                trace.outcome.value,
                "PASS" if item.passed else "FAIL",
            )
        )
    lines.extend(
        [
            "",
            "通过：%d/%d。" % (report.passed, report.total),
            "",
            "`NOT_RUN` 表示前层已经阻断；`NOT_APPLICABLE` 表示 Scenario 没有该类对象。两者都不等于检查后 `PASS`。",
            "",
        ]
    )
    return "\n".join(lines)


def _traces(report: GuardrailEvaluationReport) -> str:
    lines = ["# Guardrail Traces", ""]
    for evaluation in report.scenarios:
        lines.extend(["## %s" % evaluation.scenario.id, ""])
        for record in evaluation.trace.stages:
            lines.append("- `%s`: %s" % (record.stage.value, _stage_cell(record)))
            for event in record.events:
                evidence = ", ".join(event.evidence) if event.evidence else "-"
                lines.append(
                    "  - `%s` / `%s`; evidence: %s"
                    % (event.reason_code, event.guard_name, evidence)
                )
        lines.extend(
            [
                "- Pipeline: `%s`" % evaluation.trace.outcome.value,
                "- Expected trace: `%s`" % ("matched" if evaluation.passed else "mismatched"),
                "",
            ]
        )
    return "\n".join(lines)


def _json(report: GuardrailEvaluationReport) -> str:
    payload = {
        "summary": {
            "passed": report.passed,
            "total": report.total,
            "strict_passed": report.strict_passed,
            "external_model_calls": 0,
            "real_tool_side_effects": 0,
        },
        "scenarios": [
            {
                "scenario_id": item.scenario.id,
                "passed": item.passed,
                "mismatches": list(item.mismatches),
                "outcome": item.trace.outcome.value,
                "stopped_at": item.trace.stopped_at.value if item.trace.stopped_at else None,
                "stages": [
                    {
                        "stage": record.stage.value,
                        "status": record.status.value,
                        "action": record.action.value if record.action else None,
                        "events": [
                            {
                                "guard_name": event.guard_name,
                                "action": event.action.value,
                                "reason_code": event.reason_code,
                                "evidence": list(event.evidence),
                                "details": dict(event.details),
                            }
                            for event in record.events
                        ],
                    }
                    for record in item.trace.stages
                ],
            }
            for item in report.scenarios
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _stage_cell(record: StageRecord) -> str:
    if record.status is not StageStatus.EXECUTED:
        return record.status.value
    assert record.action is not None
    return record.action.value


def _mermaid() -> str:
    return """flowchart LR
    A[External Content] --> B[Input Guard]
    B -->|PASS or FLAG| C[Context Guard]
    B -->|BLOCK| X[Stop]
    C -->|PASS or FLAG| D[Deterministic Replay]
    C -->|BLOCK| X
    D --> E[Tool Proposal Guard]
    E -->|PASS or N/A| F[Output Guard]
    E -->|BLOCK| X
    F -->|PASS or REDACT| G[Final Result]
    F -->|BLOCK| X
"""
