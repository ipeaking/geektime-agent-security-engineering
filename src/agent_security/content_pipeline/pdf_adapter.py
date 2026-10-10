"""从受限的本地文字型 PDF 提取文本。"""

from io import BytesIO
from pathlib import Path

from .base import build_envelope, read_bounded, resolve_source
from .errors import ContentPipelineError
from .models import ContentEnvelope, ContentSource


class PdfContentAdapter:
    def __init__(
        self,
        max_bytes: int = 1_048_576,
        max_pages: int = 8,
        max_chars: int = 100_000,
    ) -> None:
        self.max_bytes = max_bytes
        self.max_pages = max_pages
        self.max_chars = max_chars

    def load(self, source: ContentSource, lesson_root: Path) -> ContentEnvelope:
        if source.media_type != "application/pdf":
            raise ContentPipelineError("pdf adapter requires application/pdf")
        try:
            from pypdf import PdfReader
        except ImportError as error:
            raise ContentPipelineError(
                "PDF parsing requires: pip install -e '.[lesson04]'"
            ) from error

        path = resolve_source(lesson_root, source.source_ref)
        raw = read_bounded(path, self.max_bytes)
        try:
            reader = PdfReader(BytesIO(raw), strict=True)
        except Exception as error:
            raise ContentPipelineError("invalid PDF fixture: %s" % path.name) from error
        if reader.is_encrypted:
            raise ContentPipelineError("encrypted PDFs are not supported")
        if len(reader.pages) > self.max_pages:
            raise ContentPipelineError("PDF exceeds page limit")
        content = "\n".join((page.extract_text() or "") for page in reader.pages)
        if len(content) > self.max_chars:
            raise ContentPipelineError("PDF extracted text exceeds character limit")
        return build_envelope(
            source,
            raw,
            content,
            parser="PdfContentAdapter/pypdf",
            transformations=("parse_pdf", "extract_text"),
            metadata={"fixture_name": path.name, "page_count": str(len(reader.pages))},
        )
