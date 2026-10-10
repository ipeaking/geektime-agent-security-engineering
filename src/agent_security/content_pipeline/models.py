"""统一内容封装的不可变领域对象。"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ContentSource:
    id: str
    source_type: str
    source_ref: str
    media_type: str
    trust: str = "untrusted"
    intended_role: str = "data"
    retrieval_query: str | None = None


@dataclass(frozen=True)
class ContentEnvelope:
    id: str
    source_type: str
    source_ref: str
    media_type: str
    trust: str
    intended_role: str
    parser: str
    content: str
    source_sha256: str
    content_sha256: str
    transformations: Tuple[str, ...]
    metadata: Tuple[Tuple[str, str], ...]

    def metadata_dict(self) -> dict[str, str]:
        return dict(self.metadata)
