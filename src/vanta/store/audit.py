"""Append-only audit log.

Every decision -- authorized, blocked, abstained, review-required -- is written
here with its full trace. Append-only is enforced by SQLite triggers, not by
convention: UPDATE and DELETE abort at the database level.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    arm             TEXT NOT NULL,
    seed            INTEGER NOT NULL,
    decided_at      TEXT NOT NULL,
    event_id        TEXT NOT NULL,
    customer_id     TEXT NOT NULL,
    attempt_no      INTEGER NOT NULL,
    reason_slug     TEXT NOT NULL,
    amount_paise    INTEGER NOT NULL,
    diagnosed_cause TEXT,
    confidence      REAL,
    rationale       TEXT,
    requested_action TEXT NOT NULL,
    outcome         TEXT NOT NULL,
    block_reason    TEXT,
    authorization_id TEXT,
    cost_paise      INTEGER NOT NULL DEFAULT 0,
    succeeded       INTEGER,
    recovered_paise INTEGER NOT NULL DEFAULT 0,
    world_trace     TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_run ON audit(run_id, arm);
CREATE INDEX IF NOT EXISTS idx_audit_event ON audit(event_id);

CREATE TRIGGER IF NOT EXISTS audit_no_update
BEFORE UPDATE ON audit
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;

CREATE TRIGGER IF NOT EXISTS audit_no_delete
BEFORE DELETE ON audit
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
"""

_COLS = [
    "run_id", "arm", "seed", "decided_at", "event_id", "customer_id",
    "attempt_no", "reason_slug", "amount_paise", "diagnosed_cause",
    "confidence", "rationale", "requested_action", "outcome", "block_reason",
    "authorization_id", "cost_paise", "succeeded", "recovered_paise",
    "world_trace",
]


@dataclass
class AuditRecord:
    run_id: str
    arm: str
    seed: int
    decided_at: datetime
    event_id: str
    customer_id: str
    attempt_no: int
    reason_slug: str
    amount_paise: int
    requested_action: str
    outcome: str
    diagnosed_cause: str | None = None
    confidence: float | None = None
    rationale: str | None = None
    block_reason: str | None = None
    authorization_id: str | None = None
    cost_paise: int = 0
    succeeded: bool | None = None
    recovered_paise: int = 0
    world_trace: str | None = None


class AuditLog:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.conn = sqlite3.connect(str(path))
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def append(self, rec: AuditRecord) -> None:
        values = []
        for c in _COLS:
            v = getattr(rec, c)
            if isinstance(v, datetime):
                v = v.isoformat()
            elif isinstance(v, bool):
                v = int(v)
            values.append(v)
        self.conn.execute(
            f"INSERT INTO audit ({','.join(_COLS)}) VALUES ({','.join('?' * len(_COLS))})",
            values,
        )

    def commit(self) -> None:
        self.conn.commit()

    def trace(self, event_id: str) -> list[sqlite3.Row]:
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.execute(
            "SELECT * FROM audit WHERE event_id=? ORDER BY id", (event_id,)
        )
        return cur.fetchall()

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()
