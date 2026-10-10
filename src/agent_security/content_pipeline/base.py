"""Adapter 协议和共享的安全读取逻辑。"""

import hashlib
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from .errors import ContentPipelineError
from .models import ContentEnvelope, ContentSource


class ContentAdapter(Protocol):
    def load(self, source: ContentSource, lesson_root: Path) -> ContentEnvelope:
        ...


def resolve_source(lesson_root: Path, source_ref: str) -> Path:
    if Path(source_ref).is_absolute():
        raise ContentPipelineError("source_ref must be relative")
    root = lesson_root.resolve()
    target = (root / source_ref).resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise ContentPipelineError("source_ref escapes lesson root: %s" % source_ref) from error
    if not target.is_file():
        raise ContentPipelineError("content source does not exist: %s" % source_ref)
    return target


def read_bounded(path: Path, max_bytes: int) -> bytes:
    size = path.stat().st_size
    if size > max_bytes:
        raise ContentPipelineError("content source exceeds %d bytes" % max_bytes)
    return path.read_bytes()


def normalize_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines()).strip()


def build_envelope(
    source: ContentSource,
    raw: bytes,
    content: str,
    parser: str,
    transformations: Sequence[str],
    metadata: Mapping[str, str],
) -> ContentEnvelope:
    normalized = normalize_text(content)
    if not normalized:
        raise ContentPipelineError("adapter produced empty content")
    return ContentEnvelope(
        id=source.id,
        source_type=source.source_type,
        source_ref=source.source_ref,
        media_type=source.media_type,
        trust=source.trust,
        intended_role=source.intended_role,
        parser=parser,
        content=normalized,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        content_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        transformations=tuple(transformations),
        metadata=tuple(sorted((str(key), str(value)) for key, value in metadata.items())),
    )
