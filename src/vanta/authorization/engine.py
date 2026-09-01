"""The only place in VANTA that can grant authority."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from vanta.authorization.limits import DEFAULT_LIMITS, Limits
from vanta.authorization.merchant import DEFAULT_MERCHANT, MerchantConfig
from vanta.authorization.rules import ALL_RULES
from vanta.events.models import CustomerState
from vanta.execution.types import _POLICY_TOKEN, AuthorizedAction, _mint
from vanta.types import REVIEW_REQUIRED_ACTIONS, ActionKind, BlockReason, Outcome


@dataclass(frozen=True)
class AuthorizationRequest:
    """What a recommendation policy asks for. Carries no authority."""
    action: ActionKind
    event_id: str
    customer_id: str
    amount_paise: int
    scheduled_for: datetime
    policy_name: str
    justification: str = ""
    message: str | None = None
    offer_id: str | None = None
    discount_pct: float = 0.0
    offer_time_bound: bool = False
    cost_paise: int = 0


@dataclass(frozen=True)
class Decision:
    request: AuthorizationRequest
    outcome: Outcome
    authorized: AuthorizedAction | None
    block_reason: BlockReason | None
    decided_at: datetime

    @property
    def allowed(self) -> bool:
        return self.authorized is not None

    @property
    def abstained(self) -> bool:
        return self.outcome is Outcome.ABSTAINED


class PolicyEngine:
    def __init__(
        self,
        limits: Limits = DEFAULT_LIMITS,
        merchant: MerchantConfig = DEFAULT_MERCHANT,
    ) -> None:
        self.limits = limits
        self.merchant = merchant

    def authorize(
        self,
        request: AuthorizationRequest,
        state: CustomerState,
        now: datetime,
    ) -> Decision:
        # Abstention is a first-class outcome, not a failure.
        if request.action is ActionKind.ABSTAIN:
            return Decision(request, Outcome.ABSTAINED, None, None, now)

        for rule in ALL_RULES:
            reason = rule(request, state, self.limits, now, self.merchant)
            if reason is not None:
                return Decision(request, Outcome.BLOCKED, None, reason, now)

        # Sensitive/irreversible actions, and review-first mode, are never
        # auto-approved: the agent does the work, the final call stays merchant-side.
        if self.merchant.review_first or request.action in REVIEW_REQUIRED_ACTIONS:
            return Decision(request, Outcome.REVIEW_REQUIRED, None, None, now)

        action = _mint(
            _POLICY_TOKEN,
            action=request.action,
            event_id=request.event_id,
            customer_id=request.customer_id,
            amount_paise=request.amount_paise,
            scheduled_for=request.scheduled_for,
            authorization_id=f"VNT-{uuid.uuid4().hex[:10].upper()}",
            policy_name=request.policy_name,
        )
        return Decision(request, Outcome.AUTHORIZED, action, None, now)
