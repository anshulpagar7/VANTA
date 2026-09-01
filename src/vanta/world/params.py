"""FROZEN WORLD PARAMETERS.

Authored before any policy code exists (ADR-003). Every value carries a
provenance marker. `sourced` means a published figure or a documented Razorpay
behaviour; `assumed` means our estimate, and every `assumed` value is an axis
in the sensitivity sweep.

None of these numbers may be edited after the v0.1-frozen-world tag. If the
benchmark is unflattering, that is the result.
"""
from __future__ import annotations

from vanta.types import ActionKind, RootCause

# --- reason slug -> candidate true root causes -------------------------------
# Razorpay's error object exposes source/step/reason. The reason slug does NOT
# uniquely determine the root cause: several slugs are genuinely ambiguous.
# That ambiguity is what makes diagnosis a real task rather than a lookup.
# provenance: slug names sourced from Razorpay error docs; the ambiguity
# weights are assumed.
REASON_TO_ROOT_CAUSE: dict[str, dict[RootCause, float]] = {
    "gateway_timeout":        {RootCause.TRANSIENT_GATEWAY: 0.90, RootCause.ISSUER_SOFT_DECLINE: 0.10},
    "gateway_technical_error":{RootCause.TRANSIENT_GATEWAY: 0.80, RootCause.AUTH_FAILURE: 0.20},
    "payment_failed":         {RootCause.ISSUER_SOFT_DECLINE: 0.40,  # deliberately ambiguous
                               RootCause.INSUFFICIENT_FUNDS: 0.30,
                               RootCause.ISSUER_HARD_DECLINE: 0.20,
                               RootCause.TRANSIENT_GATEWAY: 0.10},
    "insufficient_funds":     {RootCause.INSUFFICIENT_FUNDS: 1.00},
    "invalid_otp":            {RootCause.AUTH_FAILURE: 0.85, RootCause.TRANSIENT_GATEWAY: 0.15},
    "payment_timeout":        {RootCause.AUTH_FAILURE: 0.55, RootCause.CUSTOMER_ABANDONED: 0.45},
    "card_declined":          {RootCause.ISSUER_HARD_DECLINE: 0.65, RootCause.ISSUER_SOFT_DECLINE: 0.35},
    "method_unsupported":     {RootCause.METHOD_UNSUPPORTED: 1.00},
    "mandate_revoked":        {RootCause.MANDATE_REVOKED: 1.00},
    "checkout_abandoned":     {RootCause.CUSTOMER_ABANDONED: 1.00},
    "invoice_overdue":        {RootCause.INVOICE_OVERDUE: 1.00},
}

# --- base recoverability, given the ideal intervention -----------------------
# provenance: assumed, ordered by domain reasoning. Hard declines and revoked
# mandates are near-unrecoverable by automation; transient failures are not.
BASE_RECOVERABILITY: dict[RootCause, float] = {
    RootCause.TRANSIENT_GATEWAY:   0.72,
    RootCause.ISSUER_SOFT_DECLINE: 0.46,
    RootCause.INSUFFICIENT_FUNDS:  0.38,
    RootCause.AUTH_FAILURE:        0.44,
    RootCause.METHOD_UNSUPPORTED:  0.35,
    RootCause.CUSTOMER_ABANDONED:  0.22,
    RootCause.INVOICE_OVERDUE:     0.30,
    RootCause.MANDATE_REVOKED:     0.06,
    RootCause.ISSUER_HARD_DECLINE: 0.04,
    RootCause.UNKNOWN:             0.15,
}

# --- action fit: multiplier on base, by (root cause, action) -----------------
# provenance: assumed. A retry cannot fix a hard decline; a payment link cannot
# fix a gateway outage. This matrix is where policy quality actually shows.
_DEFAULT_FIT = 0.15
ACTION_FIT: dict[RootCause, dict[ActionKind, float]] = {
    RootCause.TRANSIENT_GATEWAY: {
        ActionKind.SCHEDULE_RETRY: 1.00, ActionKind.RETRY_SAME_METHOD: 0.80,
        ActionKind.RETRY_ALTERNATE_METHOD: 0.60, ActionKind.SEND_PAYMENT_LINK: 0.35,
    },
    RootCause.ISSUER_SOFT_DECLINE: {
        ActionKind.SCHEDULE_RETRY: 0.85, ActionKind.RETRY_ALTERNATE_METHOD: 0.90,
        ActionKind.RETRY_SAME_METHOD: 0.45, ActionKind.SEND_PAYMENT_LINK: 0.55,
    },
    RootCause.INSUFFICIENT_FUNDS: {
        ActionKind.SCHEDULE_RETRY: 0.95,   # time is the cure
        ActionKind.SEND_NUDGE: 0.60, ActionKind.SEND_PAYMENT_LINK: 0.55,
        ActionKind.RETRY_SAME_METHOD: 0.20,
    },
    RootCause.AUTH_FAILURE: {
        ActionKind.SEND_PAYMENT_LINK: 0.90, ActionKind.RETRY_ALTERNATE_METHOD: 0.70,
        ActionKind.RETRY_SAME_METHOD: 0.50, ActionKind.SCHEDULE_RETRY: 0.40,
    },
    RootCause.METHOD_UNSUPPORTED: {
        ActionKind.RETRY_ALTERNATE_METHOD: 1.00, ActionKind.SEND_PAYMENT_LINK: 0.70,
        ActionKind.RETRY_SAME_METHOD: 0.02,
    },
    RootCause.CUSTOMER_ABANDONED: {
        ActionKind.SEND_PAYMENT_LINK: 1.00, ActionKind.SEND_NUDGE: 0.75,
        ActionKind.SCHEDULE_RETRY: 0.05,
    },
    RootCause.INVOICE_OVERDUE: {
        ActionKind.SEND_NUDGE: 0.85, ActionKind.SEND_PAYMENT_LINK: 1.00,
        ActionKind.ESCALATE_HUMAN: 0.95,
    },
    RootCause.MANDATE_REVOKED: {
        ActionKind.SEND_PAYMENT_LINK: 0.80, ActionKind.SEND_NUDGE: 0.55,
        ActionKind.RETRY_SAME_METHOD: 0.01, ActionKind.SCHEDULE_RETRY: 0.01,
    },
    RootCause.ISSUER_HARD_DECLINE: {
        ActionKind.RETRY_ALTERNATE_METHOD: 0.60, ActionKind.SEND_PAYMENT_LINK: 0.45,
        ActionKind.RETRY_SAME_METHOD: 0.02, ActionKind.SCHEDULE_RETRY: 0.02,
    },
}


def action_fit(root_cause: RootCause, action: ActionKind) -> float:
    return ACTION_FIT.get(root_cause, {}).get(action, _DEFAULT_FIT)


# --- attempt decay -----------------------------------------------------------
# provenance: assumed. Each further attempt on the same event is worth less.
ATTEMPT_DECAY = (1.00, 0.62, 0.38, 0.22, 0.12)


def attempt_decay(attempt_no: int) -> float:
    idx = max(0, min(attempt_no - 1, len(ATTEMPT_DECAY) - 1))
    return ATTEMPT_DECAY[idx]


# --- timing curve ------------------------------------------------------------
# provenance: assumed. Retrying immediately is near-useless; there is a sweet
# spot in hours; very late, the customer has moved on.
TIMING_CURVE = (
    (0.0, 0.20), (1.0, 0.55), (6.0, 0.90), (24.0, 1.00),
    (72.0, 0.72), (168.0, 0.38), (720.0, 0.12),
)


def timing_multiplier(hours_since_failure: float) -> float:
    h = max(0.0, hours_since_failure)
    pts = TIMING_CURVE
    if h <= pts[0][0]:
        return pts[0][1]
    if h >= pts[-1][0]:
        return pts[-1][1]
    for (h0, v0), (h1, v1) in zip(pts, pts[1:], strict=False):
        if h0 <= h <= h1:
            t = (h - h0) / (h1 - h0)
            return v0 + t * (v1 - v0)
    return pts[-1][1]


# Hidden per-customer responsiveness, drawn at generation. No policy can read
# it. Without it, perfect play would exist, and a benchmark where perfect play
# exists measures nothing. provenance: assumed.
RESPONSIVENESS_RANGE = (0.55, 1.35)
