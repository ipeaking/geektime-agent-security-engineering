"""把结构化威胁模型渲染成人可以阅读的 Markdown 报告。"""

from typing import Dict, Iterable, List, Sequence

from .models import ThreatModel


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _join(values: Iterable[str]) -> str:
    items = tuple(values)
    return "、".join(items) if items else "—"


def _statements(values: Iterable[str]) -> str:
    items = tuple(value.rstrip("。；") for value in values)
    return "；".join(items) + ("。" if items else "—")


def _table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> List[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
    return lines


def _mermaid_label(value: str) -> str:
    return value.replace('"', "'").replace("\n", " ")


def render_report(model: ThreatModel) -> str:
    """生成内容稳定、可由测试比较的 Markdown。"""

    names: Dict[str, str] = {
        item.id: item.name
        for items in (model.actors, model.components)
        for item in items
    }
    requirements_by_threat = {
        threat.id: sorted(
            requirement.id
            for requirement in model.requirements
            if threat.id in requirement.derived_from
        )
        for threat in model.threats
    }
    verifications_by_requirement = {
        requirement.id: sorted(
            verification.id
            for verification in model.verifications
            if requirement.id in verification.verifies_requirements
        )
        for requirement in model.requirements
    }

    lines = [
        "# 第 02 讲威胁模型报告",
        "",
        "> 此文件由 `python -m agent_security.threat_model render` 自动生成，请修改 `model/*.toml`，不要直接编辑本文件。",
        "",
        "## 系统与范围",
        "",
        "- 系统：%s（`%s`）" % (model.system.name, model.system.id),
        "- 代码基线：`%s`" % model.system.baseline_tag,
        "- 说明：%s" % model.system.description,
        "- 范围内组件：%s" % _join(model.system.in_scope),
        "- 暂不讨论：%s" % _join(model.system.out_of_scope_topics),
        "",
        "### 建模假设",
        "",
    ]
    lines.extend("- `%s`：%s" % (item.id, item.statement) for item in sorted(model.assumptions, key=lambda x: x.id))

    lines.extend(["", "## 参与者", ""])
    lines.extend(_table(("编号", "名称", "信任级别", "说明"), ((x.id, x.name, x.trust, x.description) for x in sorted(model.actors, key=lambda x: x.id))))

    lines.extend(["", "## 组件", ""])
    lines.extend(
        _table(
            ("编号", "名称", "类型", "信任级别", "说明", "源码位置"),
            (
                (x.id, x.name, x.kind, x.trust, x.description, _join(x.code_refs))
                for x in sorted(model.components, key=lambda x: x.id)
            ),
        )
    )

    lines.extend(["", "## 资产", ""])
    lines.extend(_table(("编号", "名称", "分类", "说明"), ((x.id, x.name, x.classification, x.description) for x in sorted(model.assets, key=lambda x: x.id))))

    lines.extend(["", "## 信任边界", ""])
    lines.extend(_table(("编号", "名称", "说明"), ((x.id, x.name, x.description) for x in sorted(model.trust_boundaries, key=lambda x: x.id))))

    lines.extend(["", "## 数据流", ""])
    lines.extend(
        _table(
            ("编号", "数据流", "来源 → 去向", "通道", "携带资产", "跨越边界", "说明"),
            (
                (
                    x.id,
                    x.name,
                    "%s → %s" % (x.source, x.destination),
                    x.channel,
                    _join(x.assets),
                    _join(x.crosses),
                    x.description,
                )
                for x in sorted(model.data_flows, key=lambda x: x.id)
            ),
        )
    )
    lines.extend(["", "```mermaid", "flowchart LR"])
    for endpoint_id, name in sorted(names.items()):
        lines.append('    %s["%s<br/>%s"]' % (endpoint_id.replace("-", "_"), endpoint_id, _mermaid_label(name)))
    for flow in sorted(model.data_flows, key=lambda x: x.id):
        lines.append(
            '    %s -->|"%s %s"| %s'
            % (
                flow.source.replace("-", "_"),
                flow.id,
                _mermaid_label(flow.name),
                flow.destination.replace("-", "_"),
            )
        )
    lines.extend(
        [
            "```",
            "",
            "## 威胁总览",
            "",
            "> 本实验中的 P1 表示后续课程需要优先补上的架构缺口，不表示受控教学环境已经发生真实生产事故。",
            "",
        ]
    )
    lines.extend(
        _table(
            ("编号", "威胁", "优先级", "机密性/完整性/可用性", "可能性", "安全需求"),
            (
                (
                    x.id,
                    x.title,
                    x.priority,
                    "%s/%s/%s" % (x.impact_confidentiality, x.impact_integrity, x.impact_availability),
                    x.likelihood,
                    _join(requirements_by_threat[x.id]),
                )
                for x in sorted(model.threats, key=lambda x: x.id)
            ),
        )
    )

    lines.extend(["", "## 威胁详情", ""])
    for threat in sorted(model.threats, key=lambda x: x.id):
        lines.extend(
            [
                "### %s｜%s" % (threat.id, threat.title),
                "",
                threat.description,
                "",
                "- 攻击来源：%s" % _join(threat.sources),
                "- 入口数据流：%s" % _join(threat.entry_flows),
                "- 攻击路径：%s" % " → ".join(threat.attack_flows),
                "- 受影响资产：%s" % _join(threat.affected_assets),
                "- 受影响组件：%s" % _join(threat.affected_components),
                "- 跨越边界：%s" % _join(threat.trust_boundaries),
                "- 前置条件：%s" % _statements(threat.preconditions),
                "- 现有控制：%s" % _statements(threat.current_controls),
                "- 控制缺口：%s" % _statements(threat.control_gaps),
                "- 影响判断：%s" % threat.impact_rationale,
                "- 可能性判断：%s" % threat.likelihood_rationale,
                "",
            ]
        )

    lines.extend(["## 安全需求与验证计划", ""])
    lines.extend(
        _table(
            ("安全需求", "要求", "来源威胁", "控制类型", "计划课程", "验证计划"),
            (
                (
                    "%s %s" % (requirement.id, requirement.title),
                    requirement.statement,
                    _join(requirement.derived_from),
                    requirement.control_type,
                    _join(requirement.planned_lessons),
                    _join(verifications_by_requirement[requirement.id]),
                )
                for requirement in sorted(model.requirements, key=lambda x: x.id)
            ),
        )
    )
    lines.extend(["", "### 验证说明", ""])
    for verification in sorted(model.verifications, key=lambda x: x.id):
        lines.append(
            "- `%s`（%s）：%s；验证 %s。"
            % (
                verification.id,
                verification.type,
                verification.description.rstrip("。；"),
                _join(verification.verifies_requirements),
            )
        )

    lines.extend(
        [
            "",
            "## 统计",
            "",
            "- 参与者：%d" % len(model.actors),
            "- 组件：%d" % len(model.components),
            "- 资产：%d" % len(model.assets),
            "- 信任边界：%d" % len(model.trust_boundaries),
            "- 数据流：%d" % len(model.data_flows),
            "- 威胁：%d" % len(model.threats),
            "- 安全需求：%d" % len(model.requirements),
            "- 验证计划：%d" % len(model.verifications),
            "",
        ]
    )
    return "\n".join(lines)
