from __future__ import annotations

from datetime import datetime

import pytest

from vanta.authorization.engine import AuthorizationRequest, PolicyEngine
from vanta.events.models import CustomerState
from vanta.execution.simulated import SimulatedExecutor
from vanta.execution.types import AuthorityError, AuthorizedAction, _mint
from vanta.types import ActionKind

NOON = datetime(2026, 9, 1, 12, 0)


def _req(action=ActionKind.SEND_NUDGE, amount=10_000):
    return AuthorizationRequest(
        action=action, event_id="evt1", customer_id="cust1",
        amount_paise=amount, scheduled_for=NOON, policy_name="test",
    )


def test_authorized_action_requires_policy_token():
    with pytest.raises(AuthorityError):
        _mint(
            object(), action=ActionKind.SEND_NUDGE, event_id="e", customer_id="c",
            amount_paise=1, scheduled_for=NOON, authorization_id="x", policy_name="p",
        )


def test_executor_rejects_non_authorized_action():
    ex = SimulatedExecutor(world=None)
    with pytest.raises(AuthorityError):
        ex.execute(_req())  # a request is not an authorization


def test_engine_mints_only_after_rules_pass():
    engine = PolicyEngine()
    decision = engine.authorize(_req(), CustomerState("cust1"), NOON)
    assert isinstance(decision.authorized, AuthorizedAction)
    assert decision.authorized.authorization_id.startswith("VNT-")


def test_promise_to_pay_blocks_and_yields_no_action():
    engine = PolicyEngine()
    state = CustomerState("cust1", promise_to_pay_until=datetime(2026, 9, 4, 10, 0))
    decision = engine.authorize(_req(), state, NOON)
    assert decision.authorized is None
    assert decision.block_reason is not None


def test_abstain_is_not_a_block():
    engine = PolicyEngine()
    d = engine.authorize(_req(ActionKind.ABSTAIN), CustomerState("cust1"), NOON)
    assert d.abstained and d.block_reason is None and d.authorized is None
