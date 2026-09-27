"""检查威胁模型的引用、覆盖关系以及与代码的偏移。"""

from collections import Counter
from pathlib import Path
from typing import Iterable, List, Mapping, Set

from agent_security.agent.deepseek_runtime import LIVE_TOOLS

from .models import ThreatModel, ValidationIssue


def validate_threat_model(
    model: ThreatModel,
    repository_root: Path,
) -> List[ValidationIssue]:
    """返回全部问题；空列表表示校验通过。"""

    issues: List[ValidationIssue] = []

    def add(code: str, location: str, message: str) -> None:
        issues.append(ValidationIssue(code, "error", location, message))

    if model.schema_version != "1.0":
        add("TM001", "schema_version", "仅支持 schema_version 1.0")

    groups = {
        "system": (model.system,),
        "assumptions": model.assumptions,
        "actors": model.actors,
        "components": model.components,
        "assets": model.assets,
        "trust_boundaries": model.trust_boundaries,
        "data_flows": model.data_flows,
        "threats": model.threats,
        "requirements": model.requirements,
        "verifications": model.verifications,
    }
    all_ids = [item.id for items in groups.values() for item in items]
    for item_id, count in sorted(Counter(all_ids).items()):
        if count > 1:
            add("TM002", item_id, "编号在整个模型中重复出现 %d 次" % count)

    expected_prefixes = {
        "system": "SYS-",
        "assumptions": "ASM-",
        "actors": "ACT-",
        "components": "CMP-",
        "assets": "AST-",
        "trust_boundaries": "TB-",
        "data_flows": "DF-",
        "threats": "THR-",
        "requirements": "SR-",
        "verifications": "VER-",
    }
    for group_name, items in groups.items():
        prefix = expected_prefixes[group_name]
        for item in items:
            if not item.id.startswith(prefix):
                add("TM003", item.id, "编号应以 %s 开头" % prefix)

    actor_ids = {item.id for item in model.actors}
    component_ids = {item.id for item in model.components}
    asset_ids = {item.id for item in model.assets}
    boundary_ids = {item.id for item in model.trust_boundaries}
    flow_ids = {item.id for item in model.data_flows}
    threat_ids = {item.id for item in model.threats}
    requirement_ids = {item.id for item in model.requirements}
    endpoints = actor_ids | component_ids

    _check_refs(issues, "TM010", model.system.id, "in_scope", model.system.in_scope, component_ids)

    for component in model.components:
        for code_ref in component.code_refs:
            target = (repository_root / code_ref).resolve()
            try:
                target.relative_to(repository_root.resolve())
            except ValueError:
                add("TM011", component.id, "源码引用逃出仓库：%s" % code_ref)
                continue
            if not target.is_file():
                add("TM011", component.id, "源码引用不存在：%s" % code_ref)

    for flow in model.data_flows:
        _check_refs(issues, "TM020", flow.id, "source", (flow.source,), endpoints)
        _check_refs(issues, "TM020", flow.id, "destination", (flow.destination,), endpoints)
        _check_refs(issues, "TM021", flow.id, "assets", flow.assets, asset_ids)
        _check_refs(issues, "TM022", flow.id, "crosses", flow.crosses, boundary_ids)

    for threat in model.threats:
        _check_refs(issues, "TM030", threat.id, "sources", threat.sources, endpoints)
        _check_refs(issues, "TM031", threat.id, "entry_flows", threat.entry_flows, flow_ids)
        _check_refs(issues, "TM032", threat.id, "affected_assets", threat.affected_assets, asset_ids)
        _check_refs(issues, "TM033", threat.id, "affected_components", threat.affected_components, component_ids)
        _check_refs(issues, "TM034", threat.id, "trust_boundaries", threat.trust_boundaries, boundary_ids)
        _check_refs(issues, "TM035", threat.id, "attack_flows", threat.attack_flows, flow_ids)
        if threat.priority not in {"P0", "P1", "P2"}:
            add("TM036", threat.id, "priority 必须是 P0、P1 或 P2")
        for field_name, value in (
            ("impact_confidentiality", threat.impact_confidentiality),
            ("impact_integrity", threat.impact_integrity),
            ("impact_availability", threat.impact_availability),
            ("likelihood", threat.likelihood),
        ):
            if value not in {"low", "medium", "high"}:
                add("TM037", threat.id, "%s 必须是 low、medium 或 high" % field_name)

    for requirement in model.requirements:
        _check_refs(issues, "TM040", requirement.id, "derived_from", requirement.derived_from, threat_ids)

    for verification in model.verifications:
        _check_refs(
            issues,
            "TM041",
            verification.id,
            "verifies_requirements",
            verification.verifies_requirements,
            requirement_ids,
        )

    for threat in model.threats:
        if threat.priority not in {"P0", "P1"}:
            continue
        derived = {
            requirement.id
            for requirement in model.requirements
            if threat.id in requirement.derived_from
        }
        if not derived:
            add("TM050", threat.id, "P0/P1 威胁没有推导出安全需求")
            continue
        verified = {
            requirement_id
            for verification in model.verifications
            for requirement_id in verification.verifies_requirements
        }
        if not derived & verified:
            add("TM051", threat.id, "P0/P1 威胁的安全需求没有验证计划")

    documented_tools = {
        component.tool_name
        for component in model.components
        if component.kind == "tool" and component.tool_name
    }
    runtime_tools = {str(tool["name"]) for tool in LIVE_TOOLS}
    if documented_tools != runtime_tools:
        add(
            "TM060",
            "components",
            "工具清单与 LIVE_TOOLS 不一致；模型=%s，代码=%s"
            % (sorted(documented_tools), sorted(runtime_tools)),
        )

    return sorted(issues, key=lambda issue: (issue.location, issue.code, issue.message))


def _check_refs(
    issues: List[ValidationIssue],
    code: str,
    location: str,
    field_name: str,
    references: Iterable[str],
    known_ids: Set[str],
) -> None:
    for reference in references:
        if reference not in known_ids:
            issues.append(
                ValidationIssue(
                    code=code,
                    severity="error",
                    location=location,
                    message="%s 引用了不存在的编号：%s" % (field_name, reference),
                )
            )
