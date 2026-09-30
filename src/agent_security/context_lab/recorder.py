"""保存经过裁剪的 Live 客观观察，不记录隐藏推理或敏感内容。"""

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
        """在已有观察后继续编号，避免覆盖之前的单次记录。"""

        if not self.jsonl_path.is_file():
            return 1
        highest = 0
        for line in self.jsonl_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("case_id") == case_id:
                highest = max(highest, int(data.get("run_index", 0)))
        return highest + 1

    def append(self, observation: LiveObservation) -> None:
        payload = observation.to_dict()
        with self.jsonl_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
        run_path = self.runs_dir / (
            "%s-run-%03d.json" % (observation.case_id.lower(), observation.run_index)
        )
        run_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
