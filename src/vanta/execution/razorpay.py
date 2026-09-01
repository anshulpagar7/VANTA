"""Integration proof only -- NEVER used in the benchmark.

Same AuthorizedAction interface, pointed at Razorpay test mode. Requires
RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET; absent them this is a no-op stub so CI
never needs credentials.
"""
from __future__ import annotations

import os

from vanta.execution.types import AuthorityError, AuthorizedAction, ExecutionResult


class RazorpayTestExecutor:
    def __init__(self) -> None:
        self.key_id = os.getenv("RAZORPAY_KEY_ID")
        self.key_secret = os.getenv("RAZORPAY_KEY_SECRET")

    @property
    def configured(self) -> bool:
        return bool(self.key_id and self.key_secret)

    def execute(self, action: AuthorizedAction) -> ExecutionResult:
        if not isinstance(action, AuthorizedAction):
            raise AuthorityError("executor accepts AuthorizedAction only")
        if not self.configured:
            raise RuntimeError("Razorpay test-mode credentials not configured")
        # TODO(day-8): create test-mode payment link / order for the demo clip.
        raise NotImplementedError("wire on demo day; not part of the benchmark")
