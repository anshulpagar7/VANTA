"""Arm A -- naive fixed retry. The dumbest defensible baseline.

Retry the same method at +1h, +6h, +24h, then stop. No diagnosis, no
targeting, no notion of whether the failure is even retryable.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from vanta.authorization.engine import AuthorizationRequest
from vanta.events.models import CustomerState, RevenueEvent
from vanta.recommendation.costs import cost_of
from vanta.types import ActionKind

LADDER_HOURS = (1, 6, 24)


class NaiveRetryPolicy:
    name = "A_naive"

    def propose(
        self, event: RevenueEvent, state: CustomerState, now: datetime
    ) -> AuthorizationRequest | None:
        attempt = state.attempts_on_event
        if attempt > len(LADDER_HOURS):
            return None
        if attempt == len(LADDER_HOURS):
            return AuthorizationRequest(
                action=ActionKind.ABSTAIN, event_id=event.event_id,
                customer_id=event.customer_id, amount_paise=event.amount_paise,
                scheduled_for=now, policy_name=self.name, cost_paise=0,
                justification="fixed ladder exhausted",
            )
        when = event.occurred_at + timedelta(hours=LADDER_HOURS[attempt])
        when = max(when, now)
        action = ActionKind.RETRY_SAME_METHOD
        return AuthorizationRequest(
            action=action, event_id=event.event_id, customer_id=event.customer_id,
            amount_paise=event.amount_paise, scheduled_for=when,
            policy_name=self.name, cost_paise=cost_of(action),
            justification=f"fixed ladder step {attempt + 1}",
        )
