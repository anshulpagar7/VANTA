from __future__ import annotations

from datetime import datetime
from typing import Protocol

from vanta.authorization.engine import AuthorizationRequest
from vanta.events.models import CustomerState, RevenueEvent


class RecommendationPolicy(Protocol):
    name: str

    def propose(
        self, event: RevenueEvent, state: CustomerState, now: datetime
    ) -> AuthorizationRequest: ...
