"""从课程 TOML 文件加载威胁模型。"""

import tomllib
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Tuple

from .models import (
    Actor,
    Asset,
    Assumption,
    Component,
    DataFlow,
    SecurityRequirement,
    SystemScope,
    Threat,
    ThreatModel,
    TrustBoundary,
    Verification,
)


class ModelLoadError(ValueError):
    """模型文件缺失、语法错误或字段结构不正确。"""


def _read_toml(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise ModelLoadError("missing model file: %s" % path)
    try:
        with path.open("rb") as stream:
            return tomllib.load(stream)
    except tomllib.TOMLDecodeError as error:
        raise ModelLoadError("invalid TOML in %s: %s" % (path, error)) from error


def _require_keys(
    item: Mapping[str, Any],
    required: Iterable[str],
    optional: Iterable[str],
    location: str,
) -> None:
    required_set = set(required)
    allowed = required_set | set(optional)
    missing = sorted(required_set - set(item))
    unknown = sorted(set(item) - allowed)
    if missing:
        raise ModelLoadError("%s missing fields: %s" % (location, ", ".join(missing)))
    if unknown:
        raise ModelLoadError("%s has unknown fields: %s" % (location, ", ".join(unknown)))


def _text(item: Mapping[str, Any], key: str, location: str) -> str:
    value = item[key]
    if not isinstance(value, str) or not value.strip():
        raise ModelLoadError("%s.%s must be a non-empty string" % (location, key))
    return value


def _texts(item: Mapping[str, Any], key: str, location: str) -> Tuple[str, ...]:
    value = item[key]
    if not isinstance(value, list) or any(
        not isinstance(entry, str) or not entry.strip() for entry in value
    ):
        raise ModelLoadError("%s.%s must be a list of non-empty strings" % (location, key))
    return tuple(value)


def _tables(data: Mapping[str, Any], key: str, location: str) -> Tuple[Dict[str, Any], ...]:
    value = data.get(key)
    if not isinstance(value, list) or any(not isinstance(entry, dict) for entry in value):
        raise ModelLoadError("%s.%s must be an array of tables" % (location, key))
    return tuple(value)


def load_threat_model(model_dir: Path) -> ThreatModel:
    """加载四个文件，并转换为不可变领域对象。"""

    scope_data = _read_toml(model_dir / "scope.toml")
    inventory_data = _read_toml(model_dir / "inventory.toml")
    flows_data = _read_toml(model_dir / "data_flows.toml")
    threats_data = _read_toml(model_dir / "threats.toml")

    _require_keys(scope_data, ("schema_version", "system", "scope", "assumptions"), (), "scope.toml")
    _require_keys(inventory_data, ("actors", "components", "assets", "trust_boundaries"), (), "inventory.toml")
    _require_keys(flows_data, ("data_flows",), (), "data_flows.toml")
    _require_keys(threats_data, ("threats", "requirements", "verifications"), (), "threats.toml")
    system_data = scope_data["system"]
    scope_section = scope_data["scope"]
    if not isinstance(system_data, dict) or not isinstance(scope_section, dict):
        raise ModelLoadError("scope.toml system and scope must be tables")
    _require_keys(system_data, ("id", "name", "baseline_tag", "description"), (), "system")
    _require_keys(scope_section, ("in_scope", "out_of_scope_topics"), (), "scope")
    system = SystemScope(
        id=_text(system_data, "id", "system"),
        name=_text(system_data, "name", "system"),
        baseline_tag=_text(system_data, "baseline_tag", "system"),
        description=_text(system_data, "description", "system"),
        in_scope=_texts(scope_section, "in_scope", "scope"),
        out_of_scope_topics=_texts(scope_section, "out_of_scope_topics", "scope"),
    )

    assumptions = []
    for index, item in enumerate(_tables(scope_data, "assumptions", "scope.toml")):
        location = "assumptions[%d]" % index
        _require_keys(item, ("id", "statement"), (), location)
        assumptions.append(Assumption(_text(item, "id", location), _text(item, "statement", location)))

    actors = []
    for index, item in enumerate(_tables(inventory_data, "actors", "inventory.toml")):
        location = "actors[%d]" % index
        _require_keys(item, ("id", "name", "trust", "description"), (), location)
        actors.append(Actor(*(_text(item, key, location) for key in ("id", "name", "trust", "description"))))

    components = []
    for index, item in enumerate(_tables(inventory_data, "components", "inventory.toml")):
        location = "components[%d]" % index
        _require_keys(
            item,
            ("id", "name", "kind", "trust", "description", "code_refs"),
            ("tool_name",),
            location,
        )
        tool_name = _text(item, "tool_name", location) if "tool_name" in item else None
        components.append(
            Component(
                id=_text(item, "id", location),
                name=_text(item, "name", location),
                kind=_text(item, "kind", location),
                trust=_text(item, "trust", location),
                description=_text(item, "description", location),
                code_refs=_texts(item, "code_refs", location),
                tool_name=tool_name,
            )
        )

    assets = []
    for index, item in enumerate(_tables(inventory_data, "assets", "inventory.toml")):
        location = "assets[%d]" % index
        _require_keys(item, ("id", "name", "classification", "description"), (), location)
        assets.append(Asset(*(_text(item, key, location) for key in ("id", "name", "classification", "description"))))

    boundaries = []
    for index, item in enumerate(_tables(inventory_data, "trust_boundaries", "inventory.toml")):
        location = "trust_boundaries[%d]" % index
        _require_keys(item, ("id", "name", "description"), (), location)
        boundaries.append(TrustBoundary(*(_text(item, key, location) for key in ("id", "name", "description"))))

    flows = []
    for index, item in enumerate(_tables(flows_data, "data_flows", "data_flows.toml")):
        location = "data_flows[%d]" % index
        _require_keys(
            item,
            ("id", "name", "source", "destination", "assets", "crosses", "channel", "description"),
            (),
            location,
        )
        flows.append(
            DataFlow(
                id=_text(item, "id", location),
                name=_text(item, "name", location),
                source=_text(item, "source", location),
                destination=_text(item, "destination", location),
                assets=_texts(item, "assets", location),
                crosses=_texts(item, "crosses", location),
                channel=_text(item, "channel", location),
                description=_text(item, "description", location),
            )
        )

    threats = []
    threat_fields = (
        "id", "title", "description", "sources", "entry_flows", "affected_assets",
        "affected_components", "trust_boundaries", "attack_flows", "preconditions",
        "current_controls", "control_gaps", "priority", "impact_confidentiality",
        "impact_integrity", "impact_availability", "impact_rationale", "likelihood",
        "likelihood_rationale",
    )
    list_fields = {
        "sources", "entry_flows", "affected_assets", "affected_components",
        "trust_boundaries", "attack_flows", "preconditions", "current_controls", "control_gaps",
    }
    for index, item in enumerate(_tables(threats_data, "threats", "threats.toml")):
        location = "threats[%d]" % index
        _require_keys(item, threat_fields, (), location)
        values = {
            key: (_texts(item, key, location) if key in list_fields else _text(item, key, location))
            for key in threat_fields
        }
        threats.append(Threat(**values))

    requirements = []
    for index, item in enumerate(_tables(threats_data, "requirements", "threats.toml")):
        location = "requirements[%d]" % index
        _require_keys(item, ("id", "title", "statement", "derived_from", "control_type", "planned_lessons"), (), location)
        requirements.append(
            SecurityRequirement(
                id=_text(item, "id", location),
                title=_text(item, "title", location),
                statement=_text(item, "statement", location),
                derived_from=_texts(item, "derived_from", location),
                control_type=_text(item, "control_type", location),
                planned_lessons=_texts(item, "planned_lessons", location),
            )
        )

    verifications = []
    for index, item in enumerate(_tables(threats_data, "verifications", "threats.toml")):
        location = "verifications[%d]" % index
        _require_keys(item, ("id", "type", "description", "verifies_requirements"), (), location)
        verifications.append(
            Verification(
                id=_text(item, "id", location),
                type=_text(item, "type", location),
                description=_text(item, "description", location),
                verifies_requirements=_texts(item, "verifies_requirements", location),
            )
        )

    return ThreatModel(
        schema_version=_text(scope_data, "schema_version", "scope.toml"),
        system=system,
        assumptions=tuple(assumptions),
        actors=tuple(actors),
        components=tuple(components),
        assets=tuple(assets),
        trust_boundaries=tuple(boundaries),
        data_flows=tuple(flows),
        threats=tuple(threats),
        requirements=tuple(requirements),
        verifications=tuple(verifications),
    )
