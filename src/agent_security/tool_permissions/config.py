"""严格加载第 08 讲 Tool Permission System 配置。"""

import tomllib
from pathlib import Path
from typing import Any

from agent_security.models import ToolCall

from .models import (
    PermissionOutcome,
    PermissionPolicy,
    PermissionScenario,
    SubjectContext,
    TaskContract,
    ToolCapability,
    ToolManifest,
)


EXPECTED_CHECK_ORDER = (
    "request_valid",
    "tool_registered",
    "subject_role_allowed",
    "tool_allowed_by_task",
    "capabilities_allowed_by_task",
)


class ToolPermissionConfigError(ValueError):
    pass


def load_tools(path: Path) -> tuple[ToolManifest, ...]:
    payload = _toml(path)
    _exact(payload, {"schema_version", "tools"}, path.name)
    _version(payload)
    rows = _tables(payload, "tools", path.name)
    tools: list[ToolManifest] = []
    for row in rows:
        _exact(
            row,
            {
                "name",
                "description",
                "capabilities",
                "required_arguments",
                "optional_arguments",
                "argument_types",
            },
            "tools",
        )
        capabilities = _capabilities(row, "capabilities", "tools")
        required = _texts(row, "required_arguments", "tools")
        optional = _texts(row, "optional_arguments", "tools")
        if set(required) & set(optional):
            raise ToolPermissionConfigError("tool arguments overlap")
        argument_types = row.get("argument_types")
        if not isinstance(argument_types, dict) or any(
            not isinstance(key, str) or value not in {"string", "integer", "object"}
            for key, value in argument_types.items()
        ):
            raise ToolPermissionConfigError("argument_types must be a supported map")
        if set(argument_types) != set(required) | set(optional):
            raise ToolPermissionConfigError("argument_types must cover declared arguments")
        tools.append(
            ToolManifest(
                name=_text(row, "name", "tools"),
                description=_text(row, "description", "tools"),
                capabilities=capabilities,
                required_arguments=required,
                optional_arguments=optional,
                argument_types=tuple(sorted(argument_types.items())),
            )
        )
    _unique([item.name for item in tools], "tool name")
    return tuple(tools)


def load_subjects(path: Path) -> tuple[SubjectContext, ...]:
    payload = _toml(path)
    _exact(payload, {"schema_version", "subjects"}, path.name)
    _version(payload)
    subjects: list[SubjectContext] = []
    for row in _tables(payload, "subjects", path.name):
        _exact(row, {"id", "display_name", "roles"}, "subjects")
        subjects.append(
            SubjectContext(
                id=_text(row, "id", "subjects"),
                display_name=_text(row, "display_name", "subjects"),
                roles=_texts(row, "roles", "subjects"),
            )
        )
    _unique([item.id for item in subjects], "subject id")
    return tuple(subjects)


def load_tasks(path: Path, tools: tuple[ToolManifest, ...]) -> tuple[TaskContract, ...]:
    payload = _toml(path)
    _exact(payload, {"schema_version", "tasks"}, path.name)
    _version(payload)
    known_tools = {item.name for item in tools}
    tasks: list[TaskContract] = []
    for row in _tables(payload, "tasks", path.name):
        _exact(
            row,
            {"id", "display_name", "allowed_roles", "allowed_tools", "allowed_capabilities"},
            "tasks",
        )
        allowed_tools = _texts(row, "allowed_tools", "tasks")
        if not set(allowed_tools) <= known_tools:
            raise ToolPermissionConfigError("task references unknown tool")
        tasks.append(
            TaskContract(
                id=_text(row, "id", "tasks"),
                display_name=_text(row, "display_name", "tasks"),
                allowed_roles=_texts(row, "allowed_roles", "tasks"),
                allowed_tools=allowed_tools,
                allowed_capabilities=_capabilities(row, "allowed_capabilities", "tasks"),
            )
        )
    _unique([item.id for item in tasks], "task id")
    return tuple(tasks)


def load_policy(path: Path) -> PermissionPolicy:
    payload = _toml(path)
    _exact(payload, {"schema_version", "version", "check_order"}, path.name)
    _version(payload)
    order = _texts(payload, "check_order", path.name)
    if order != EXPECTED_CHECK_ORDER:
        raise ToolPermissionConfigError("policy check_order must match the executable contract")
    return PermissionPolicy(_text(payload, "version", path.name), order)


def load_scenarios(
    scenarios_dir: Path,
    subjects: tuple[SubjectContext, ...],
    tasks: tuple[TaskContract, ...],
) -> tuple[PermissionScenario, ...]:
    subject_ids = {item.id for item in subjects}
    task_ids = {item.id for item in tasks}
    scenarios: list[PermissionScenario] = []
    for path in sorted(scenarios_dir.glob("*.toml")):
        payload = _toml(path)
        _exact(
            payload,
            {
                "schema_version",
                "id",
                "title",
                "subject_id",
                "task_id",
                "tool_call",
                "expected",
            },
            path.name,
        )
        _version(payload)
        subject_id = _text(payload, "subject_id", path.name)
        task_id = _text(payload, "task_id", path.name)
        if subject_id not in subject_ids:
            raise ToolPermissionConfigError("scenario references unknown subject")
        if task_id not in task_ids:
            raise ToolPermissionConfigError("scenario references unknown task")
        call = payload.get("tool_call")
        if not isinstance(call, dict):
            raise ToolPermissionConfigError("tool_call must be a table")
        _exact(call, {"name", "arguments"}, path.name + ".tool_call")
        arguments = call.get("arguments")
        if not isinstance(arguments, dict):
            raise ToolPermissionConfigError("tool_call.arguments must be a table")
        expected = payload.get("expected")
        if not isinstance(expected, dict):
            raise ToolPermissionConfigError("expected must be a table")
        _exact(expected, {"outcome", "reason", "delegated"}, path.name + ".expected")
        try:
            outcome = PermissionOutcome(_text(expected, "outcome", path.name))
        except ValueError as error:
            raise ToolPermissionConfigError("unknown expected outcome") from error
        scenarios.append(
            PermissionScenario(
                id=_text(payload, "id", path.name),
                title=_text(payload, "title", path.name),
                subject_id=subject_id,
                task_id=task_id,
                tool_call=ToolCall(
                    name=_text(call, "name", path.name),
                    arguments=arguments,
                    reason="deterministic lesson-08 replay",
                    call_id=_text(payload, "id", path.name) + "-CALL-001",
                ),
                expected_outcome=outcome,
                expected_reason=_text(expected, "reason", path.name),
                expected_delegated=_boolean(expected, "delegated", path.name),
            )
        )
    if not scenarios:
        raise ToolPermissionConfigError("no scenarios found")
    _unique([item.id for item in scenarios], "scenario id")
    return tuple(scenarios)


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        value = tomllib.load(handle)
    if not isinstance(value, dict):
        raise ToolPermissionConfigError("TOML root must be a table")
    return value


def _version(value: dict[str, Any]) -> None:
    if value.get("schema_version") != "1.0":
        raise ToolPermissionConfigError("unsupported schema_version")


def _exact(value: dict[str, Any], expected: set[str], where: str) -> None:
    missing = expected - set(value)
    unknown = set(value) - expected
    if missing or unknown:
        raise ToolPermissionConfigError(
            "%s fields mismatch: missing=%s unknown=%s"
            % (where, sorted(missing), sorted(unknown))
        )


def _tables(value: dict[str, Any], key: str, where: str) -> list[dict[str, Any]]:
    rows = value.get(key)
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        raise ToolPermissionConfigError("%s.%s must be a non-empty table array" % (where, key))
    return rows


def _text(value: dict[str, Any], key: str, where: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise ToolPermissionConfigError("%s.%s must be non-empty text" % (where, key))
    return item


def _texts(value: dict[str, Any], key: str, where: str) -> tuple[str, ...]:
    items = value.get(key)
    if not isinstance(items, list) or any(not isinstance(item, str) or not item for item in items):
        raise ToolPermissionConfigError("%s.%s must be a text array" % (where, key))
    if len(items) != len(set(items)):
        raise ToolPermissionConfigError("%s.%s contains duplicates" % (where, key))
    return tuple(items)


def _capabilities(value: dict[str, Any], key: str, where: str) -> tuple[ToolCapability, ...]:
    try:
        return tuple(ToolCapability(item) for item in _texts(value, key, where))
    except ValueError as error:
        raise ToolPermissionConfigError("unknown capability") from error


def _boolean(value: dict[str, Any], key: str, where: str) -> bool:
    item = value.get(key)
    if not isinstance(item, bool):
        raise ToolPermissionConfigError("%s.%s must be boolean" % (where, key))
    return item


def _unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ToolPermissionConfigError("duplicate " + label)
