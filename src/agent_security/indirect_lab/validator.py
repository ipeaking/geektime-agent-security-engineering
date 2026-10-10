"""验证 8 个载体 Case 的配对关系和 Payload 提取结果。"""

from pathlib import Path
from typing import Sequence

from agent_security.content_pipeline.base import normalize_text, resolve_source

from .builder import build_context
from .models import CarrierCase, ValidationIssue


EXPECTED_LAYOUT = {
    "CASE-01": ("web", "clean"),
    "CASE-02": ("web", "injected"),
    "CASE-03": ("pdf", "clean"),
    "CASE-04": ("pdf", "injected"),
    "CASE-05": ("email", "clean"),
    "CASE-06": ("email", "injected"),
    "CASE-07": ("rag_document", "clean"),
    "CASE-08": ("rag_document", "injected"),
}
PAIRS = (("CASE-01", "CASE-02"), ("CASE-03", "CASE-04"), ("CASE-05", "CASE-06"), ("CASE-07", "CASE-08"))


def validate_cases(cases: Sequence[CarrierCase], lesson_root: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    def add(code: str, location: str, message: str) -> None:
        issues.append(ValidationIssue(code, location, message))

    by_id = {case.id: case for case in cases}
    if set(by_id) != set(EXPECTED_LAYOUT):
        add("IL001", "cases", "Case 编号必须恰好是 CASE-01 至 CASE-08")
    for case_id, expected in EXPECTED_LAYOUT.items():
        case = by_id.get(case_id)
        if case and (case.carrier, case.variant) != expected:
            add("IL002", case_id, "carrier 和 variant 与实验设计不一致")

    injected = [case for case in cases if case.variant == "injected"]
    payload_paths = {case.payload_fixture for case in injected}
    if None in payload_paths or len(payload_paths) != 1:
        add("IL003", "cases", "四个 Injected Case 必须引用同一 Payload")
    for case in cases:
        if case.variant == "clean" and case.payload_fixture is not None:
            add("IL004", case.id, "Clean Case 不能引用 Payload")
        visible_ref = case.model_source_ref.casefold()
        if (
            "clean" in visible_ref
            or "injected" in visible_ref
            or "fixtures" in visible_ref
            or "/" in case.model_source_ref
            or "\\" in case.model_source_ref
        ):
            add("IL011", case.id, "模型可见来源必须是中性名称且不能包含 Fixture 路径")

    tasks = {case.task for case in cases}
    facts = {case.expected_normal_facts for case in cases}
    if len(tasks) != 1 or len(facts) != 1:
        add("IL005", "cases", "八个 Case 必须共享任务和正常事实")

    payload_path = next((path for path in payload_paths if path), None)
    payload = ""
    if payload_path:
        payload = resolve_source(lesson_root, payload_path).read_text(encoding="utf-8")
    for clean_id, injected_id in PAIRS:
        clean = by_id.get(clean_id)
        attack = by_id.get(injected_id)
        if not clean or not attack:
            continue
        if (
            clean.carrier != attack.carrier
            or clean.task != attack.task
            or clean.media_type != attack.media_type
            or clean.model_source_ref != attack.model_source_ref
            or clean.retrieval_query != attack.retrieval_query
            or clean.expected_normal_facts != attack.expected_normal_facts
        ):
            add("IL006", injected_id, "载体配对只能改变 Fixture 和 Payload")
            continue
        try:
            clean_content = normalize_text(build_context(clean, lesson_root).envelope.content)
            attack_content = normalize_text(build_context(attack, lesson_root).envelope.content)
        except Exception as error:
            add("IL007", injected_id, "Adapter 解析失败：%s" % error)
            continue
        normalized_payload = normalize_text(payload)
        if normalized_payload and normalized_payload in clean_content:
            add("IL008", clean_id, "Clean 内容包含公共 Payload")
        if normalized_payload and normalized_payload not in attack_content:
            add("IL009", injected_id, "Injected 内容未提取出公共 Payload")
        if clean_content not in attack_content:
            add("IL010", injected_id, "Injected 内容没有完整保留 Clean 正常内容")
    return sorted(issues, key=lambda issue: (issue.location, issue.code))
