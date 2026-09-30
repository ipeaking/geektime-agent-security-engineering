"""从 Live JSONL 生成只包含客观计数的观察矩阵。"""

import csv
import io
import json
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

from .errors import ContextLabError
from .models import ExperimentCase, LiveObservation


HEADERS = (
    "Case",
    "Runs",
    "Completed",
    "Sensitive proposals",
    "read_file proposals",
    "send_diagnostic proposals",
    "Normal fact hits",
    "Errors",
)


def load_observations(path: Path) -> Tuple[LiveObservation, ...]:
    if not path.is_file():
        raise ContextLabError("live observation file does not exist: %s" % path)
    observations = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            observations.append(
                LiveObservation(
                    case_id=str(data["case_id"]),
                    run_index=int(data["run_index"]),
                    provider=str(data["provider"]),
                    model=str(data["model"]),
                    status=str(data["status"]),
                    proposed_tools=tuple(data["proposed_tools"]),
                    first_sensitive_tool=data.get("first_sensitive_tool"),
                    sensitive_tool_proposed=bool(data["sensitive_tool_proposed"]),
                    normal_fact_hits=tuple(data["normal_fact_hits"]),
                    final_answer_preview=data.get("final_answer_preview"),
                    error_type=data.get("error_type"),
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ContextLabError(
                "invalid observation at line %d" % line_number
            ) from error
    return tuple(observations)


def build_observation_matrix(
    observations: Sequence[LiveObservation],
    cases: Sequence[ExperimentCase],
) -> Tuple[str, str]:
    case_map = {case.id: case for case in cases}
    grouped: Dict[str, List[LiveObservation]] = {}
    for observation in observations:
        grouped.setdefault(observation.case_id, []).append(observation)

    rows = []
    for case_id in sorted(grouped):
        items = grouped[case_id]
        case = case_map.get(case_id)
        expected_count = len(items) * (len(case.expected_normal_facts) if case else 0)
        hit_count = sum(len(item.normal_fact_hits) for item in items)
        rows.append(
            (
                case_id,
                len(items),
                sum(item.status == "completed" for item in items),
                sum(item.sensitive_tool_proposed for item in items),
                sum(item.proposed_tools.count("read_file") for item in items),
                sum(item.proposed_tools.count("send_diagnostic") for item in items),
                "%d/%d" % (hit_count, expected_count),
                sum(item.status in {"error", "unknown_tool"} for item in items),
            )
        )

    markdown = [
        "# Context Lab 真实模型观察矩阵",
        "",
        "> 此报告只聚合模型输出和工具提议的客观字段，不使用 LLM Judge。",
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
    cases: Sequence[ExperimentCase],
    output_dir: Path,
) -> Tuple[Path, Path]:
    markdown, csv_text = build_observation_matrix(observations, cases)
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "observation_matrix.md"
    csv_path = output_dir / "observation_matrix.csv"
    markdown_path.write_text(markdown, encoding="utf-8")
    csv_path.write_text(csv_text, encoding="utf-8")
    return markdown_path, csv_path
