"""Arm B -- deterministic rule ladder. No LLM.

Diagnose from the error slug with a hand-authored map, then follow a fixed
escalation path for that cause. This is the honest engineering baseline: if an
LLM cannot beat this, the LLM is not earning its cost.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from vanta.authorization.engine import AuthorizationRequest
from vanta.diagnosis.deterministic import diagnose
from vanta.events.models import CustomerState, RevenueEvent
from vanta.recommendation.costs import cost_of
from vanta.types import ActionKind, RootCause

# Per-cause escalation path and the delay before each step.
LADDERS: dict[RootCause, tuple[tuple[ActionKind, int], ...]] = {
    RootCause.TRANSIENT_GATEWAY: (
        (ActionKind.SCHEDULE_RETRY, 6), (ActionKind.SCHEDULE_RETRY, 24),
        (ActionKind.SEND_PAYMENT_LINK, 48),
    ),
    RootCause.ISSUER_SOFT_DECLINE: (
        (ActionKind.RETRY_ALTERNATE_METHOD, 12), (ActionKind.SEND_PAYMENT_LINK, 36),
    ),
    RootCause.INSUFFICIENT_FUNDS: (
        (ActionKind.SCHEDULE_RETRY, 24), (ActionKind.SEND_NUDGE, 72),
        (ActionKind.SCHEDULE_RETRY, 96),
    ),
    RootCause.AUTH_FAILURE: (
        (ActionKind.SEND_PAYMENT_LINK, 12), (ActionKind.RETRY_ALTERNATE_METHOD, 36),
    ),
    RootCause.METHOD_UNSUPPORTED: (
        (ActionKind.RETRY_ALTERNATE_METHOD, 6), (ActionKind.SEND_PAYMENT_LINK, 24),
    ),
    RootCause.CUSTOMER_ABANDONED: (
        (ActionKind.SEND_PAYMENT_LINK, 12), (ActionKind.SEND_NUDGE, 48),
    ),
    RootCause.INVOICE_OVERDUE: (
        (ActionKind.SEND_PAYMENT_LINK, 24), (ActionKind.SEND_NUDGE, 96),
        (ActionKind.ESCALATE_HUMAN, 168),
    ),
    RootCause.MANDATE_REVOKED: ((ActionKind.SEND_PAYMENT_LINK, 24),),
    RootCause.ISSUER_HARD_DECLINE: (),   # abstain: not worth the contact
    RootCause.UNKNOWN: ((ActionKind.SCHEDULE_RETRY, 24),),
}


class RuleLadderPolicy:
    name = "B_ladder"

    def propose(
        self, event: RevenueEvent, state: CustomerState, now: datetime
    ) -> AuthorizationRequest | None:
        rec = diagnose(event.reason)
        ladder = LADDERS.get(rec.root_cause, ())
        step = state.attempts_on_event
        if step > len(ladder):
            return None
        if step == len(ladder):
            # Ladder exhausted (or empty, for hard declines). Abstaining is a
            # decision and gets logged as one -- silence would hide it.
            return AuthorizationRequest(
                action=ActionKind.ABSTAIN, event_id=event.event_id,
                customer_id=event.customer_id, amount_paise=event.amount_paise,
                scheduled_for=now, policy_name=self.name, cost_paise=0,
                justification=f"{rec.root_cause.value}: ladder exhausted, expected return too low",
            )
        action, delay_h = ladder[step]
        when = max(event.occurred_at + timedelta(hours=delay_h), now)
        message = None
        if action in (ActionKind.SEND_NUDGE, ActionKind.SEND_PAYMENT_LINK):
            message = "Your payment did not go through. You can complete it here."
        return AuthorizationRequest(
            action=action, event_id=event.event_id, customer_id=event.customer_id,
            amount_paise=event.amount_paise, scheduled_for=when,
            policy_name=self.name, cost_paise=cost_of(action), message=message,
            justification=f"{rec.root_cause.value} ladder step {step + 1}",
        )
