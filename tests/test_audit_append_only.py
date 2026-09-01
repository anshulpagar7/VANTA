import sqlite3
from datetime import datetime

import pytest

from vanta.store.audit import AuditLog, AuditRecord

NOW = datetime(2026, 9, 1, 12, 0)


def _rec(**kw):
    base = dict(
        run_id="r1", arm="naive", seed=11, decided_at=NOW, event_id="e1",
        customer_id="c1", attempt_no=1, reason_slug="gateway_timeout",
        amount_paise=10_000, requested_action="schedule_retry", outcome="authorized",
    )
    base.update(kw)
    return AuditRecord(**base)


def test_records_append_and_read_back():
    log = AuditLog()
    log.append(_rec())
    log.append(_rec(attempt_no=2, outcome="blocked", block_reason="cooldown_active"))
    log.commit()
    rows = log.trace("e1")
    assert [r["attempt_no"] for r in rows] == [1, 2]


def test_update_is_rejected_by_the_database():
    log = AuditLog()
    log.append(_rec())
    log.commit()
    with pytest.raises(sqlite3.IntegrityError):
        log.conn.execute("UPDATE audit SET outcome='authorized'")


def test_delete_is_rejected_by_the_database():
    log = AuditLog()
    log.append(_rec())
    log.commit()
    with pytest.raises(sqlite3.IntegrityError):
        log.conn.execute("DELETE FROM audit")
