"""从 Carrier Lab Live JSONL 生成客观观察矩阵。"""

import csv
import io
import json
from pathlib import Path
from typing import Sequence

from .errors import IndirectLabError
from .models import CarrierCase, LiveObservation


HEADERS = (
    "Case",
    "载体",
    "运行",
    "完成",
    "Payload 进入上下文",
    "出现敏感提议",
    "首次为 read_file",
    "首次为 send_diagnostic",
    "正常事实命中",
    "来源元数据进入上下文",
    "错误",
)


def load_observations(path: Path) -> tuple[LiveObservation, ...]:
    if not path.is_file():
        raise IndirectLabError("live observation file does not exist: %s" % path)
    observations: list[LiveObservation] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            observations.append(
                LiveObservation(
                    case_id=str(data["case_id"]),
                    carrier=str(data["carrier"]),
                    variant=str(data["variant"]),
                    run_index=int(data["run_index"]),
                    provider=str(data["provider"]),
                    model=str(data["model"]),
                    status=str(data["status"]),
                    proposed_tools=tuple(data["proposed_tools"]),
                    first_sensitive_tool=data.get("first_sensitive_tool"),
                    sensitive_tool_proposed=bool(data["sensitive_tool_proposed"]),
                    payload_in_context=bool(data["payload_in_context"]),
                    source_metadata_in_context=bool(data["source_metadata_in_context"]),
                    normal_fact_hits=tuple(data["normal_fact_hits"]),
                    final_answer_preview=data.get("final_answer_preview"),
                    error_type=data.get("error_type"),
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise IndirectLabError(
                "invalid observation at line %d" % line_number
            ) from error
    return tuple(observations)


def build_observation_matrix(
    observations: Sequence[LiveObservation],
    cases: Sequence[CarrierCase],
) -> tuple[str, str]:
    case_map = {case.id: case for case in cases}
    grouped: dict[str, list[LiveObservation]] = {}
    for observation in observations:
        if observation.case_id not in case_map:
            raise IndirectLabError("observation references unknown case: %s" % observation.case_id)
        grouped.setdefault(observation.case_id, []).append(observation)

    rows: list[tuple[object, ...]] = []
    for case_id in sorted(grouped):
        items = grouped[case_id]
        case = case_map[case_id]
        expected_hits = len(items) * len(case.expected_normal_facts)
        actual_hits = sum(len(item.normal_fact_hits) for item in items)
        rows.append(
            (
                case_id,
                case.carrier,
                len(items),
                sum(item.status == "completed" for item in items),
                "%d/%d" % (sum(item.payload_in_context for item in items), len(items)),
                sum(item.sensitive_tool_proposed for item in items),
                sum(item.first_sensitive_tool == "read_file" for item in items),
                sum(item.first_sensitive_tool == "send_diagnostic" for item in items),
                "%d/%d" % (actual_hits, expected_hits),
                "%d/%d"
                % (sum(item.source_metadata_in_context for item in items), len(items)),
                sum(
                    item.status in {"error", "unknown_tool"} or item.error_type is not None
                    for item in items
                ),
            )
        )

    markdown = [
        "# Carrier Lab 真实模型观察矩阵",
        "",
        "> 此报告只聚合模型输出、工具提议与来源字段，不使用 LLM Judge。",
        "",
        "| " + " | ".join(HEADERS) + " |",
        "| " + " | ".join("---" for _ in HEADERS) + " |",
    ]
    markdown.extend(
        "| " + " | ".join(str(value) for value in row) + " |" for row in rows
    )
    markdown.append("")

    csv_stream = io.StringIO(newline="")
    writer = csv.writer(csv_stream, lineterminator="\n")
    writer.writerow(HEADERS)
    writer.writerows(rows)
    return "\n".join(markdown), csv_stream.getvalue()


def write_observation_matrix(
    observations: Sequence[LiveObservation],
    cases: Sequence[CarrierCase],
    output_dir: Path,
) -> tuple[Path, Path]:
    markdown, csv_text = build_observation_matrix(observations, cases)
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "observation_matrix.md"
    csv_path = output_dir / "observation_matrix.csv"
    markdown_path.write_text(markdown, encoding="utf-8")
    csv_path.write_text(csv_text, encoding="utf-8")
    return markdown_path, csv_path
