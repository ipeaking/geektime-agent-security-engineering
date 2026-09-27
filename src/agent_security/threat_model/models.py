"""威胁模型的领域对象。

这些对象只描述第一讲系统当前是什么样，不在这里实现安全防御。
"""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class SystemScope:
    id: str
    name: str
    baseline_tag: str
    description: str
    in_scope: Tuple[str, ...]
    out_of_scope_topics: Tuple[str, ...]


@dataclass(frozen=True)
class Assumption:
    id: str
    statement: str


@dataclass(frozen=True)
class Actor:
    id: str
    name: str
    trust: str
    description: str


@dataclass(frozen=True)
class Component:
    id: str
    name: str
    kind: str
    trust: str
    description: str
    code_refs: Tuple[str, ...]
    tool_name: Optional[str] = None


@dataclass(frozen=True)
class Asset:
    id: str
    name: str
    classification: str
    description: str


@dataclass(frozen=True)
class TrustBoundary:
    id: str
    name: str
    description: str


@dataclass(frozen=True)
class DataFlow:
    id: str
    name: str
    source: str
    destination: str
    assets: Tuple[str, ...]
    crosses: Tuple[str, ...]
    channel: str
    description: str


@dataclass(frozen=True)
class Threat:
    id: str
    title: str
    description: str
    sources: Tuple[str, ...]
    entry_flows: Tuple[str, ...]
    affected_assets: Tuple[str, ...]
    affected_components: Tuple[str, ...]
    trust_boundaries: Tuple[str, ...]
    attack_flows: Tuple[str, ...]
    preconditions: Tuple[str, ...]
    current_controls: Tuple[str, ...]
    control_gaps: Tuple[str, ...]
    priority: str
    impact_confidentiality: str
    impact_integrity: str
    impact_availability: str
    impact_rationale: str
    likelihood: str
    likelihood_rationale: str


@dataclass(frozen=True)
class SecurityRequirement:
    id: str
    title: str
    statement: str
    derived_from: Tuple[str, ...]
    control_type: str
    planned_lessons: Tuple[str, ...]


@dataclass(frozen=True)
class Verification:
    id: str
    type: str
    description: str
    verifies_requirements: Tuple[str, ...]


@dataclass(frozen=True)
class ThreatModel:
    schema_version: str
    system: SystemScope
    assumptions: Tuple[Assumption, ...]
    actors: Tuple[Actor, ...]
    components: Tuple[Component, ...]
    assets: Tuple[Asset, ...]
    trust_boundaries: Tuple[TrustBoundary, ...]
    data_flows: Tuple[DataFlow, ...]
    threats: Tuple[Threat, ...]
    requirements: Tuple[SecurityRequirement, ...]
    verifications: Tuple[Verification, ...]

    def get_threat(self, threat_id: str) -> Threat:
        """按编号查找威胁，找不到时给出清晰错误。"""

        for threat in self.threats:
            if threat.id == threat_id:
                return threat
        raise KeyError("unknown threat: %s" % threat_id)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: str
    location: str
    message: str
