"""严格加载第 06 讲配置与确定性 Replay Scenario。"""

import hashlib
import re
import tomllib
from pathlib import Path
from typing import Any, Mapping

from agent_security.prompt_firewall.config import load_cases

from .models import (
    ContextSegment,
    ExpectedStage,
    GuardrailAction,
    GuardrailPolicyConfig,
    GuardrailScenario,
    GuardrailStage,
    OutputMode,
    PipelineOutcome,
    ReplayPlan,
    ScenarioExpectation,
    StageStatus,
    TaskContract,
    stable_tool_call,
)


class GuardrailConfigError(ValueError):
    pass


KNOWN_TOOLS = {"load_content", "fetch_webpage", "read_file", "send_diagnostic"}
KNOWN_SOURCES = {"system", "user", "webpage", "pdf", "email", "rag_document", "tool_result", "documentation"}
KNOWN_TRUST = {"trusted", "user_controlled", "untrusted"}
KNOWN_ROLES = {"instruction", "data"}
KNOWN_TRANSPORTS = {"instructions", "user_message", "function_call_output"}
STAGE_KEYS = {
    "input": GuardrailStage.INPUT,
    "context": GuardrailStage.CONTEXT,
    "tool_proposal": GuardrailStage.TOOL_PROPOSAL,
    "output": GuardrailStage.OUTPUT,
}


def load_guardrail_policy(path: Path) -> GuardrailPolicyConfig:
    data = _load_toml(path)
    expected = {
        "schema_version",
        "version",
        "known_tools",
        "sensitive_tools",
        "cross_segment_combinations",
        "spoof_markers",
        "max_event_evidence",
        "max_output_chars",
        "max_protected_values",
        "max_protected_value_chars",
        "redaction_token",
    }
    _exact_fields(data, expected, path.name)
    if data["schema_version"] != "1.0":
        raise GuardrailConfigError("unsupported guardrail policy schema_version")
    known_tools = _texts(data, "known_tools", path.name)
    sensitive_tools = _texts(data, "sensitive_tools", path.name)
    if set(known_tools) != KNOWN_TOOLS:
        raise GuardrailConfigError("guardrail policy known_tools drifted from runtime tools")
    if not set(sensitive_tools).issubset(known_tools):
        raise GuardrailConfigError("sensitive_tools must be a subset of known_tools")
    raw_combinations = data["cross_segment_combinations"]
    if not isinstance(raw_combinations, list) or not raw_combinations:
        raise GuardrailConfigError("cross_segment_combinations must be a non-empty array")
    combinations: list[tuple[str, ...]] = []
    for item in raw_combinations:
        if not isinstance(item, list) or len(item) < 2 or any(
            not isinstance(value, str) or not value.strip() for value in item
        ):
            raise GuardrailConfigError("invalid cross_segment_combinations entry")
        combination = tuple(value.strip() for value in item)
        if len(set(combination)) != len(combination):
            raise GuardrailConfigError("cross-segment combination contains duplicate category")
        combinations.append(combination)
    if len(set(combinations)) != len(combinations):
        raise GuardrailConfigError("duplicate cross-segment combination")
    return GuardrailPolicyConfig(
        version=_text(data, "version", path.name),
        known_tools=known_tools,
        sensitive_tools=sensitive_tools,
        cross_segment_combinations=tuple(combinations),
        spoof_markers=_texts(data, "spoof_markers", path.name),
        max_event_evidence=_integer(data, "max_event_evidence", path.name, 1, 32),
        max_output_chars=_integer(data, "max_output_chars", path.name, 1, 1_000_000),
        max_protected_values=_integer(data, "max_protected_values", path.name, 1, 1_000),
        max_protected_value_chars=_integer(
            data, "max_protected_value_chars", path.name, 1, 10_000
        ),
        redaction_token=_text(data, "redaction_token", path.name),
    )


def load_scenarios(
    scenarios_dir: Path,
    lesson_root: Path,
    firewall_lesson_root: Path,
    policy: GuardrailPolicyConfig,
) -> tuple[GuardrailScenario, ...]:
    if not scenarios_dir.is_dir():
        raise GuardrailConfigError("scenarios directory does not exist: %s" % scenarios_dir)
    scenarios = tuple(
        _parse_scenario(
            path,
            lesson_root.resolve(),
            firewall_lesson_root.resolve(),
            policy,
        )
        for path in sorted(scenarios_dir.glob("*.toml"))
    )
    if not scenarios:
        raise GuardrailConfigError("no guardrail scenarios found")
    ids = [item.id for item in scenarios]
    if len(ids) != len(set(ids)):
        raise GuardrailConfigError("duplicate scenario id")
    return tuple(sorted(scenarios, key=lambda item: item.id))


def _parse_scenario(
    path: Path,
    lesson_root: Path,
    firewall_root: Path,
    policy: GuardrailPolicyConfig,
) -> GuardrailScenario:
    data = _load_toml(path)
    _exact_fields(
        data,
        {"schema_version", "id", "title", "description", "task", "segments", "replay", "output_mode", "expected"},
        path.name,
    )
    if data["schema_version"] != "1.0":
        raise GuardrailConfigError("unsupported schema_version in %s" % path.name)
    scenario_id = _text(data, "id", path.name)
    if not re.fullmatch(r"GR-SCENARIO-[0-9]{2}", scenario_id):
        raise GuardrailConfigError("invalid scenario id: %s" % scenario_id)

    task_data = _table(data, "task", scenario_id)
    _exact_fields(task_data, {"type", "allowed_tools"}, scenario_id + ".task")
    allowed_tools = _texts(task_data, "allowed_tools", scenario_id)
    if any(item not in KNOWN_TOOLS for item in allowed_tools):
        raise GuardrailConfigError("%s has unknown allowed tool" % scenario_id)
    contract = TaskContract(_text(task_data, "type", scenario_id), allowed_tools)

    raw_segments = data["segments"]
    if not isinstance(raw_segments, list) or not raw_segments:
        raise GuardrailConfigError("%s.segments must be a non-empty array" % scenario_id)
    segments = tuple(
        _parse_segment(value, scenario_id, lesson_root, firewall_root)
        for value in raw_segments
    )
    segment_ids = [item.id for item in segments]
    if len(segment_ids) != len(set(segment_ids)):
        raise GuardrailConfigError("%s has duplicate segment id" % scenario_id)

    replay_data = _table(data, "replay", scenario_id)
    _allowed_fields(
        replay_data,
        {"tool_name", "tool_arguments", "output_fixture", "protected_fixture"},
        scenario_id + ".replay",
    )
    tool_call = None
    if "tool_name" in replay_data:
        tool_name = _text(replay_data, "tool_name", scenario_id)
        if tool_name not in KNOWN_TOOLS:
            raise GuardrailConfigError("%s has unknown replay tool" % scenario_id)
        arguments = replay_data.get("tool_arguments", {})
        if not isinstance(arguments, dict):
            raise GuardrailConfigError("%s.tool_arguments must be a table" % scenario_id)
        tool_call = stable_tool_call(tool_name, arguments, scenario_id)
    elif "tool_arguments" in replay_data:
        raise GuardrailConfigError("%s has tool arguments without tool name" % scenario_id)

    output_text = _optional_fixture(replay_data, "output_fixture", scenario_id, lesson_root)
    protected_text = _optional_fixture(replay_data, "protected_fixture", scenario_id, lesson_root)
    protected_values = () if protected_text is None else tuple(
        line for line in (item.strip() for item in protected_text.splitlines()) if line
    )
    if len(protected_values) > policy.max_protected_values or any(
        len(item) > policy.max_protected_value_chars for item in protected_values
    ):
        raise GuardrailConfigError("%s has oversized protected value set" % scenario_id)
    if output_text is not None and len(output_text) > policy.max_output_chars:
        raise GuardrailConfigError("%s output fixture exceeds replay limit" % scenario_id)
    replay = ReplayPlan(tool_call, output_text, protected_values)

    try:
        output_mode = OutputMode(_text(data, "output_mode", scenario_id))
    except ValueError as error:
        raise GuardrailConfigError("%s has invalid output_mode" % scenario_id) from error
    expectation = _parse_expectation(_table(data, "expected", scenario_id), scenario_id)
    _validate_expectation(expectation, scenario_id)
    return GuardrailScenario(
        id=scenario_id,
        title=_text(data, "title", scenario_id),
        description=_text(data, "description", scenario_id),
        task_contract=contract,
        segments=segments,
        replay=replay,
        output_mode=output_mode,
        expected=expectation,
    )


def _parse_segment(
    value: Any,
    scenario_id: str,
    lesson_root: Path,
    firewall_root: Path,
) -> ContextSegment:
    if not isinstance(value, dict):
        raise GuardrailConfigError("%s segment must be a table" % scenario_id)
    _allowed_fields(
        value,
        {"id", "source", "trust", "intended_role", "transport", "media_type", "parser", "fixture", "firewall_case_id"},
        scenario_id + ".segment",
    )
    required = {"id", "source", "trust", "intended_role", "transport", "media_type", "parser"}
    if not required.issubset(value):
        raise GuardrailConfigError("%s segment is missing required fields" % scenario_id)
    fixture = value.get("fixture")
    firewall_case_id = value.get("firewall_case_id")
    if bool(fixture) == bool(firewall_case_id):
        raise GuardrailConfigError(
            "%s segment requires exactly one fixture or firewall_case_id" % scenario_id
        )
    if fixture:
        content = _read_fixture(str(fixture), scenario_id, lesson_root)
    else:
        cases = {item.id: item for item in load_cases(firewall_root / "cases", firewall_root)}
        case = cases.get(str(firewall_case_id))
        if case is None:
            raise GuardrailConfigError("%s references unknown firewall case" % scenario_id)
        content = _read_fixture(case.fixture, scenario_id, firewall_root)
    source = _text(value, "source", scenario_id)
    trust = _text(value, "trust", scenario_id)
    intended_role = _text(value, "intended_role", scenario_id)
    transport = _text(value, "transport", scenario_id)
    if source not in KNOWN_SOURCES or trust not in KNOWN_TRUST:
        raise GuardrailConfigError("%s segment has unknown source or trust" % scenario_id)
    if intended_role not in KNOWN_ROLES or transport not in KNOWN_TRANSPORTS:
        raise GuardrailConfigError("%s segment has unknown role or transport" % scenario_id)
    return ContextSegment(
        id=_text(value, "id", scenario_id),
        source=source,
        trust=trust,
        intended_role=intended_role,
        transport=transport,
        media_type=_text(value, "media_type", scenario_id),
        parser=_text(value, "parser", scenario_id),
        content=content,
        content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )


def _parse_expectation(value: Mapping[str, Any], scenario_id: str) -> ScenarioExpectation:
    _allowed_fields(
        value,
        set(STAGE_KEYS) | {"outcome", "stopped_at"},
        scenario_id + ".expected",
    )
    missing = sorted((set(STAGE_KEYS) | {"outcome"}) - set(value))
    if missing:
        raise GuardrailConfigError(
            "%s.expected missing fields: %s" % (scenario_id, ", ".join(missing))
        )
    stages = []
    for key, stage in STAGE_KEYS.items():
        raw = _table(value, key, scenario_id + ".expected")
        _allowed_fields(raw, {"status", "action"}, scenario_id + ".expected." + key)
        try:
            status = StageStatus(_text(raw, "status", scenario_id))
            action = GuardrailAction(_text(raw, "action", scenario_id)) if "action" in raw else None
        except ValueError as error:
            raise GuardrailConfigError("%s has invalid expected stage value" % scenario_id) from error
        if (status is StageStatus.EXECUTED) != (action is not None):
            raise GuardrailConfigError("%s expected action/status are inconsistent" % scenario_id)
        stages.append((stage, ExpectedStage(status, action)))
    try:
        outcome = PipelineOutcome(_text(value, "outcome", scenario_id))
        stopped_at = GuardrailStage(value["stopped_at"]) if "stopped_at" in value else None
    except ValueError as error:
        raise GuardrailConfigError("%s has invalid expected outcome" % scenario_id) from error
    return ScenarioExpectation(tuple(stages), outcome, stopped_at)


def _validate_expectation(expected: ScenarioExpectation, scenario_id: str) -> None:
    blocked = None
    actions: set[GuardrailAction] = set()
    for stage in GuardrailStage:
        value = expected.stage(stage)
        if stage in (GuardrailStage.INPUT, GuardrailStage.CONTEXT) and (
            value.status is StageStatus.NOT_APPLICABLE
        ):
            raise GuardrailConfigError("%s cannot mark %s not applicable" % (scenario_id, stage.value))
        if blocked is None and value.status is StageStatus.NOT_RUN:
            raise GuardrailConfigError("%s marks %s not run before a BLOCK" % (scenario_id, stage.value))
        if blocked is not None and value.status is not StageStatus.NOT_RUN:
            raise GuardrailConfigError("%s executes a stage after expected BLOCK" % scenario_id)
        if value.action is GuardrailAction.BLOCK:
            blocked = stage
        if value.action is GuardrailAction.REDACT and stage is not GuardrailStage.OUTPUT:
            raise GuardrailConfigError("%s uses REDACT outside Output Guard" % scenario_id)
        if value.action is not None:
            actions.add(value.action)
    if blocked != expected.stopped_at:
        raise GuardrailConfigError("%s stopped_at does not match expected BLOCK" % scenario_id)
    if (blocked is not None) != (expected.outcome is PipelineOutcome.BLOCKED):
        raise GuardrailConfigError("%s outcome does not match expected stages" % scenario_id)
    if blocked is None:
        derived = (
            PipelineOutcome.COMPLETED_REDACTED
            if GuardrailAction.REDACT in actions
            else PipelineOutcome.COMPLETED_WITH_FLAGS
            if GuardrailAction.FLAG in actions
            else PipelineOutcome.COMPLETED
        )
        if expected.outcome is not derived:
            raise GuardrailConfigError("%s completion outcome does not match actions" % scenario_id)


def _optional_fixture(data: Mapping[str, Any], key: str, location: str, root: Path) -> str | None:
    if key not in data:
        return None
    return _read_fixture(_text(data, key, location), location, root)


def _read_fixture(value: str, location: str, root: Path) -> str:
    path = (root / value).resolve()
    if root != path and root not in path.parents:
        raise GuardrailConfigError("%s fixture escapes lesson root" % location)
    if not path.is_file():
        raise GuardrailConfigError("%s fixture does not exist: %s" % (location, value))
    return path.read_text(encoding="utf-8").strip()


def _load_toml(path: Path) -> Mapping[str, Any]:
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise GuardrailConfigError("cannot load TOML: %s" % path) from error
    if not isinstance(data, dict):
        raise GuardrailConfigError("TOML root must be a table")
    return data


def _table(data: Mapping[str, Any], key: str, location: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise GuardrailConfigError("%s.%s must be a table" % (location, key))
    return value


def _text(data: Mapping[str, Any], key: str, location: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GuardrailConfigError("%s.%s must be a non-empty string" % (location, key))
    return value.strip()


def _texts(data: Mapping[str, Any], key: str, location: str) -> tuple[str, ...]:
    value = data.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise GuardrailConfigError("%s.%s must be a string list" % (location, key))
    return tuple(value)


def _integer(
    data: Mapping[str, Any],
    key: str,
    location: str,
    minimum: int,
    maximum: int,
) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise GuardrailConfigError(
            "%s.%s must be an integer from %d to %d"
            % (location, key, minimum, maximum)
        )
    return value


def _allowed_fields(data: Mapping[str, Any], allowed: set[str], location: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise GuardrailConfigError("%s has unknown fields: %s" % (location, ", ".join(unknown)))


def _exact_fields(data: Mapping[str, Any], expected: set[str], location: str) -> None:
    _allowed_fields(data, expected, location)
    missing = sorted(expected - set(data))
    if missing:
        raise GuardrailConfigError("%s missing fields: %s" % (location, ", ".join(missing)))
