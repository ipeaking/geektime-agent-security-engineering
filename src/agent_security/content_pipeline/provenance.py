"""把完整内容封装裁剪成可审计、可生成的来源追踪项。"""

from dataclasses import dataclass

from .models import ContentEnvelope


@dataclass(frozen=True)
class ProvenanceItem:
    id: str
    source_type: str
    source_ref: str
    trust: str
    intended_role: str
    parser: str
    transport: str
    source_sha256: str
    content_sha256: str
    transformations: tuple[str, ...]
    content_preview: str


def trace_envelope(
    envelope: ContentEnvelope,
    item_id: str = "CTX-003",
    preview_limit: int = 180,
) -> ProvenanceItem:
    preview = " ".join(envelope.content.split())[:preview_limit]
    return ProvenanceItem(
        id=item_id,
        source_type=envelope.source_type,
        source_ref=envelope.source_ref,
        trust=envelope.trust,
        intended_role=envelope.intended_role,
        parser=envelope.parser,
        transport="function_call_output",
        source_sha256=envelope.source_sha256,
        content_sha256=envelope.content_sha256,
        transformations=envelope.transformations,
        content_preview=preview,
    )
