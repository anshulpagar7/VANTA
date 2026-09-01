"""Domain state. Deliberately plain: the world model owns dynamics, not these."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from vanta.types import FailureSource, FailureStep


@dataclass(frozen=True)
class RevenueEvent:
    """A single unit of revenue at risk."""
    event_id: str
    customer_id: str
    amount_paise: int
    occurred_at: datetime
    source: FailureSource
    step: FailureStep
    reason: str            # Razorpay-style reason slug, e.g. "invalid_otp"
    method: str            # card | upi | netbanking | wallet | emandate
    attempt_no: int = 1
    metadata: dict = field(default_factory=dict)


@dataclass
class EventState:
    """Per-event facts. Distinct from CustomerState because one customer can
    have several at-risk events at once: paying invoice A does not pay
    invoice B, and the retry ladder for A must not start mid-way because B
    already used two attempts."""
    event_id: str
    attempts: int = 0
    paid: bool = False


@dataclass
class CustomerState:
    """Customer-scoped limits, plus the current event's facts.

    `attempts_on_event` and `already_paid` are set by the runner from the
    EventState of the event being decided, so guardrails see event-scoped
    facts without every rule needing a second argument.
    """
    customer_id: str
    contacts_last_7d: int = 0
    last_contact_at: datetime | None = None
    last_attempt_at: datetime | None = None
    attempts_on_event: int = 0
    promise_to_pay_until: datetime | None = None
    opted_out: bool = False
    already_paid: bool = False
    spend_authorized_paise: int = 0
    spend_used_paise: int = 0
    max_offer_pct_shown: float = 0.0
    suppressed_permanently: bool = False
