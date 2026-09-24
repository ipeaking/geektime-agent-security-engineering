"""合成工作区文件读取工具。

工作区限制属于环境安全护栏，不是 Agent 授权策略：
即使用户没有在当前任务中授权，存在安全缺陷的 Agent
仍然可以读取这个工作区中的所有文件。
"""

from pathlib import Path
from typing import Any, Dict

from .base import Tool


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read a UTF-8 file from the project workspace."

    def __init__(self, workspace_root: Path, max_bytes: int = 65_536) -> None:
        self.workspace_root = workspace_root.resolve()
        self.max_bytes = max_bytes

    def execute(self, **arguments: Any) -> Dict[str, Any]:
        relative_path = str(arguments["path"])
        target = (self.workspace_root / relative_path).resolve()

        try:
            target.relative_to(self.workspace_root)
        except ValueError as error:
            raise ValueError("path escapes the synthetic lab workspace") from error

        data = target.read_bytes()
        if len(data) > self.max_bytes:
            raise ValueError("file exceeds the lab size limit")

        return {
            "path": relative_path,
            "content": data.decode("utf-8", errors="replace"),
        }
