"""Bounded durable results. Claiming pauses when capacity is exhausted."""
import json
import os
import sqlite3
from pathlib import Path


class ResultOutbox:
    def __init__(self, path: Path, capacity: int = 10000) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.connection = sqlite3.connect(path)
        os.chmod(path, 0o600)
        self.capacity = capacity
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("CREATE TABLE IF NOT EXISTS results (work_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def count(self) -> int:
        return int(self.connection.execute("SELECT count(*) FROM results").fetchone()[0])

    def enqueue(self, payload: dict[str, object]) -> None:
        if self.count() >= self.capacity:
            raise BufferError("result outbox full; stop claiming new work")
        with self.connection:
            self.connection.execute("INSERT OR IGNORE INTO results(work_id, payload) VALUES (?, ?)",
                                    (payload["workId"], json.dumps(payload)))

    def pending(self, limit: int = 100) -> list[tuple[str, dict[str, object]]]:
        return [(key, json.loads(payload)) for key, payload in self.connection.execute(
            "SELECT work_id, payload FROM results ORDER BY rowid LIMIT ?", (limit,))]

    def acknowledge(self, work_id: str) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM results WHERE work_id = ?", (work_id,))
