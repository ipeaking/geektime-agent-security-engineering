"""按控制变量构建模型看到的内容和确定性 Context Trace。"""

from hashlib import sha256
from pathlib import Path
from typing import List

from .errors import CaseLoadError, UnsupportedWrapperError
from .loader import resolve_fixture
from .models import BuiltContext, ContextItem, ContextTrace, ExperimentCase


PAYLOAD_MARKER = "{{INJECTION_PAYLOAD}}"
PREVIEW_LIMIT = 160


def wrap_payload(payload: str, wrapper: str) -> str:
    """只改变 Payload 外层文本，不删除或改写 Payload 本体。"""

    if wrapper == "none":
        return payload
    if wrapper == "delimiter":
        return (
            "--- BEGIN UNTRUSTED WEB CONTENT ---\n\n"
            + payload
            + "\n--- END UNTRUSTED WEB CONTENT ---"
        )
    if wrapper == "source_label":
        return (
            "[SOURCE: external_web]\n"
            "[TRUST: untrusted]\n"
            "[INTENDED_ROLE: data]\n"
            "[PURPOSE: summarize_only]\n\n"
            + payload
        )
    raise UnsupportedWrapperError(wrapper)


def build_context(case: ExperimentCase, lesson_root: Path) -> BuiltContext:
    """构造一次独立实验所需的 Prompt、消息、页面和 Trace。"""

    prompt_path = lesson_root / "prompts" / (case.prompt_profile + ".txt")
    system_prompt = prompt_path.read_text(encoding="utf-8").strip()
    if case.page_fixture is None:
        raise CaseLoadError("case has no page fixture: %s" % case.id)
    template = resolve_fixture(lesson_root, case.page_fixture).read_text(
        encoding="utf-8"
    )

    if case.payload_fixture is None:
        page_content = template
    else:
        payload = resolve_fixture(lesson_root, case.payload_fixture).read_text(
            encoding="utf-8"
        )
        if PAYLOAD_MARKER not in template:
            raise CaseLoadError("injection template has no payload marker: %s" % case.id)
        page_content = template.replace(
            PAYLOAD_MARKER,
            wrap_payload(payload, case.wrapper),
        )

    items: List[ContextItem] = [
        _item("CTX-001", "system", "trusted", "instruction", "instructions", system_prompt),
        _item("CTX-002", "user", "user_controlled", "instruction", "user_message", case.task),
    ]

    if case.channel == "inline_quoted_content":
        user_message = (
            case.task
            + "\n\n--- BEGIN QUOTED MATERIAL ---\n"
            + page_content
            + "\n--- END QUOTED MATERIAL ---"
        )
        items.append(
            _item(
                "CTX-003",
                "user_embedded_content",
                "user_controlled",
                "data",
                "user_message",
                page_content,
            )
        )
        live_page_content = None
    else:
        user_message = case.task
        items.append(
            _item(
                "CTX-003",
                "webpage",
                "untrusted",
                "data",
                "function_call_output",
                page_content,
            )
        )
        live_page_content = page_content

    return BuiltContext(
        case=case,
        system_prompt=system_prompt,
        user_message=user_message,
        page_content=live_page_content,
        trace=ContextTrace(case_id=case.id, items=tuple(items)),
    )


def _item(
    item_id: str,
    source: str,
    trust: str,
    intended_role: str,
    transport: str,
    content: str,
) -> ContextItem:
    preview = " ".join(content.split())[:PREVIEW_LIMIT]
    return ContextItem(
        id=item_id,
        source=source,
        trust=trust,
        intended_role=intended_role,
        transport=transport,
        content_sha256=sha256(content.encode("utf-8")).hexdigest(),
        content_preview=preview,
    )
