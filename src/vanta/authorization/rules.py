"""Deterministic guardrails. No LLM reaches this module.

Each rule is a pure function: (request, state, limits, now) -> BlockReason | None
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from vanta.authorization.dark_patterns import screen
from vanta.authorization.limits import Limits
from vanta.types import CONTACT_ACTIONS, MONEY_ACTIONS, ActionKind, BlockReason


def _in_quiet_hours(now: datetime, limits: Limits) -> bool:
    h = now.hour
    if limits.quiet_hours_start > limits.quiet_hours_end:  # wraps midnight
        return h >= limits.quiet_hours_start or h < limits.quiet_hours_end
    return limits.quiet_hours_start <= h < limits.quiet_hours_end


def rule_known_action(req, state, limits, now, merchant=None):
    if req.action not in set(ActionKind):
        return BlockReason.UNRECOGNISED_ACTION
    return None


def rule_already_paid(req, state, limits, now, merchant=None):
    if state.already_paid and req.action != ActionKind.ABSTAIN:
        return BlockReason.ALREADY_PAID
    return None


def rule_opted_out(req, state, limits, now, merchant=None):
    if state.opted_out and req.action in CONTACT_ACTIONS:
        return BlockReason.CUSTOMER_OPTED_OUT
    return None


def rule_promise_to_pay(req, state, limits, now, merchant=None):
    ptp = state.promise_to_pay_until
    if ptp and now < ptp and req.action in (CONTACT_ACTIONS | MONEY_ACTIONS):
        return BlockReason.PROMISE_TO_PAY_ACTIVE
    return None


def rule_quiet_hours(req, state, limits, now, merchant=None):
    if req.action in CONTACT_ACTIONS and _in_quiet_hours(now, limits):
        return BlockReason.QUIET_HOURS
    return None


def rule_contact_cap(req, state, limits, now, merchant=None):
    if req.action in CONTACT_ACTIONS and state.contacts_last_7d >= limits.max_contacts_per_7d:
        return BlockReason.CONTACT_CAP_EXCEEDED
    return None


def rule_cooldown(req, state, limits, now, merchant=None):
    if req.action in CONTACT_ACTIONS and state.last_contact_at is not None:
        if now - state.last_contact_at < timedelta(hours=limits.contact_cooldown_hours):
            return BlockReason.COOLDOWN_ACTIVE
    return None


def rule_attempt_cap(req, state, limits, now, merchant=None):
    if req.action in MONEY_ACTIONS and state.attempts_on_event >= limits.max_attempts_per_event:
        return BlockReason.ATTEMPT_CAP_EXCEEDED
    return None


def rule_spend_cap(req, state, limits, now, merchant=None):
    """Caps what the agent may SPEND recovering, not the value it may recover.

    Capping on transaction value would make the guardrail refuse exactly the
    events most worth recovering -- the large ones. The merchant's budget
    constrains intervention cost (nudges, calls, agent time); the transaction
    amount is the upside, not the exposure.
    """
    if state.spend_used_paise + req.cost_paise > limits.spend_cap_paise:
        return BlockReason.SPEND_CAP_EXCEEDED
    return None


def rule_agent_enabled(req, state, limits, now, merchant=None):
    """One-tap kill switch. Immediate, no exceptions."""
    if merchant is not None and not merchant.enabled:
        return BlockReason.AGENT_DISABLED
    return None


def rule_agent_scope(req, state, limits, now, merchant=None):
    """Scope check: an action outside the agent's approved permissions is
    blocked before it executes."""
    if merchant is not None and not merchant.permits(req.action):
        return BlockReason.OUT_OF_AGENT_SCOPE
    return None


def rule_offer_within_merchant_ceiling(req, state, limits, now, merchant=None):
    """The agent picks from what the merchant authorized. It does not invent
    discounts, and it never exceeds the merchant's configured ceiling."""
    if merchant is None or req.offer_id is None:
        return None
    if req.offer_id not in merchant.approved_offer_ids:
        return BlockReason.UNAPPROVED_OFFER
    if req.discount_pct > merchant.max_discount_pct:
        return BlockReason.OFFER_EXCEEDS_MERCHANT_CEILING
    return None


def rule_no_escalating_offers(req, state, limits, now, merchant=None):
    """No escalation loop where the agent keeps trying with bigger offers."""
    if req.discount_pct and req.discount_pct > state.max_offer_pct_shown:
        if state.contacts_last_7d > 0:
            return BlockReason.ESCALATING_OFFER
    return None


def rule_no_dark_patterns(req, state, limits, now, merchant=None):
    """Outbound copy is screened before it is authorized, not after it is sent."""
    if req.action in CONTACT_ACTIONS and req.message:
        if screen(req.message, offer_genuinely_time_bound=req.offer_time_bound):
            return BlockReason.DARK_PATTERN_DETECTED
    return None


ALL_RULES: tuple[Callable, ...] = (
    rule_agent_enabled,
    rule_agent_scope,
    rule_known_action,
    rule_already_paid,
    rule_opted_out,
    rule_promise_to_pay,
    rule_quiet_hours,
    rule_contact_cap,
    rule_cooldown,
    rule_attempt_cap,
    rule_spend_cap,
    rule_offer_within_merchant_ceiling,
    rule_no_escalating_offers,
    rule_no_dark_patterns,
)
