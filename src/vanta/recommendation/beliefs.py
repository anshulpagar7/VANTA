"""Policy-side beliefs about what works.

These are the policy's ESTIMATES, authored from domain reasoning. They are
deliberately NOT the world's parameters -- vanta.world is the answer key and
importing it is forbidden (tests/test_import_boundaries.py). The numbers here
are in the same shape as the world's but were written independently and are
wrong in places. That error is real and it is part of what the benchmark
measures: a policy is judged on decisions made under an imperfect model, which
is the only situation that ever exists in production.
"""
from __future__ import annotations

from vanta.types import ActionKind, RootCause

# Believed probability of recovery given the ideal intervention.
BELIEVED_RECOVERABILITY: dict[RootCause, float] = {
    RootCause.TRANSIENT_GATEWAY:   0.65,
    RootCause.ISSUER_SOFT_DECLINE: 0.50,
    RootCause.INSUFFICIENT_FUNDS:  0.42,
    RootCause.AUTH_FAILURE:        0.40,
    RootCause.METHOD_UNSUPPORTED:  0.40,
    RootCause.CUSTOMER_ABANDONED:  0.28,
    RootCause.INVOICE_OVERDUE:     0.34,
    RootCause.MANDATE_REVOKED:     0.10,
    RootCause.ISSUER_HARD_DECLINE: 0.06,
    RootCause.UNKNOWN:             0.18,
}

_DEFAULT_FIT = 0.20
BELIEVED_FIT: dict[RootCause, dict[ActionKind, float]] = {
    RootCause.TRANSIENT_GATEWAY: {
        ActionKind.SCHEDULE_RETRY: 0.95, ActionKind.RETRY_SAME_METHOD: 0.75,
        ActionKind.RETRY_ALTERNATE_METHOD: 0.55, ActionKind.SEND_PAYMENT_LINK: 0.40,
    },
    RootCause.ISSUER_SOFT_DECLINE: {
        ActionKind.RETRY_ALTERNATE_METHOD: 0.85, ActionKind.SCHEDULE_RETRY: 0.80,
        ActionKind.SEND_PAYMENT_LINK: 0.60, ActionKind.RETRY_SAME_METHOD: 0.40,
    },
    RootCause.INSUFFICIENT_FUNDS: {
        ActionKind.SCHEDULE_RETRY: 0.90, ActionKind.SEND_NUDGE: 0.55,
        ActionKind.SEND_PAYMENT_LINK: 0.50, ActionKind.RETRY_SAME_METHOD: 0.25,
    },
    RootCause.AUTH_FAILURE: {
        ActionKind.SEND_PAYMENT_LINK: 0.85, ActionKind.RETRY_ALTERNATE_METHOD: 0.65,
        ActionKind.RETRY_SAME_METHOD: 0.45, ActionKind.SCHEDULE_RETRY: 0.45,
    },
    RootCause.METHOD_UNSUPPORTED: {
        ActionKind.RETRY_ALTERNATE_METHOD: 0.95, ActionKind.SEND_PAYMENT_LINK: 0.65,
        ActionKind.RETRY_SAME_METHOD: 0.05,
    },
    RootCause.CUSTOMER_ABANDONED: {
        ActionKind.SEND_PAYMENT_LINK: 0.95, ActionKind.SEND_NUDGE: 0.70,
        ActionKind.SCHEDULE_RETRY: 0.10,
    },
    RootCause.INVOICE_OVERDUE: {
        ActionKind.SEND_PAYMENT_LINK: 0.95, ActionKind.SEND_NUDGE: 0.80,
        ActionKind.ESCALATE_HUMAN: 0.90,
    },
    RootCause.MANDATE_REVOKED: {
        ActionKind.SEND_PAYMENT_LINK: 0.75, ActionKind.SEND_NUDGE: 0.50,
        ActionKind.RETRY_SAME_METHOD: 0.05, ActionKind.SCHEDULE_RETRY: 0.05,
    },
    RootCause.ISSUER_HARD_DECLINE: {
        ActionKind.RETRY_ALTERNATE_METHOD: 0.55, ActionKind.SEND_PAYMENT_LINK: 0.40,
        ActionKind.RETRY_SAME_METHOD: 0.05, ActionKind.SCHEDULE_RETRY: 0.05,
    },
}

BELIEVED_DECAY = (1.00, 0.60, 0.35, 0.20, 0.10)

BELIEVED_TIMING = (
    (0.0, 0.25), (1.0, 0.50), (6.0, 0.85), (24.0, 1.00),
    (72.0, 0.70), (168.0, 0.40), (720.0, 0.15),
)


def fit(cause: RootCause, action: ActionKind) -> float:
    return BELIEVED_FIT.get(cause, {}).get(action, _DEFAULT_FIT)


def decay(attempt_no: int) -> float:
    i = max(0, min(attempt_no - 1, len(BELIEVED_DECAY) - 1))
    return BELIEVED_DECAY[i]


def timing(hours: float) -> float:
    h = max(0.0, hours)
    pts = BELIEVED_TIMING
    if h <= pts[0][0]:
        return pts[0][1]
    if h >= pts[-1][0]:
        return pts[-1][1]
    for (h0, v0), (h1, v1) in zip(pts, pts[1:], strict=False):
        if h0 <= h <= h1:
            t = (h - h0) / (h1 - h0)
            return v0 + t * (v1 - v0)
    return pts[-1][1]


def p_recover(cause: RootCause, action: ActionKind, attempt_no: int, hours: float) -> float:
    p = (
        BELIEVED_RECOVERABILITY[cause]
        * fit(cause, action)
        * decay(attempt_no)
        * timing(hours)
    )
    return max(0.0, min(1.0, p))
