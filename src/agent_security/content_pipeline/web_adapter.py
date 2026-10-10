"""从本地 HTML Fixture 确定性提取正文文本。"""

from html.parser import HTMLParser
from pathlib import Path

from .base import build_envelope, read_bounded, resolve_source
from .errors import ContentPipelineError
from .models import ContentEnvelope, ContentSource


class _DocumentTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data.strip():
            self.parts.append(data.strip())


class WebContentAdapter:
    max_bytes = 262_144

    def load(self, source: ContentSource, lesson_root: Path) -> ContentEnvelope:
        if source.media_type != "text/html":
            raise ContentPipelineError("web adapter requires text/html")
        path = resolve_source(lesson_root, source.source_ref)
        raw = read_bounded(path, self.max_bytes)
        parser = _DocumentTextParser()
        parser.feed(raw.decode("utf-8", errors="strict"))
        parser.close()
        return build_envelope(
            source,
            raw,
            "\n".join(parser.parts),
            parser="WebContentAdapter/html.parser",
            transformations=("decode_utf8", "extract_document_text"),
            metadata={"fixture_name": path.name},
        )
