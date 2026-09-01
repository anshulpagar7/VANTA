"""Shared vocabulary for VANTA.

The failure taxonomy is derived from Razorpay's published error object, which
exposes `source`, `step` and `reason` alongside `code`/`description`/`metadata`.
See https://razorpay.com/docs/errors/ -- we mirror that three-axis structure so
the simulator speaks the same language as the real API.
"""
from __future__ import annotations

from enum import Enum


class FailureSource(str, Enum):
    CUSTOMER = "customer"
    BUSINESS = "business"
    GATEWAY = "gateway"
    BANK = "bank"
    NETWORK = "network"
    RAZORPAY = "razorpay"
    NA = "na"


class FailureStep(str, Enum):
    PAYMENT_INITIATION = "payment_initiation"
    PAYMENT_AUTHENTICATION = "payment_authentication"
    PAYMENT_AUTHORIZATION = "payment_authorization"
    PAYMENT_CAPTURE = "payment_capture"
    MANDATE_CREATION = "mandate_creation"
    MANDATE_DEBIT = "mandate_debit"
    CHECKOUT = "checkout"
    INVOICE_DUE = "invoice_due"


class RootCause(str, Enum):
    """Closed set. The model may not invent a root cause."""
    TRANSIENT_GATEWAY = "transient_gateway"
    ISSUER_SOFT_DECLINE = "issuer_soft_decline"
    ISSUER_HARD_DECLINE = "issuer_hard_decline"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    AUTH_FAILURE = "auth_failure"
    METHOD_UNSUPPORTED = "method_unsupported"
    MANDATE_REVOKED = "mandate_revoked"
    CUSTOMER_ABANDONED = "customer_abandoned"
    INVOICE_OVERDUE = "invoice_overdue"
    UNKNOWN = "unknown"


class ActionKind(str, Enum):
    """Closed set of intervention kinds. ABSTAIN is a first-class outcome."""
    RETRY_SAME_METHOD = "retry_same_method"
    RETRY_ALTERNATE_METHOD = "retry_alternate_method"
    SCHEDULE_RETRY = "schedule_retry"
    SEND_PAYMENT_LINK = "send_payment_link"
    SEND_NUDGE = "send_nudge"
    ESCALATE_HUMAN = "escalate_human"
    ABSTAIN = "abstain"


MONEY_ACTIONS = frozenset({
    ActionKind.RETRY_SAME_METHOD,
    ActionKind.RETRY_ALTERNATE_METHOD,
    ActionKind.SCHEDULE_RETRY,
})

CONTACT_ACTIONS = frozenset({
    ActionKind.SEND_PAYMENT_LINK,
    ActionKind.SEND_NUDGE,
})


class Recoverability(str, Enum):
    LIKELY = "likely"
    UNLIKELY = "unlikely"
    UNKNOWN = "unknown"


class Outcome(str, Enum):
    """Three-way, not two. Razorpay's Agent Studio ships a "review-first mode"
    where the agent does the work but holds it for merchant approval; we mirror
    that as a first-class decision outcome."""
    AUTHORIZED = "authorized"
    REVIEW_REQUIRED = "review_required"
    BLOCKED = "blocked"
    ABSTAINED = "abstained"


# Actions Razorpay classifies as irreversible / sensitive: never auto-approved.
REVIEW_REQUIRED_ACTIONS = frozenset()  # populated below after ActionKind exists


class BlockReason(str, Enum):
    PROMISE_TO_PAY_ACTIVE = "promise_to_pay_active"
    QUIET_HOURS = "quiet_hours"
    CONTACT_CAP_EXCEEDED = "contact_cap_exceeded"
    COOLDOWN_ACTIVE = "cooldown_active"
    SPEND_CAP_EXCEEDED = "spend_cap_exceeded"
    ALREADY_PAID = "already_paid"
    CUSTOMER_OPTED_OUT = "customer_opted_out"
    DUPLICATE_ACTION = "duplicate_action"
    ATTEMPT_CAP_EXCEEDED = "attempt_cap_exceeded"
    UNRECOGNISED_ACTION = "unrecognised_action"
    OUT_OF_AGENT_SCOPE = "out_of_agent_scope"
    OFFER_EXCEEDS_MERCHANT_CEILING = "offer_exceeds_merchant_ceiling"
    UNAPPROVED_OFFER = "unapproved_offer"
    DARK_PATTERN_DETECTED = "dark_pattern_detected"
    AGENT_DISABLED = "agent_disabled"
    ESCALATING_OFFER = "escalating_offer"


# Sensitive/irreversible actions require merchant review; never auto-approved.
REVIEW_REQUIRED_ACTIONS = frozenset({ActionKind.ESCALATE_HUMAN})
