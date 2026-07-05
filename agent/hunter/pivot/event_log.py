from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class PivotEvent:
    event_id: str
    seq: int
    ts: str
    task_id: str
    parent_event_id: str | None
    ip: str
    type: str
    description: str
    action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "seq": self.seq,
            "ts": self.ts,
            "task_id": self.task_id,
            "parent_event_id": self.parent_event_id,
            "ip": self.ip,
            "type": self.type,
            "description": self.description,
            "action": self.action,
        }


class EventLog:
    """Append-only audit log. Only the orchestrator writes here — never the LLM."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pivot_events (
                event_id TEXT PRIMARY KEY,
                seq INTEGER NOT NULL,
                ts TEXT NOT NULL,
                task_id TEXT NOT NULL,
                parent_event_id TEXT,
                ip TEXT NOT NULL,
                type TEXT NOT NULL,
                description TEXT NOT NULL,
                action TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def append(
        self,
        *,
        task_id: str,
        parent_event_id: str | None,
        ip: str,
        type: str,
        description: str,
        action: str,
    ) -> PivotEvent:
        seq = self._next_seq()
        event = PivotEvent(
            event_id=f"evt-{uuid.uuid4().hex[:12]}",
            seq=seq,
            ts=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            task_id=task_id,
            parent_event_id=parent_event_id,
            ip=ip,
            type=type,
            description=description,
            action=action,
        )
        self._conn.execute(
            """
            INSERT INTO pivot_events
            (event_id, seq, ts, task_id, parent_event_id, ip, type, description, action)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.seq,
                event.ts,
                event.task_id,
                event.parent_event_id,
                event.ip,
                event.type,
                event.description,
                event.action,
            ),
        )
        self._conn.commit()
        return event

    def _next_seq(self) -> int:
        row = self._conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM pivot_events").fetchone()
        return int(row[0])

    def all_events(self) -> list[PivotEvent]:
        rows = self._conn.execute("SELECT * FROM pivot_events ORDER BY seq ASC").fetchall()
        return [self._row_to_event(row) for row in rows]

    def export_dicts(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.all_events()]

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> PivotEvent:
        return PivotEvent(
            event_id=row["event_id"],
            seq=row["seq"],
            ts=row["ts"],
            task_id=row["task_id"],
            parent_event_id=row["parent_event_id"],
            ip=row["ip"],
            type=row["type"],
            description=row["description"],
            action=row["action"],
        )

    def close(self) -> None:
        self._conn.close()
