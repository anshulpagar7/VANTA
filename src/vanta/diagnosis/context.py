"""Cache keys for diagnosis.

The LLM is asked about a BUCKET, not an event. Two events with the same error
slug, source, step, method, size band and attempt band get the same diagnosis,
so a 1000-event run costs a few hundred model calls at most -- and zero on a
replay. Bucketing is what makes the free-tier budget work.
"""
from __future__ import annotations

from vanta.events.models import RevenueEvent

AMOUNT_BANDS = ((50_000, "small"), (300_000, "medium"))    # paise


def amount_band(paise: int) -> str:
    for ceiling, name in AMOUNT_BANDS:
        if paise < ceiling:
            return name
    return "large"


def attempt_band(attempt_no: int) -> str:
    if attempt_no <= 1:
        return "first"
    if attempt_no <= 3:
        return "repeat"
    return "late"


def bucket_key(event: RevenueEvent, attempt_no: int) -> str:
    return "|".join((
        event.reason, event.source.value, event.step.value, event.method,
        amount_band(event.amount_paise), attempt_band(attempt_no),
    ))
