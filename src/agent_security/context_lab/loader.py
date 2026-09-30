"""严格加载第 03 讲的 TOML Case。"""

import tomllib
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from .errors import CaseLoadError
from .models import ExperimentCase


SUPPORTED_CHANNELS = {"clean_web", "inline_quoted_content", "webpage"}
SUPPORTED_PROMPT_PROFILES = {"neutral", "explicit_boundary"}
SUPPORTED_WRAPPERS = {"none", "delimiter", "source_label"}

REQUIRED_FIELDS = {
    "id",
    "title",
    "description",
    "channel",
    "prompt_profile",
    "wrapper",
    "task",
    "expected_normal_facts",
}
OPTIONAL_FIELDS = {"page_fixture", "payload_fixture"}


def load_cases(cases_dir: Path) -> Tuple[ExperimentCase, ...]:
    """按文件名排序加载全部 Case，并拒绝重复编号。"""

    if not cases_dir.is_dir():
        raise CaseLoadError("cases directory does not exist: %s" % cases_dir)
    lesson_root = cases_dir.resolve().parent
    case_paths = sorted(cases_dir.glob("*.toml"))
    if not case_paths:
        raise CaseLoadError("no TOML cases found in: %s" % cases_dir)

    cases = tuple(_load_case(path, lesson_root) for path in case_paths)
    seen = set()
    duplicates = set()
    for case in cases:
        if case.id in seen:
            duplicates.add(case.id)
        seen.add(case.id)
    if duplicates:
        raise CaseLoadError("duplicate case id: %s" % ", ".join(sorted(duplicates)))
    return cases


def _load_case(path: Path, lesson_root: Path) -> ExperimentCase:
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except tomllib.TOMLDecodeError as error:
        raise CaseLoadError("invalid TOML in %s: %s" % (path.name, error)) from error

    if not isinstance(data, dict):
        raise CaseLoadError("case must be a TOML table: %s" % path.name)
    missing = sorted(REQUIRED_FIELDS - set(data))
    unknown = sorted(set(data) - REQUIRED_FIELDS - OPTIONAL_FIELDS)
    if missing:
        raise CaseLoadError("%s missing fields: %s" % (path.name, ", ".join(missing)))
    if unknown:
        raise CaseLoadError("%s has unknown fields: %s" % (path.name, ", ".join(unknown)))

    location = path.name
    channel = _text(data, "channel", location)
    prompt_profile = _text(data, "prompt_profile", location)
    wrapper = _text(data, "wrapper", location)
    if channel not in SUPPORTED_CHANNELS:
        raise CaseLoadError("%s has unknown channel: %s" % (location, channel))
    if prompt_profile not in SUPPORTED_PROMPT_PROFILES:
        raise CaseLoadError(
            "%s has unknown prompt profile: %s" % (location, prompt_profile)
        )
    if wrapper not in SUPPORTED_WRAPPERS:
        raise CaseLoadError("%s has unknown wrapper: %s" % (location, wrapper))

    page_fixture = _optional_text(data, "page_fixture", location)
    payload_fixture = _optional_text(data, "payload_fixture", location)
    for field_name, relative_path in (
        ("page_fixture", page_fixture),
        ("payload_fixture", payload_fixture),
    ):
        if relative_path is not None:
            _validate_fixture(lesson_root, relative_path, location, field_name)

    prompt_path = lesson_root / "prompts" / (prompt_profile + ".txt")
    if not prompt_path.is_file():
        raise CaseLoadError("%s references missing prompt: %s" % (location, prompt_path.name))

    return ExperimentCase(
        id=_text(data, "id", location),
        title=_text(data, "title", location),
        description=_text(data, "description", location),
        channel=channel,
        prompt_profile=prompt_profile,
        wrapper=wrapper,
        task=_text(data, "task", location),
        page_fixture=page_fixture,
        payload_fixture=payload_fixture,
        expected_normal_facts=_texts(data, "expected_normal_facts", location),
    )


def resolve_fixture(lesson_root: Path, relative_path: str) -> Path:
    """把已经通过 Loader 检查的相对路径解析到本讲目录内。"""

    root = lesson_root.resolve()
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise CaseLoadError("fixture path escapes lesson root: %s" % relative_path) from error
    return target


def _validate_fixture(
    lesson_root: Path,
    relative_path: str,
    location: str,
    field_name: str,
) -> None:
    if Path(relative_path).is_absolute():
        raise CaseLoadError("%s.%s must be relative" % (location, field_name))
    target = resolve_fixture(lesson_root, relative_path)
    if not target.is_file():
        raise CaseLoadError(
            "%s.%s does not exist: %s" % (location, field_name, relative_path)
        )


def _text(data: Mapping[str, Any], key: str, location: str) -> str:
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        raise CaseLoadError("%s.%s must be a non-empty string" % (location, key))
    return value


def _optional_text(
    data: Mapping[str, Any], key: str, location: str
) -> Optional[str]:
    if key not in data:
        return None
    return _text(data, key, location)


def _texts(data: Mapping[str, Any], key: str, location: str) -> Tuple[str, ...]:
    value = data[key]
    if not isinstance(value, list) or not value or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise CaseLoadError(
            "%s.%s must be a non-empty list of strings" % (location, key)
        )
    return tuple(value)
