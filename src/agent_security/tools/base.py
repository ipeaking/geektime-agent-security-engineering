"""每个 Agent 工具都需要实现的最小接口。"""

from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    name: str
    description: str

    @abstractmethod
    def execute(self, **arguments: Any) -> Any:
        raise NotImplementedError
