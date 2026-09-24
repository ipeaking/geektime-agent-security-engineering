"""小型 Agent Runtime 共用的数据模型。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class ToolCall:
    """模型提出的动作，而不是已经获得授权的动作。"""

    name: str
    arguments: Dict[str, Any]
    reason: str
    call_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class ToolResult:
    call_id: str
    tool_name: str
    success: bool
    output: Any = None
    error: Optional[str] = None


@dataclass
class AgentRunResult:
    answer: str
    tool_calls: List[ToolCall]
    tool_results: List[ToolResult]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
