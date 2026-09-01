from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Limits:
    """Merchant-configured bounds. Every value here is a defensible knob and a
    sensitivity-sweep axis."""
    quiet_hours_start: int = 21      # local hour, inclusive
    quiet_hours_end: int = 8         # local hour, exclusive
    max_contacts_per_7d: int = 3
    contact_cooldown_hours: int = 24
    max_attempts_per_event: int = 4
    spend_cap_paise: int = 500_00    # per customer, per recovery episode


DEFAULT_LIMITS = Limits()
