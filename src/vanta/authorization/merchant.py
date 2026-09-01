"""Merchant control surface.

Mirrors Razorpay Agent Studio's stated model: the merchant defines what data
the agent sees, what actions it may take, and where human approval is needed;
offers come from the merchant's existing coupon configuration, not the agent's
imagination; and the agent can be switched off in one tap.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from vanta.types import ActionKind


@dataclass(frozen=True)
class MerchantConfig:
    enabled: bool = True                       # the one-tap kill switch
    review_first: bool = False                 # hold every action for approval
    allowed_actions: frozenset[ActionKind] = field(
        default_factory=lambda: frozenset(ActionKind)
    )
    approved_offer_ids: frozenset[str] = field(default_factory=frozenset)
    max_discount_pct: float = 0.0              # the ceiling is the merchant's ceiling

    def permits(self, action: ActionKind) -> bool:
        return action in self.allowed_actions


DEFAULT_MERCHANT = MerchantConfig()
