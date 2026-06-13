"""Stage 6 — Trajectory: every call is appended to the session JSONL,
successes and denials alike."""

import json
from datetime import datetime, timezone
from pathlib import Path


class Trajectory:
    def __init__(self, path: Path, session_id: str):
        self.path = Path(path)
        self.session_id = session_id

    def record(self, **fields) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session": self.session_id,
            **fields,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
