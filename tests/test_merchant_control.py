"""Guardrails mapped to Razorpay Agent Studio's published principles (ADR-001)."""
from __future__ import annotations

from datetime import datetime

from vanta.authorization.engine import AuthorizationRequest, PolicyEngine
from vanta.authorization.merchant import MerchantConfig
from vanta.events.models import CustomerState
from vanta.types import ActionKind, BlockReason, Outcome

NOON = datetime(2026, 9, 1, 12, 0)


def _req(action=ActionKind.SEND_NUDGE, **kw):
    base = dict(
        action=action, event_id="e1", customer_id="c1", amount_paise=10_000,
        scheduled_for=NOON, policy_name="test",
    )
    base.update(kw)
    return AuthorizationRequest(**base)


def test_kill_switch_blocks_everything():
    engine = PolicyEngine(merchant=MerchantConfig(enabled=False))
    d = engine.authorize(_req(), CustomerState("c1"), NOON)
    assert d.block_reason is BlockReason.AGENT_DISABLED


def test_action_outside_agent_scope_is_blocked():
    engine = PolicyEngine(merchant=MerchantConfig(
        allowed_actions=frozenset({ActionKind.SEND_NUDGE})))
    d = engine.authorize(_req(ActionKind.SEND_PAYMENT_LINK), CustomerState("c1"), NOON)
    assert d.block_reason is BlockReason.OUT_OF_AGENT_SCOPE


def test_review_first_mode_never_auto_approves():
    engine = PolicyEngine(merchant=MerchantConfig(review_first=True))
    d = engine.authorize(_req(), CustomerState("c1"), NOON)
    assert d.outcome is Outcome.REVIEW_REQUIRED and d.authorized is None


def test_escalation_to_human_always_requires_review():
    engine = PolicyEngine()
    d = engine.authorize(_req(ActionKind.ESCALATE_HUMAN), CustomerState("c1"), NOON)
    assert d.outcome is Outcome.REVIEW_REQUIRED


def test_agent_cannot_invent_an_offer():
    engine = PolicyEngine(merchant=MerchantConfig(
        approved_offer_ids=frozenset({"FLAT10"}), max_discount_pct=10.0))
    d = engine.authorize(_req(offer_id="MADEUP50", discount_pct=50.0),
                         CustomerState("c1"), NOON)
    assert d.block_reason is BlockReason.UNAPPROVED_OFFER


def test_agent_cannot_exceed_merchant_discount_ceiling():
    engine = PolicyEngine(merchant=MerchantConfig(
        approved_offer_ids=frozenset({"FLAT10"}), max_discount_pct=10.0))
    d = engine.authorize(_req(offer_id="FLAT10", discount_pct=15.0),
                         CustomerState("c1"), NOON)
    assert d.block_reason is BlockReason.OFFER_EXCEEDS_MERCHANT_CEILING


def test_no_escalating_offer_loop():
    engine = PolicyEngine(merchant=MerchantConfig(
        approved_offer_ids=frozenset({"FLAT10"}), max_discount_pct=20.0))
    state = CustomerState("c1", contacts_last_7d=1, max_offer_pct_shown=5.0)
    d = engine.authorize(_req(offer_id="FLAT10", discount_pct=15.0), state, NOON)
    assert d.block_reason is BlockReason.ESCALATING_OFFER


def test_false_urgency_copy_is_blocked_before_send():
    engine = PolicyEngine()
    d = engine.authorize(_req(message="Hurry! This offer expires in 2 hours"),
                         CustomerState("c1"), NOON)
    assert d.block_reason is BlockReason.DARK_PATTERN_DETECTED


def test_genuine_time_bound_offer_may_be_stated_truthfully():
    engine = PolicyEngine()
    d = engine.authorize(
        _req(message="Your cart is saved. This sale expires today at midnight.",
             offer_time_bound=True),
        CustomerState("c1"), NOON)
    assert d.outcome is Outcome.AUTHORIZED
