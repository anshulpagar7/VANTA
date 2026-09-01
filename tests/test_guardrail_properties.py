"""Property-based guardrails: asserted over generated state, not three examples."""
from __future__ import annotations

from datetime import datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from vanta.authorization.engine import AuthorizationRequest, PolicyEngine
from vanta.authorization.limits import DEFAULT_LIMITS
from vanta.events.models import CustomerState
from vanta.types import CONTACT_ACTIONS, MONEY_ACTIONS, ActionKind

BASE = datetime(2026, 9, 1, 0, 0)

states = st.builds(
    CustomerState,
    customer_id=st.just("c1"),
    contacts_last_7d=st.integers(0, 10),
    last_contact_at=st.one_of(st.none(), st.integers(0, 200).map(lambda h: BASE + timedelta(hours=h))),
    attempts_on_event=st.integers(0, 10),
    promise_to_pay_until=st.one_of(st.none(), st.integers(0, 200).map(lambda h: BASE + timedelta(hours=h))),
    opted_out=st.booleans(),
    already_paid=st.booleans(),
    spend_used_paise=st.integers(0, 100_000),
)
actions = st.sampled_from(list(ActionKind))
hours = st.integers(0, 200)
amounts = st.integers(1, 100_000)


@settings(max_examples=400)
@given(states, actions, hours, amounts)
def test_blocked_requests_never_produce_an_action(state, action, h, amount):
    now = BASE + timedelta(hours=h)
    engine = PolicyEngine()
    req = AuthorizationRequest(action, "e1", "c1", amount, now, "prop")
    d = engine.authorize(req, state, now)
    if d.block_reason is not None:
        assert d.authorized is None


@settings(max_examples=400)
@given(states, actions, hours, amounts)
def test_active_promise_to_pay_never_authorizes_contact_or_money(state, action, h, amount):
    now = BASE + timedelta(hours=h)
    if not (state.promise_to_pay_until and now < state.promise_to_pay_until):
        return
    engine = PolicyEngine()
    req = AuthorizationRequest(action, "e1", "c1", amount, now, "prop")
    d = engine.authorize(req, state, now)
    if action in (CONTACT_ACTIONS | MONEY_ACTIONS):
        assert d.authorized is None


@settings(max_examples=400)
@given(states, hours, amounts)
def test_spend_cap_is_never_exceeded(state, h, amount):
    now = BASE + timedelta(hours=h)
    engine = PolicyEngine()
    for action in MONEY_ACTIONS:
        req = AuthorizationRequest(action, "e1", "c1", amount, now, "prop",
                                   cost_paise=amount)
        d = engine.authorize(req, state, now)
        if d.authorized is not None:
            assert state.spend_used_paise + amount <= DEFAULT_LIMITS.spend_cap_paise
