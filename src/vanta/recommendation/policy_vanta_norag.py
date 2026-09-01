"""Arm B+ -- VANTA scoring without the LLM. The ablation arm.

Same expected-recovery-value machinery as arm C, same candidate generation,
same guardrail-aware scheduling. The ONLY difference is that diagnosis comes
from the deterministic slug map instead of a language model.

C minus B+ is therefore the LLM's isolated contribution. Without this arm we
could not tell whether any win came from the model or from better decision
maths -- and that is the first question a reviewer will ask.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from vanta.authorization.engine import AuthorizationRequest
from vanta.authorization.limits import DEFAULT_LIMITS, Limits
from vanta.diagnosis.deterministic import diagnose
from vanta.events.models import CustomerState, RevenueEvent
from vanta.recommendation import beliefs
from vanta.recommendation.costs import COSTS, cost_of
from vanta.types import CONTACT_ACTIONS, MONEY_ACTIONS, ActionKind

CANDIDATE_ACTIONS = (
    ActionKind.SCHEDULE_RETRY,
    ActionKind.RETRY_SAME_METHOD,
    ActionKind.RETRY_ALTERNATE_METHOD,
    ActionKind.SEND_PAYMENT_LINK,
    ActionKind.SEND_NUDGE,
)
CANDIDATE_DELAYS_H = (2, 6, 12, 24, 48, 96, 168)

# Soft cost of spending a customer's attention, over and above channel cost.
ATTENTION_COST_PAISE = 100

MAX_ATTEMPTS = 5


def _shift_out_of_quiet_hours(when: datetime, limits: Limits) -> datetime:
    """Move a contact to the next permitted hour rather than being blocked.

    A policy that ignores the guardrail does not get punished for cruelty --
    it gets punished for wasting its action budget on decisions the engine
    will refuse. Respecting the constraint is simply better play.
    """
    for _ in range(48):
        h = when.hour
        quiet = (
            h >= limits.quiet_hours_start or h < limits.quiet_hours_end
            if limits.quiet_hours_start > limits.quiet_hours_end
            else limits.quiet_hours_start <= h < limits.quiet_hours_end
        )
        if not quiet:
            return when
        when = when + timedelta(hours=1)
    return when


class VantaScoringPolicy:
    """Shared body of arms B+ and C.

    Candidate generation, expected-value scoring, guardrail-aware scheduling
    and the abstention rule all live here. The ONLY thing an arm supplies is
    `diagnose_fn`. That is what makes C minus B+ the LLM's isolated
    contribution rather than a comparison of two different programs.
    """

    def __init__(self, diagnose_fn, name: str, limits: Limits = DEFAULT_LIMITS) -> None:
        self._diagnose = diagnose_fn
        self.name = name
        self.limits = limits

    def _feasible(self, action: ActionKind, state: CustomerState, when: datetime) -> bool:
        """Skip candidates the authorization layer would certainly refuse."""
        if action in CONTACT_ACTIONS:
            if state.contacts_last_7d >= self.limits.max_contacts_per_7d:
                return False
            if state.last_contact_at is not None:
                if when - state.last_contact_at < timedelta(hours=self.limits.contact_cooldown_hours):
                    return False
        if action in MONEY_ACTIONS and state.attempts_on_event >= self.limits.max_attempts_per_event:
            return False
        if state.spend_used_paise + cost_of(action) > self.limits.spend_cap_paise:
            return False
        return True

    def propose(
        self, event: RevenueEvent, state: CustomerState, now: datetime
    ) -> AuthorizationRequest | None:
        attempt = state.attempts_on_event
        if attempt > MAX_ATTEMPTS:
            return None

        rec = self._diagnose(event, attempt + 1)
        best = None

        for action in CANDIDATE_ACTIONS:
            for delay in CANDIDATE_DELAYS_H:
                when = event.occurred_at + timedelta(hours=delay)
                when = max(when, now)
                if action in CONTACT_ACTIONS:
                    when = _shift_out_of_quiet_hours(when, self.limits)
                if not self._feasible(action, state, when):
                    continue

                hours = (when - event.occurred_at).total_seconds() / 3600.0
                p = beliefs.p_recover(rec.root_cause, action, attempt + 1, hours)
                cost = COSTS.get(action, 0)
                if action in CONTACT_ACTIONS:
                    cost += ATTENTION_COST_PAISE
                ev = p * event.amount_paise - cost
                if best is None or ev > best[0]:
                    best = (ev, action, when, p)

        if best is None or best[0] <= 0:
            # Expected return does not justify the intervention. Abstaining is
            # the decision, and it is logged as one.
            return AuthorizationRequest(
                action=ActionKind.ABSTAIN, event_id=event.event_id,
                customer_id=event.customer_id, amount_paise=event.amount_paise,
                scheduled_for=now, policy_name=self.name, cost_paise=0,
                justification=(
                    f"{rec.root_cause.value}: best EV "
                    f"{(best[0] / 100 if best else 0):.2f} <= 0, not worth the spend"
                ),
            )

        ev, action, when, p = best
        message = None
        if action in CONTACT_ACTIONS:
            message = "Your payment did not go through. You can complete it here."
        return AuthorizationRequest(
            action=action, event_id=event.event_id, customer_id=event.customer_id,
            amount_paise=event.amount_paise, scheduled_for=when,
            policy_name=self.name, cost_paise=cost_of(action), message=message,
            justification=f"{rec.root_cause.value}: p={p:.3f} EV=Rs{ev/100:.2f}",
        )


class VantaNoLLMPolicy(VantaScoringPolicy):
    """Arm B+ -- deterministic diagnosis from the error slug."""

    def __init__(self, limits: Limits = DEFAULT_LIMITS) -> None:
        super().__init__(
            diagnose_fn=lambda event, attempt: diagnose(event.reason),
            name="Bplus_vanta_norag",
            limits=limits,
        )
