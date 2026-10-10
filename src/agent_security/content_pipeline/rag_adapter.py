"""确定性本地关键词检索，用于演示 RAG 内容进入上下文。"""

import json
import re
from pathlib import Path
from typing import Any

from .base import build_envelope, read_bounded, resolve_source
from .errors import ContentPipelineError
from .models import ContentEnvelope, ContentSource


TOKEN_PATTERN = re.compile(r"[a-z0-9_-]+", re.IGNORECASE)


def _tokens(text: str) -> set[str]:
    return {token.casefold() for token in TOKEN_PATTERN.findall(text)}


class RagContentAdapter:
    def __init__(self, max_bytes: int = 524_288, max_documents: int = 50) -> None:
        self.max_bytes = max_bytes
        self.max_documents = max_documents

    def load(self, source: ContentSource, lesson_root: Path) -> ContentEnvelope:
        if source.media_type != "application/json":
            raise ContentPipelineError("rag adapter requires application/json")
        if not source.retrieval_query:
            raise ContentPipelineError("rag source requires retrieval_query")
        path = resolve_source(lesson_root, source.source_ref)
        raw = read_bounded(path, self.max_bytes)
        try:
            documents = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ContentPipelineError("invalid RAG corpus") from error
        if not isinstance(documents, list) or not documents:
            raise ContentPipelineError("RAG corpus must be a non-empty list")
        if len(documents) > self.max_documents:
            raise ContentPipelineError("RAG corpus exceeds document limit")

        query_tokens = _tokens(source.retrieval_query)
        ranked: list[tuple[int, str, dict[str, Any]]] = []
        for document in documents:
            if not isinstance(document, dict) or set(document) != {"id", "title", "content"}:
                raise ContentPipelineError("RAG documents require id, title and content")
            if not all(isinstance(document[key], str) and document[key].strip() for key in document):
                raise ContentPipelineError("RAG document fields must be non-empty strings")
            searchable = "%s %s" % (document["title"], document["content"])
            score = len(query_tokens & _tokens(searchable))
            ranked.append((score, document["id"], document))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        score, document_id, selected = ranked[0]
        if score == 0:
            raise ContentPipelineError("RAG query did not match any document")
        content = "%s\n%s" % (selected["title"], selected["content"])
        return build_envelope(
            source,
            raw,
            content,
            parser="RagContentAdapter/deterministic_keyword",
            transformations=("parse_json_corpus", "keyword_retrieve_top_1"),
            metadata={
                "fixture_name": path.name,
                "query": source.retrieval_query,
                "selected_document_id": document_id,
                "score": str(score),
            },
        )
