"""Context Lab 的不可变领域对象。"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class ContextItem:
    id: str
    source: str
    trust: str
    intended_role: str
    transport: str
    content_sha256: str
    content_preview: str


@dataclass(frozen=True)
class ExperimentCase:
    id: str
    title: str
    description: str
    channel: str
    prompt_profile: str
    wrapper: str
    task: str
    page_fixture: Optional[str]
    payload_fixture: Optional[str]
    expected_normal_facts: Tuple[str, ...]


@dataclass(frozen=True)
class ContextTrace:
    case_id: str
    items: Tuple[ContextItem, ...]


@dataclass(frozen=True)
class BuiltContext:
    case: ExperimentCase
    system_prompt: str
    user_message: str
    page_content: Optional[str]
    trace: ContextTrace


@dataclass(frozen=True)
class LiveObservation:
    case_id: str
    run_index: int
    provider: str
    model: str
    status: str
    proposed_tools: Tuple[str, ...]
    first_sensitive_tool: Optional[str]
    sensitive_tool_proposed: bool
    normal_fact_hits: Tuple[str, ...]
    final_answer_preview: Optional[str]
    error_type: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CaseValidationIssue:
    code: str
    location: str
    message: str
