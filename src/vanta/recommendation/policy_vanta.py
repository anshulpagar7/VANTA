"""Arm C -- VANTA with LLM diagnosis.

Identical scoring, candidates, scheduling and abstention rule as arm B+. The
only difference is where the Recommendation comes from. Any gap between the
two arms is therefore attributable to diagnosis quality and nothing else.
"""
from __future__ import annotations

from vanta.authorization.limits import DEFAULT_LIMITS, Limits
from vanta.diagnosis.context import bucket_key
from vanta.diagnosis.provider import CachedProvider
from vanta.recommendation.policy_vanta_norag import VantaScoringPolicy


class VantaLLMPolicy(VantaScoringPolicy):
    def __init__(self, provider: CachedProvider, limits: Limits = DEFAULT_LIMITS) -> None:
        self.provider = provider
        super().__init__(
            diagnose_fn=lambda event, attempt: provider.diagnose(bucket_key(event, attempt)),
            name="C_vanta",
            limits=limits,
        )
