"""把 Case、Adapter 输出和来源信息构建成模型运行上下文。"""

import hashlib
from pathlib import Path

from agent_security.content_pipeline import AdapterRegistry, ContentSource
from agent_security.content_pipeline.provenance import trace_envelope

from .models import (
    BuiltCarrierContext,
    CarrierCase,
    ProvenanceTrace,
    TraceItem,
    trace_item_from_provenance,
)


PREVIEW_LIMIT = 180


def _text_trace(
    item_id: str,
    source_type: str,
    source_ref: str,
    trust: str,
    intended_role: str,
    transport: str,
    content: str,
) -> TraceItem:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return TraceItem(
        id=item_id,
        source_type=source_type,
        source_ref=source_ref,
        trust=trust,
        intended_role=intended_role,
        parser="text",
        transport=transport,
        source_sha256=digest,
        content_sha256=digest,
        transformations=(),
        content_preview=" ".join(content.split())[:PREVIEW_LIMIT],
    )


def build_context(
    case: CarrierCase,
    lesson_root: Path,
    registry: AdapterRegistry | None = None,
) -> BuiltCarrierContext:
    prompt_path = lesson_root / "prompts" / "neutral.txt"
    system_prompt = prompt_path.read_text(encoding="utf-8").strip()
    source = ContentSource(
        id=case.source_id,
        source_type=case.carrier,
        source_ref=case.source_fixture,
        media_type=case.media_type,
        retrieval_query=case.retrieval_query,
    )
    envelope = (registry or AdapterRegistry()).load(source, lesson_root)
    user_message = "%s\n内容编号：%s" % (case.task, case.source_id)
    trace = ProvenanceTrace(
        case_id=case.id,
        items=(
            _text_trace(
                "CTX-001",
                "system",
                "prompts/neutral.txt",
                "trusted",
                "instruction",
                "instructions",
                system_prompt,
            ),
            _text_trace(
                "CTX-002",
                "user",
                case.id,
                "user_controlled",
                "instruction",
                "user_message",
                user_message,
            ),
            trace_item_from_provenance(trace_envelope(envelope)),
        ),
    )
    return BuiltCarrierContext(case, system_prompt, user_message, envelope, trace)
