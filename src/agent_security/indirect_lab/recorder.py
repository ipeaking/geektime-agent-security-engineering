"""保存裁剪后的第 04 讲 Live 观察。"""

import json
from pathlib import Path

from .models import LiveObservation


class ObservationRecorder:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.runs_dir = output_dir / "runs"
        self.jsonl_path = output_dir / "live_runs.jsonl"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def next_run_index(self, case_id: str) -> int:
        if not self.jsonl_path.is_file():
            return 1
        highest = 0
        for line in self.jsonl_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                data = json.loads(line)
                if data.get("case_id") == case_id:
                    highest = max(highest, int(data.get("run_index", 0)))
        return highest + 1

    def append(self, observation: LiveObservation) -> None:
        payload = observation.to_dict()
        with self.jsonl_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
        path = self.runs_dir / (
            "%s-run-%03d.json" % (observation.case_id.lower(), observation.run_index)
        )
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
