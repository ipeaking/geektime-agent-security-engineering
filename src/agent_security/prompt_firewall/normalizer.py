"""只为检测生成规范化文本，不修改原始 ContentEnvelope。"""

import hashlib
import html
import re
import unicodedata

from .models import NormalizedContent


ZERO_WIDTH_CHARACTERS = {"\u200b", "\u200c", "\u200d", "\ufeff"}
TRANSFORMATIONS = (
    "normalize_newlines",
    "html_entity_decode_once",
    "unicode_nfkc",
    "remove_selected_zero_width_characters",
    "unicode_casefold",
    "collapse_whitespace",
    "strip",
)


class ContentNormalizer:
    def normalize(self, content: str) -> NormalizedContent:
        original_sha256 = _sha256(content)
        text = content.replace("\r\n", "\n").replace("\r", "\n")
        text = html.unescape(text)
        text = unicodedata.normalize("NFKC", text)
        text = "".join(char for char in text if char not in ZERO_WIDTH_CHARACTERS)
        text = text.casefold()
        text = re.sub(r"\s+", " ", text).strip()
        return NormalizedContent(
            original_sha256=original_sha256,
            normalized_sha256=_sha256(text),
            text=text,
            transformations=TRANSFORMATIONS,
        )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
