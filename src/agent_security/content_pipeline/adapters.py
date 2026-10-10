"""按来源类型选择内容 Adapter。"""

from pathlib import Path

from .base import ContentAdapter
from .email_adapter import EmailContentAdapter
from .errors import ContentPipelineError
from .models import ContentEnvelope, ContentSource
from .pdf_adapter import PdfContentAdapter
from .rag_adapter import RagContentAdapter
from .web_adapter import WebContentAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ContentAdapter] = {
            "web": WebContentAdapter(),
            "pdf": PdfContentAdapter(),
            "email": EmailContentAdapter(),
            "rag_document": RagContentAdapter(),
        }

    def load(self, source: ContentSource, lesson_root: Path) -> ContentEnvelope:
        adapter = self._adapters.get(source.source_type)
        if adapter is None:
            raise ContentPipelineError("unsupported source_type: %s" % source.source_type)
        return adapter.load(source, lesson_root)
