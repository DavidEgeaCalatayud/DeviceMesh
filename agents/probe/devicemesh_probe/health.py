from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path


class ProbeHealthState:
    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": "alive",
            "pid": os.getpid(),
            "updatedAt": datetime.now(UTC).isoformat(),
            "monotonic": time.monotonic(),
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        temporary.replace(self.path)

    def healthy(self, stale_after_seconds: float) -> bool:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            updated = datetime.fromisoformat(str(payload["updatedAt"]))
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return False
        if updated.tzinfo is None:
            return False
        age = (datetime.now(UTC) - updated).total_seconds()
        return 0 <= age <= stale_after_seconds


async def maintain_liveness(state: ProbeHealthState, interval_seconds: float = 10.0) -> None:
    while True:
        state.write()
        await asyncio.sleep(interval_seconds)
