"""第 04 讲实验领域对象。"""

from dataclasses import asdict, dataclass
from typing import Any, Optional, Tuple

from agent_security.content_pipeline.models import ContentEnvelope
from agent_security.content_pipeline.provenance import ProvenanceItem


@dataclass(frozen=True)
class CarrierCase:
    id: str
    title: str
    description: str
    carrier: str
    variant: str
    task: str
    source_fixture: str
    model_source_ref: str
    media_type: str
    payload_fixture: Optional[str]
    retrieval_query: Optional[str]
    expected_normal_facts: Tuple[str, ...]

    @property
    def source_id(self) -> str:
        return self.carrier.upper().replace("_", "-") + "-SOURCE"


@dataclass(frozen=True)
class TraceItem:
    id: str
    source_type: str
    source_ref: str
    trust: str
    intended_role: str
    parser: str
    transport: str
    source_sha256: str
    content_sha256: str
    transformations: Tuple[str, ...]
    content_preview: str


@dataclass(frozen=True)
class ProvenanceTrace:
    case_id: str
    items: Tuple[TraceItem, ...]


@dataclass(frozen=True)
class BuiltCarrierContext:
    case: CarrierCase
    system_prompt: str
    user_message: str
    envelope: ContentEnvelope
    trace: ProvenanceTrace


@dataclass(frozen=True)
class LiveObservation:
    case_id: str
    carrier: str
    variant: str
    run_index: int
    provider: str
    model: str
    status: str
    proposed_tools: Tuple[str, ...]
    first_sensitive_tool: Optional[str]
    sensitive_tool_proposed: bool
    payload_in_context: bool
    source_metadata_in_context: bool
    normal_fact_hits: Tuple[str, ...]
    final_answer_preview: Optional[str]
    error_type: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    location: str
    message: str


def trace_item_from_provenance(item: ProvenanceItem) -> TraceItem:
    return TraceItem(**asdict(item))
