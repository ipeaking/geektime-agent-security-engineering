"""严格加载第 07 讲工具风险配置与确定性 Replay。"""

import hashlib
import tomllib
from pathlib import Path
from typing import Any

from .models import (
    ReplayStep,
    ToolEffect,
    ToolRiskExpectation,
    ToolRiskScenario,
    ToolSpec,
)


class ToolRiskConfigError(ValueError):
    pass


def load_tools(path: Path) -> tuple[ToolSpec, ...]:
    payload = _toml(path)
    _exact(payload, {"schema_version", "tools"}, path.name)
    if payload.get("schema_version") != "1.0":
        raise ToolRiskConfigError("unsupported tool schema_version")
    rows = payload.get("tools")
    if not isinstance(rows, list) or not rows:
        raise ToolRiskConfigError("tools must be a non-empty array")
    tools: list[ToolSpec] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ToolRiskConfigError("tool entry must be a table")
        _exact(row, {"name", "effect", "description"}, "tools")
        try:
            effect = ToolEffect(_text(row, "effect", "tools"))
        except ValueError as error:
            raise ToolRiskConfigError("unknown tool effect") from error
        tools.append(
            ToolSpec(
                name=_text(row, "name", "tools"),
                effect=effect,
                description=_text(row, "description", "tools"),
            )
        )
    names = [item.name for item in tools]
    if len(names) != len(set(names)):
        raise ToolRiskConfigError("duplicate tool name")
    return tuple(tools)


def load_scenarios(
    scenarios_dir: Path,
    lesson_root: Path,
    tools: tuple[ToolSpec, ...],
) -> tuple[ToolRiskScenario, ...]:
    known_tools = {item.name for item in tools}
    scenarios = tuple(
        _load_scenario(path, lesson_root, known_tools)
        for path in sorted(scenarios_dir.glob("*.toml"))
    )
    if not scenarios:
        raise ToolRiskConfigError("no scenarios found")
    ids = [item.id for item in scenarios]
    if len(ids) != len(set(ids)):
        raise ToolRiskConfigError("duplicate scenario id")
    return scenarios


def _load_scenario(
    path: Path,
    lesson_root: Path,
    known_tools: set[str],
) -> ToolRiskScenario:
    payload = _toml(path)
    _exact(
        payload,
        {
            "schema_version",
            "id",
            "title",
            "risk_dimension",
            "fixture",
            "final_text",
            "steps",
            "expected",
        },
        path.name,
    )
    if payload.get("schema_version") != "1.0":
        raise ToolRiskConfigError("unsupported scenario schema_version")
    fixture_ref = _text(payload, "fixture", path.name)
    fixture_path = _safe_path(lesson_root, fixture_ref)
    fixture_bytes = fixture_path.read_bytes()
    rows = payload.get("steps")
    if not isinstance(rows, list):
        raise ToolRiskConfigError("steps must be an array")
    steps: list[ReplayStep] = []
    call_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ToolRiskConfigError("step must be a table")
        _exact(row, {"call_id", "tool", "arguments"}, path.name + ".steps")
        call_id = _text(row, "call_id", path.name)
        tool_name = _text(row, "tool", path.name)
        arguments = row.get("arguments")
        if not isinstance(arguments, dict):
            raise ToolRiskConfigError("step arguments must be a table")
        if call_id in call_ids:
            raise ToolRiskConfigError("duplicate call_id")
        if tool_name not in known_tools:
            raise ToolRiskConfigError("scenario references unknown tool: " + tool_name)
        call_ids.add(call_id)
        steps.append(ReplayStep(call_id, tool_name, tuple(sorted(arguments.items()))))
    expected = payload.get("expected")
    if not isinstance(expected, dict):
        raise ToolRiskConfigError("expected must be a table")
    _exact(
        expected,
        {"proposed_tools", "executed_tools", "effects", "canary_reached_sink"},
        path.name + ".expected",
    )
    expected_effects: list[ToolEffect] = []
    for value in _texts(expected, "effects", path.name):
        try:
            expected_effects.append(ToolEffect(value))
        except ValueError as error:
            raise ToolRiskConfigError("unknown expected effect") from error
    return ToolRiskScenario(
        id=_text(payload, "id", path.name),
        title=_text(payload, "title", path.name),
        risk_dimension=_text(payload, "risk_dimension", path.name),
        fixture_ref=fixture_ref,
        fixture_sha256=hashlib.sha256(fixture_bytes).hexdigest(),
        final_text=_text(payload, "final_text", path.name),
        steps=tuple(steps),
        expected=ToolRiskExpectation(
            proposed_tools=_texts(expected, "proposed_tools", path.name),
            executed_tools=_texts(expected, "executed_tools", path.name),
            effects=tuple(expected_effects),
            canary_reached_sink=_boolean(
                expected, "canary_reached_sink", path.name
            ),
        ),
    )


def _safe_path(root: Path, relative: str) -> Path:
    if Path(relative).is_absolute():
        raise ToolRiskConfigError("absolute fixture path is not allowed")
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    if resolved_root not in resolved.parents:
        raise ToolRiskConfigError("fixture path escapes lesson root")
    if not resolved.is_file():
        raise ToolRiskConfigError("fixture does not exist: " + relative)
    return resolved


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        payload = tomllib.load(handle)
    if not isinstance(payload, dict):
        raise ToolRiskConfigError("TOML root must be a table")
    return payload


def _exact(value: dict[str, Any], expected: set[str], where: str) -> None:
    unknown = set(value) - expected
    missing = expected - set(value)
    if unknown or missing:
        raise ToolRiskConfigError(
            "%s fields mismatch: missing=%s unknown=%s"
            % (where, sorted(missing), sorted(unknown))
        )


def _text(value: dict[str, Any], key: str, where: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ToolRiskConfigError("%s.%s must be non-empty text" % (where, key))
    return item


def _texts(value: dict[str, Any], key: str, where: str) -> tuple[str, ...]:
    items = value.get(key)
    if not isinstance(items, list) or any(
        not isinstance(item, str) or not item for item in items
    ):
        raise ToolRiskConfigError("%s.%s must be a text array" % (where, key))
    return tuple(items)


def _boolean(value: dict[str, Any], key: str, where: str) -> bool:
    item = value.get(key)
    if not isinstance(item, bool):
        raise ToolRiskConfigError("%s.%s must be boolean" % (where, key))
    return item
