"""Rules-based diagnosis from Razorpay's source/step/reason axes.

IMPORTANT: this map is authored independently, from domain reasoning about
what each error slug means. It deliberately does NOT import
vanta.world.params -- doing so would be reading the answer key, and arm B/B+
would score as an oracle rather than as a policy. Enforced by
tests/test_import_boundaries.py.

Where this map is wrong, that error is real and it shows up in the benchmark
as diagnosis error rate. That is the point: it is the honest baseline the LLM
arm has to beat.
"""
from __future__ import annotations

from vanta.diagnosis.schema import Recommendation
from vanta.types import ActionKind, Recoverability, RootCause

# reason slug -> (best guess root cause, confidence we assign ourselves)
RULES: dict[str, tuple[RootCause, float]] = {
    "gateway_timeout":         (RootCause.TRANSIENT_GATEWAY, 0.85),
    "gateway_technical_error": (RootCause.TRANSIENT_GATEWAY, 0.75),
    "insufficient_funds":      (RootCause.INSUFFICIENT_FUNDS, 0.95),
    "invalid_otp":             (RootCause.AUTH_FAILURE, 0.80),
    "payment_timeout":         (RootCause.AUTH_FAILURE, 0.50),
    "card_declined":           (RootCause.ISSUER_HARD_DECLINE, 0.60),
    "method_unsupported":      (RootCause.METHOD_UNSUPPORTED, 0.95),
    "mandate_revoked":         (RootCause.MANDATE_REVOKED, 0.95),
    "checkout_abandoned":      (RootCause.CUSTOMER_ABANDONED, 0.95),
    "invoice_overdue":         (RootCause.INVOICE_OVERDUE, 0.95),
    # Genuinely ambiguous. A rules engine has to commit to something; this is
    # the guess, and it is wrong a lot. Arm C's opportunity lives here.
    "payment_failed":          (RootCause.ISSUER_SOFT_DECLINE, 0.40),
}

RECOVERABILITY: dict[RootCause, Recoverability] = {
    RootCause.TRANSIENT_GATEWAY:   Recoverability.LIKELY,
    RootCause.ISSUER_SOFT_DECLINE: Recoverability.LIKELY,
    RootCause.INSUFFICIENT_FUNDS:  Recoverability.LIKELY,
    RootCause.AUTH_FAILURE:        Recoverability.LIKELY,
    RootCause.METHOD_UNSUPPORTED:  Recoverability.LIKELY,
    RootCause.CUSTOMER_ABANDONED:  Recoverability.UNKNOWN,
    RootCause.INVOICE_OVERDUE:     Recoverability.UNKNOWN,
    RootCause.MANDATE_REVOKED:     Recoverability.UNLIKELY,
    RootCause.ISSUER_HARD_DECLINE: Recoverability.UNLIKELY,
    RootCause.UNKNOWN:             Recoverability.UNKNOWN,
}

# Preferred intervention per cause, by domain reasoning alone.
PREFERRED: dict[RootCause, ActionKind] = {
    RootCause.TRANSIENT_GATEWAY:   ActionKind.SCHEDULE_RETRY,
    RootCause.ISSUER_SOFT_DECLINE: ActionKind.RETRY_ALTERNATE_METHOD,
    RootCause.INSUFFICIENT_FUNDS:  ActionKind.SCHEDULE_RETRY,
    RootCause.AUTH_FAILURE:        ActionKind.SEND_PAYMENT_LINK,
    RootCause.METHOD_UNSUPPORTED:  ActionKind.RETRY_ALTERNATE_METHOD,
    RootCause.CUSTOMER_ABANDONED:  ActionKind.SEND_PAYMENT_LINK,
    RootCause.INVOICE_OVERDUE:     ActionKind.SEND_PAYMENT_LINK,
    RootCause.MANDATE_REVOKED:     ActionKind.SEND_PAYMENT_LINK,
    RootCause.ISSUER_HARD_DECLINE: ActionKind.ABSTAIN,
    RootCause.UNKNOWN:             ActionKind.ABSTAIN,
}


def diagnose(reason_slug: str) -> Recommendation:
    cause, confidence = RULES.get(reason_slug, (RootCause.UNKNOWN, 0.20))
    return Recommendation(
        root_cause=cause,
        recoverable=RECOVERABILITY[cause],
        suggested_action=PREFERRED[cause],
        confidence=confidence,
        rationale=f"rules: slug {reason_slug} maps to {cause.value}",
    )
