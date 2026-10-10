"""从受限的 RFC 5322 邮件 Fixture 提取头部和纯文本正文。"""

from email import policy
from email.parser import BytesParser
from pathlib import Path

from .base import build_envelope, read_bounded, resolve_source
from .errors import ContentPipelineError
from .models import ContentEnvelope, ContentSource


class EmailContentAdapter:
    def __init__(
        self,
        max_bytes: int = 262_144,
        max_parts: int = 20,
        max_chars: int = 100_000,
    ) -> None:
        self.max_bytes = max_bytes
        self.max_parts = max_parts
        self.max_chars = max_chars

    def load(self, source: ContentSource, lesson_root: Path) -> ContentEnvelope:
        if source.media_type != "message/rfc822":
            raise ContentPipelineError("email adapter requires message/rfc822")
        path = resolve_source(lesson_root, source.source_ref)
        raw = read_bounded(path, self.max_bytes)
        try:
            message = BytesParser(policy=policy.default).parsebytes(raw)
        except Exception as error:
            raise ContentPipelineError("invalid email fixture: %s" % path.name) from error

        parts = list(message.walk()) if message.is_multipart() else [message]
        if len(parts) > self.max_parts:
            raise ContentPipelineError("email exceeds MIME part limit")
        bodies: list[str] = []
        for part in parts:
            if part.get_content_disposition() == "attachment":
                raise ContentPipelineError("email attachments are not supported")
            if part.get_content_type() == "text/plain":
                payload = part.get_content()
                if isinstance(payload, str):
                    bodies.append(payload)
        if not bodies:
            raise ContentPipelineError("email has no text/plain body")
        content = "\n".join(
            [
                "Subject: %s" % (message.get("Subject", "")),
                "From: %s" % (message.get("From", "")),
                "To: %s" % (message.get("To", "")),
                "",
                *bodies,
            ]
        )
        if len(content) > self.max_chars:
            raise ContentPipelineError("email extracted text exceeds character limit")
        return build_envelope(
            source,
            raw,
            content,
            parser="EmailContentAdapter/email.parser",
            transformations=("parse_rfc5322", "select_text_plain"),
            metadata={
                "fixture_name": path.name,
                "subject": str(message.get("Subject", ""))[:200],
            },
        )
