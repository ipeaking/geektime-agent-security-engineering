"""严格加载并校验 Firewall Rule、Admission Policy 和评测 Case。"""

import re
import tomllib
from pathlib import Path
from typing import Any, Mapping, Sequence

from .models import (
    AdmissionPolicyConfig,
    CaseSuite,
    CombinationRule,
    FirewallCase,
    FirewallDecision,
    FirewallRule,
    IntentLabel,
    PatternType,
    RuleSet,
)


RULE_CATEGORIES = {
    "instruction_override",
    "task_expansion",
    "local_data_access",
    "data_egress",
    "authorization_claim",
    "stealth_instruction",
    "role_override",
    "secret_access",
}
SEVERITIES = {"low", "medium", "high", "critical"}
RULE_FIELDS = {
    "id",
    "category",
    "severity",
    "weight",
    "enabled",
    "pattern_type",
    "description",
    "explanation",
    "patterns",
    "leading_terms",
    "target_terms",
    "max_gap_chars",
}
CASE_FIELDS = {
    "id",
    "title",
    "suite",
    "intent_label",
    "expected_decision",
    "source_type",
    "fixture",
    "description",
    "tags",
}
MAX_PATTERN_CHARS = 240


class FirewallConfigError(ValueError):
    pass


def load_rules(path: Path) -> RuleSet:
    data = _load_toml(path)
    _reject_unknown(data, {"schema_version", "ruleset_version", "rules"}, path.name)
    if data.get("schema_version") != "1.0":
        raise FirewallConfigError("unsupported rules schema_version")
    version = _text(data, "ruleset_version", path.name)
    raw_rules = data.get("rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise FirewallConfigError("rules must be a non-empty array")
    rules = tuple(_parse_rule(item, index) for index, item in enumerate(raw_rules, 1))
    _reject_duplicates([rule.id for rule in rules], "rule id")
    return RuleSet(version, rules)


def _parse_rule(value: Any, index: int) -> FirewallRule:
    location = "rules[%d]" % index
    if not isinstance(value, dict):
        raise FirewallConfigError("%s must be a table" % location)
    _reject_unknown(value, RULE_FIELDS, location)
    required = {
        "id",
        "category",
        "severity",
        "weight",
        "enabled",
        "pattern_type",
        "description",
        "explanation",
    }
    _require_fields(value, required, location)
    rule_id = _text(value, "id", location)
    if not re.fullmatch(r"PF-[A-Z]+-[0-9]{3}", rule_id):
        raise FirewallConfigError("%s has invalid rule id" % location)
    category = _text(value, "category", location)
    severity = _text(value, "severity", location)
    if category not in RULE_CATEGORIES:
        raise FirewallConfigError("%s has unknown category" % location)
    if severity not in SEVERITIES:
        raise FirewallConfigError("%s has unknown severity" % location)
    weight = _integer(value, "weight", location, minimum=0, maximum=100)
    enabled = value["enabled"]
    if not isinstance(enabled, bool):
        raise FirewallConfigError("%s.enabled must be boolean" % location)
    try:
        pattern_type = PatternType(_text(value, "pattern_type", location))
    except ValueError as error:
        raise FirewallConfigError("%s has unknown pattern_type" % location) from error

    patterns = _optional_texts(value, "patterns", location)
    leading_terms = _optional_texts(value, "leading_terms", location)
    target_terms = _optional_texts(value, "target_terms", location)
    max_gap_chars = value.get("max_gap_chars", 0)
    if not isinstance(max_gap_chars, int) or isinstance(max_gap_chars, bool):
        raise FirewallConfigError("%s.max_gap_chars must be an integer" % location)
    all_terms = patterns + leading_terms + target_terms
    if any(len(term) > MAX_PATTERN_CHARS for term in all_terms):
        raise FirewallConfigError("%s contains an oversized pattern" % location)
    if pattern_type is PatternType.LITERAL:
        if not patterns or leading_terms or target_terms or max_gap_chars:
            raise FirewallConfigError("%s literal rule has invalid pattern fields" % location)
    else:
        if patterns or not leading_terms or not target_terms or not 0 <= max_gap_chars <= 200:
            raise FirewallConfigError("%s bounded_terms rule has invalid pattern fields" % location)
    return FirewallRule(
        id=rule_id,
        category=category,
        severity=severity,
        weight=weight,
        enabled=enabled,
        pattern_type=pattern_type,
        description=_text(value, "description", location),
        explanation=_text(value, "explanation", location),
        patterns=patterns,
        leading_terms=leading_terms,
        target_terms=target_terms,
        max_gap_chars=max_gap_chars,
    )


def load_policy(path: Path) -> AdmissionPolicyConfig:
    data = _load_toml(path)
    _reject_unknown(
        data,
        {"schema_version", "admission_policy_version", "thresholds", "limits", "combinations"},
        path.name,
    )
    if data.get("schema_version") != "1.0":
        raise FirewallConfigError("unsupported policy schema_version")
    thresholds = data.get("thresholds")
    limits = data.get("limits")
    if not isinstance(thresholds, dict) or not isinstance(limits, dict):
        raise FirewallConfigError("policy thresholds and limits must be tables")
    _reject_unknown(thresholds, {"flag", "block", "max_score"}, "thresholds")
    _reject_unknown(
        limits,
        {"max_content_chars", "max_evidence_per_rule", "max_evidence_chars"},
        "limits",
    )
    flag = _integer(thresholds, "flag", "thresholds", minimum=0, maximum=100)
    block = _integer(thresholds, "block", "thresholds", minimum=0, maximum=100)
    max_score = _integer(thresholds, "max_score", "thresholds", minimum=1, maximum=100)
    if not flag < block <= max_score:
        raise FirewallConfigError("thresholds must satisfy flag < block <= max_score")
    max_content_chars = _integer(
        limits, "max_content_chars", "limits", minimum=1, maximum=2_000_000
    )
    max_evidence_per_rule = _integer(
        limits, "max_evidence_per_rule", "limits", minimum=1, maximum=20
    )
    max_evidence_chars = _integer(
        limits, "max_evidence_chars", "limits", minimum=16, maximum=500
    )
    raw_combinations = data.get("combinations", [])
    if not isinstance(raw_combinations, list):
        raise FirewallConfigError("combinations must be an array")
    combinations = tuple(
        _parse_combination(item, index) for index, item in enumerate(raw_combinations, 1)
    )
    _reject_duplicates([item.id for item in combinations], "combination id")
    return AdmissionPolicyConfig(
        version=_text(data, "admission_policy_version", path.name),
        flag_threshold=flag,
        block_threshold=block,
        max_score=max_score,
        max_content_chars=max_content_chars,
        max_evidence_per_rule=max_evidence_per_rule,
        max_evidence_chars=max_evidence_chars,
        combinations=combinations,
    )


def _parse_combination(value: Any, index: int) -> CombinationRule:
    location = "combinations[%d]" % index
    if not isinstance(value, dict):
        raise FirewallConfigError("%s must be a table" % location)
    _reject_unknown(value, {"id", "required_categories", "score", "explanation"}, location)
    _require_fields(value, {"id", "required_categories", "score", "explanation"}, location)
    identifier = _text(value, "id", location)
    if not re.fullmatch(r"PF-COMB-[0-9]{3}", identifier):
        raise FirewallConfigError("%s has invalid id" % location)
    categories = _texts(value, "required_categories", location)
    if len(categories) < 2 or any(category not in RULE_CATEGORIES for category in categories):
        raise FirewallConfigError("%s has invalid required_categories" % location)
    return CombinationRule(
        id=identifier,
        required_categories=categories,
        score=_integer(value, "score", location, minimum=1, maximum=100),
        explanation=_text(value, "explanation", location),
    )


def load_cases(cases_dir: Path, lesson_root: Path | None = None) -> tuple[FirewallCase, ...]:
    if not cases_dir.is_dir():
        raise FirewallConfigError("cases directory does not exist: %s" % cases_dir)
    root = (lesson_root or cases_dir.parent).resolve()
    cases: list[FirewallCase] = []
    for path in sorted(cases_dir.rglob("*.toml")):
        data = _load_toml(path)
        _reject_unknown(data, {"schema_version", "cases"}, path.name)
        if data.get("schema_version") != "1.0":
            raise FirewallConfigError("unsupported case schema_version in %s" % path.name)
        raw_cases = data.get("cases")
        if not isinstance(raw_cases, list) or not raw_cases:
            raise FirewallConfigError("%s.cases must be a non-empty array" % path.name)
        cases.extend(_parse_case(item, path.name, root) for item in raw_cases)
    if not cases:
        raise FirewallConfigError("no firewall cases found")
    _reject_duplicates([case.id for case in cases], "case id")
    return tuple(sorted(cases, key=lambda item: item.id))


def _parse_case(value: Any, location: str, lesson_root: Path) -> FirewallCase:
    if not isinstance(value, dict):
        raise FirewallConfigError("%s case must be a table" % location)
    _reject_unknown(value, CASE_FIELDS, location)
    _require_fields(value, CASE_FIELDS, location)
    identifier = _text(value, "id", location)
    if not re.fullmatch(r"PF-(CONTRACT|EVAL|CHALLENGE)-[0-9]{3}", identifier):
        raise FirewallConfigError("%s has invalid case id" % identifier)
    try:
        suite = CaseSuite(_text(value, "suite", identifier))
        intent = IntentLabel(_text(value, "intent_label", identifier))
        expected = FirewallDecision(_text(value, "expected_decision", identifier))
    except ValueError as error:
        raise FirewallConfigError("%s has invalid enum value" % identifier) from error
    fixture = _text(value, "fixture", identifier)
    resolved = (lesson_root / fixture).resolve()
    if lesson_root != resolved and lesson_root not in resolved.parents:
        raise FirewallConfigError("%s fixture escapes lesson root" % identifier)
    if not resolved.is_file():
        raise FirewallConfigError("%s fixture does not exist" % identifier)
    return FirewallCase(
        id=identifier,
        title=_text(value, "title", identifier),
        suite=suite,
        intent_label=intent,
        expected_decision=expected,
        source_type=_text(value, "source_type", identifier),
        fixture=fixture,
        description=_text(value, "description", identifier),
        tags=_texts(value, "tags", identifier),
    )


def _load_toml(path: Path) -> Mapping[str, Any]:
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise FirewallConfigError("cannot load TOML: %s" % path) from error
    if not isinstance(data, dict):
        raise FirewallConfigError("TOML root must be a table: %s" % path)
    return data


def _reject_unknown(data: Mapping[str, Any], allowed: set[str], location: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise FirewallConfigError("%s has unknown fields: %s" % (location, ", ".join(unknown)))


def _require_fields(data: Mapping[str, Any], required: set[str], location: str) -> None:
    missing = sorted(required - set(data))
    if missing:
        raise FirewallConfigError("%s missing fields: %s" % (location, ", ".join(missing)))


def _text(data: Mapping[str, Any], key: str, location: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise FirewallConfigError("%s.%s must be a non-empty string" % (location, key))
    return value.strip()


def _texts(data: Mapping[str, Any], key: str, location: str) -> tuple[str, ...]:
    value = data.get(key)
    if not isinstance(value, list) or not value or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise FirewallConfigError("%s.%s must be a non-empty string list" % (location, key))
    return tuple(item.strip() for item in value)


def _optional_texts(data: Mapping[str, Any], key: str, location: str) -> tuple[str, ...]:
    if key not in data:
        return ()
    return _texts(data, key, location)


def _integer(
    data: Mapping[str, Any],
    key: str,
    location: str,
    minimum: int,
    maximum: int,
) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise FirewallConfigError(
            "%s.%s must be an integer from %d to %d"
            % (location, key, minimum, maximum)
        )
    return value


def _reject_duplicates(values: Sequence[str], label: str) -> None:
    if len(set(values)) != len(values):
        raise FirewallConfigError("duplicate %s" % label)
