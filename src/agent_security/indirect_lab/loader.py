"""严格加载第 04 讲的 TOML Case。"""

import tomllib
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple

from agent_security.content_pipeline.base import resolve_source
from agent_security.content_pipeline.errors import ContentPipelineError

from .errors import CaseLoadError
from .models import CarrierCase


SUPPORTED_CARRIERS = {"web", "pdf", "email", "rag_document"}
SUPPORTED_VARIANTS = {"clean", "injected"}
SUPPORTED_MEDIA_TYPES = {
    "web": "text/html",
    "pdf": "application/pdf",
    "email": "message/rfc822",
    "rag_document": "application/json",
}
REQUIRED_FIELDS = {
    "id",
    "title",
    "description",
    "carrier",
    "variant",
    "task",
    "source_fixture",
    "model_source_ref",
    "media_type",
    "expected_normal_facts",
}
OPTIONAL_FIELDS = {"payload_fixture", "retrieval_query"}


def load_cases(cases_dir: Path) -> Tuple[CarrierCase, ...]:
    if not cases_dir.is_dir():
        raise CaseLoadError("cases directory does not exist: %s" % cases_dir)
    lesson_root = cases_dir.resolve().parent
    paths = sorted(cases_dir.glob("*.toml"))
    if not paths:
        raise CaseLoadError("no TOML cases found: %s" % cases_dir)
    cases = tuple(_load_case(path, lesson_root) for path in paths)
    identifiers = [case.id for case in cases]
    if len(set(identifiers)) != len(identifiers):
        raise CaseLoadError("duplicate case id")
    return cases


def _load_case(path: Path, lesson_root: Path) -> CarrierCase:
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except tomllib.TOMLDecodeError as error:
        raise CaseLoadError("invalid TOML in %s" % path.name) from error
    missing = sorted(REQUIRED_FIELDS - set(data))
    unknown = sorted(set(data) - REQUIRED_FIELDS - OPTIONAL_FIELDS)
    if missing:
        raise CaseLoadError("%s missing fields: %s" % (path.name, ", ".join(missing)))
    if unknown:
        raise CaseLoadError("%s has unknown fields: %s" % (path.name, ", ".join(unknown)))

    carrier = _text(data, "carrier", path.name)
    variant = _text(data, "variant", path.name)
    media_type = _text(data, "media_type", path.name)
    if carrier not in SUPPORTED_CARRIERS:
        raise CaseLoadError("%s has unknown carrier: %s" % (path.name, carrier))
    if variant not in SUPPORTED_VARIANTS:
        raise CaseLoadError("%s has unknown variant: %s" % (path.name, variant))
    if media_type != SUPPORTED_MEDIA_TYPES[carrier]:
        raise CaseLoadError("%s media_type does not match carrier" % path.name)

    source_fixture = _text(data, "source_fixture", path.name)
    payload_fixture = _optional_text(data, "payload_fixture", path.name)
    try:
        resolve_source(lesson_root, source_fixture)
        if payload_fixture:
            resolve_source(lesson_root, payload_fixture)
    except ContentPipelineError as error:
        raise CaseLoadError(str(error)) from error
    retrieval_query = _optional_text(data, "retrieval_query", path.name)
    if carrier == "rag_document" and not retrieval_query:
        raise CaseLoadError("%s RAG case requires retrieval_query" % path.name)
    if carrier != "rag_document" and retrieval_query is not None:
        raise CaseLoadError("%s non-RAG case cannot set retrieval_query" % path.name)

    return CarrierCase(
        id=_text(data, "id", path.name),
        title=_text(data, "title", path.name),
        description=_text(data, "description", path.name),
        carrier=carrier,
        variant=variant,
        task=_text(data, "task", path.name),
        source_fixture=source_fixture,
        model_source_ref=_text(data, "model_source_ref", path.name),
        media_type=media_type,
        payload_fixture=payload_fixture,
        retrieval_query=retrieval_query,
        expected_normal_facts=_texts(data, "expected_normal_facts", path.name),
    )


def _text(data: Mapping[str, Any], key: str, location: str) -> str:
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        raise CaseLoadError("%s.%s must be a non-empty string" % (location, key))
    return value


def _optional_text(data: Mapping[str, Any], key: str, location: str) -> Optional[str]:
    if key not in data:
        return None
    return _text(data, key, location)


def _texts(data: Mapping[str, Any], key: str, location: str) -> Tuple[str, ...]:
    value = data[key]
    if not isinstance(value, list) or not value or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise CaseLoadError("%s.%s must be a non-empty string list" % (location, key))
    return tuple(value)
