"""Dark-pattern screening for outbound customer communication.

Razorpay's published position is that Agent Studio agents must not employ dark
patterns as defined under India's Guidelines for Prevention and Regulation of
Dark Patterns, 2023 -- explicitly naming false urgency, confirm shaming, bait
and switch, drip pricing and subscription traps.

This is a lexical screen, not a classifier. It is deliberately conservative and
its false-positive rate is measured and reported (see LIMITATIONS.md), because
a screen that never fires is not a control.
"""
from __future__ import annotations

import re

FALSE_URGENCY = re.compile(
    r"\b(hurry|last chance|expires? (in|today|soon)|only \d+ left|act now|"
    r"limited time|final (call|reminder)|don't miss out)\b",
    re.IGNORECASE,
)
CONFIRM_SHAMING = re.compile(
    r"\b(no,? i don'?t want|i prefer to (lose|miss)|no thanks,? i like)\b", re.IGNORECASE
)
MANUFACTURED_SCARCITY = re.compile(r"\b(almost (gone|sold out)|selling fast|running out)\b", re.IGNORECASE)

SCREENS = {
    "false_urgency": FALSE_URGENCY,
    "confirm_shaming": CONFIRM_SHAMING,
    "manufactured_scarcity": MANUFACTURED_SCARCITY,
}


def screen(message: str, *, offer_genuinely_time_bound: bool = False) -> list[str]:
    """Return the names of screens that fired. Empty list == clean.

    A genuinely time-bound merchant offer may be communicated truthfully, so
    the false-urgency screen is suppressed when the merchant has configured a
    real deadline.
    """
    hits = []
    for name, pattern in SCREENS.items():
        if name == "false_urgency" and offer_genuinely_time_bound:
            continue
        if pattern.search(message):
            hits.append(name)
    return hits
