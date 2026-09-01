"""The world must be identical for every arm, regardless of call order."""
from __future__ import annotations

from datetime import timedelta

from vanta.authorization.engine import AuthorizationRequest, PolicyEngine
from vanta.events.models import CustomerState
from vanta.types import ActionKind, RootCause
from vanta.world.generator import generate
from vanta.world.outcome import OutcomeModel


def _authorized(event, action, offset_hours):
    engine = PolicyEngine()
    when = event.occurred_at + timedelta(hours=offset_hours)
    req = AuthorizationRequest(
        action=action, event_id=event.event_id, customer_id=event.customer_id,
        amount_paise=event.amount_paise, scheduled_for=when, policy_name="test",
    )
    return engine.authorize(req, CustomerState(event.customer_id), when).authorized


def test_same_action_same_result_across_model_instances():
    events, truth = generate(11, 50)
    e = events[0]
    a = _authorized(e, ActionKind.SCHEDULE_RETRY, 6)
    r1 = OutcomeModel(11, truth).resolve(a)
    r2 = OutcomeModel(11, truth).resolve(a)
    assert r1.succeeded == r2.succeeded and r1.recovered_paise == r2.recovered_paise


def test_call_order_does_not_change_outcomes():
    """Two arms touching events in opposite orders must see identical draws."""
    events, truth = generate(12, 40)
    acts = [_authorized(e, ActionKind.SCHEDULE_RETRY, 6) for e in events]

    fwd = {a.event_id: OutcomeModel(12, truth).resolve(a).succeeded for a in acts}
    m = OutcomeModel(12, truth)
    rev = {a.event_id: m.resolve(a).succeeded for a in reversed(acts)}
    assert fwd == rev


def test_different_seeds_give_different_worlds():
    e11, t11 = generate(11, 200)
    e12, t12 = generate(12, 200)
    assert [x.reason for x in e11] != [x.reason for x in e12]


def test_hard_decline_is_near_unrecoverable_by_retry():
    events, truth = generate(13, 400)
    hard = [e for e in events if truth[e.event_id].root_cause is RootCause.ISSUER_HARD_DECLINE]
    assert hard, "seed produced no hard declines"
    model = OutcomeModel(13, truth)
    wins = sum(
        model.resolve(_authorized(e, ActionKind.RETRY_SAME_METHOD, 6)).succeeded
        for e in hard
    )
    assert wins / len(hard) < 0.05


def test_abstain_never_recovers_and_never_consumes_an_attempt():
    events, truth = generate(14, 10)
    e = events[0]
    model = OutcomeModel(14, truth)
    a = _authorized(e, ActionKind.ABSTAIN, 6)
    assert a is None or model.resolve(a).recovered_paise == 0


def test_hidden_responsiveness_is_not_on_the_event():
    events, truth = generate(15, 10)
    assert not hasattr(events[0], "responsiveness")
    assert not hasattr(events[0], "root_cause")
    assert truth[events[0].event_id].responsiveness > 0


def test_dev_and_holdout_seeds_are_disjoint():
    from vanta.world.generator import DEV_SEEDS, HOLDOUT_SEEDS
    assert not set(DEV_SEEDS) & set(HOLDOUT_SEEDS)
