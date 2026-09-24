"""实验使用的只追加 JSON Lines 审计日志。"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class AuditLogger:
    def __init__(self, output_path: Optional[Path] = None) -> None:
        self.output_path = output_path
        self.events: List[Dict[str, Any]] = []
        if self.output_path is not None:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, **details: Any) -> Dict[str, Any]:
        event: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            **details,
        }
        self.events.append(event)

        if self.output_path is not None:
            with self.output_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

        return event
