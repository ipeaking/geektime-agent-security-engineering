"""检查六个 Context Lab Case 是否保持控制变量。"""

from pathlib import Path
from typing import List, Sequence

from .loader import resolve_fixture
from .models import CaseValidationIssue, ExperimentCase


EXPECTED_CASE_IDS = {
    "CASE-01",
    "CASE-02",
    "CASE-03",
    "CASE-04",
    "CASE-05",
    "CASE-06",
}


def validate_cases(
    cases: Sequence[ExperimentCase], lesson_root: Path
) -> List[CaseValidationIssue]:
    issues: List[CaseValidationIssue] = []

    def add(code: str, location: str, message: str) -> None:
        issues.append(CaseValidationIssue(code, location, message))

    by_id = {case.id: case for case in cases}
    if set(by_id) != EXPECTED_CASE_IDS:
        add(
            "CL001",
            "cases",
            "Case 编号必须恰好是 CASE-01 至 CASE-06",
        )

    injection_cases = [case for case in cases if case.channel != "clean_web"]
    payload_paths = {case.payload_fixture for case in injection_cases}
    if None in payload_paths or len(payload_paths) != 1:
        add("CL002", "cases", "所有注入 Case 必须引用同一份公共 Payload")

    clean_cases = [case for case in cases if case.channel == "clean_web"]
    for case in clean_cases:
        if case.payload_fixture is not None:
            add("CL003", case.id, "Clean Case 不能引用注入 Payload")
        if case.wrapper != "none":
            add("CL004", case.id, "Clean Case 不能应用 Payload Wrapper")

    payload_text = ""
    payload_path = next((path for path in payload_paths if path is not None), None)
    if payload_path is not None:
        payload_text = resolve_fixture(lesson_root, payload_path).read_text(
            encoding="utf-8"
        )
    for case in clean_cases:
        if case.page_fixture and payload_text:
            clean_content = resolve_fixture(
                lesson_root, case.page_fixture
            ).read_text(encoding="utf-8")
            if payload_text.strip() in clean_content:
                add("CL005", case.id, "Clean Case 页面包含公共注入 Payload")

    for case in cases:
        if case.page_fixture is None:
            add("CL006", case.id, "当前六个 Case 都必须提供页面或引用材料 Fixture")
        if case.channel == "inline_quoted_content" and case.wrapper != "none":
            add("CL007", case.id, "Inline Quoted Case 不能额外应用网页 Wrapper")
        if case.channel == "webpage" and case.id != "CASE-06" and case.prompt_profile != "neutral":
            add("CL008", case.id, "网页包装对照组必须使用 neutral Prompt")

    baseline = by_id.get("CASE-03")
    for case_id in ("CASE-04", "CASE-05"):
        candidate = by_id.get(case_id)
        if baseline and candidate:
            if (
                candidate.task != baseline.task
                or candidate.page_fixture != baseline.page_fixture
                or candidate.payload_fixture != baseline.payload_fixture
                or candidate.prompt_profile != baseline.prompt_profile
                or candidate.expected_normal_facts != baseline.expected_normal_facts
            ):
                add("CL009", case_id, "网页 Wrapper 对照组只能改变 wrapper")

    explicit = by_id.get("CASE-06")
    if baseline and explicit:
        if (
            explicit.task != baseline.task
            or explicit.page_fixture != baseline.page_fixture
            or explicit.payload_fixture != baseline.payload_fixture
            or explicit.wrapper != baseline.wrapper
            or explicit.expected_normal_facts != baseline.expected_normal_facts
        ):
            add("CL010", "CASE-06", "显式边界对照组只能改变 prompt_profile")
        if explicit.prompt_profile != "explicit_boundary":
            add("CL011", "CASE-06", "CASE-06 必须使用 explicit_boundary Prompt")

    for case in injection_cases:
        if case.page_fixture:
            template = resolve_fixture(lesson_root, case.page_fixture).read_text(
                encoding="utf-8"
            )
            if "{{INJECTION_PAYLOAD}}" not in template:
                add("CL012", case.id, "注入 Fixture 缺少公共 Payload 占位符")

    return sorted(issues, key=lambda issue: (issue.location, issue.code))
