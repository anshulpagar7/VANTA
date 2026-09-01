"""FROZEN OUTCOME MODEL.

Resolves an AuthorizedAction into a realised outcome.

Determinism contract
--------------------
Randomness is drawn per (seed, event_id, attempt_no, action) -- NEVER from a
shared stream. Different policies make different numbers of calls in different
orders; a shared stream would hand each arm a different sequence of draws and
the comparison would measure luck as much as strategy. With per-outcome
seeding, every arm faces the identical world and the only difference between
them is the decisions they made.
"""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from datetime import datetime

from vanta.execution.types import AuthorizedAction, ExecutionResult
from vanta.types import ActionKind, RootCause
from vanta.world import params


def _uniform(seed: int, event_id: str, attempt_no: int, action: str) -> float:
    """Stable uniform draw in [0,1). Order-independent and process-independent
    (hashlib, not Python's salted hash())."""
    key = f"{seed}|{event_id}|{attempt_no}|{action}".encode()
    digest = hashlib.blake2b(key, digest_size=8).digest()
    return struct.unpack("<Q", digest)[0] / 2**64


@dataclass(frozen=True)
class GroundTruth:
    """What the world knows and no policy may read."""
    root_cause: RootCause
    responsiveness: float
    occurred_at: datetime
    amount_paise: int


class OutcomeModel:
    """The frozen world.

    One instance per (arm, seed). Every arm is handed a model built from the
    SAME seed and the SAME ground truth, so all arms face an identical world.
    """

    def __init__(self, seed: int, truth: dict[str, GroundTruth]) -> None:
        self.seed = seed
        self._truth = truth
        self._attempts: dict[str, int] = {}

    def resolve(self, action: AuthorizedAction) -> ExecutionResult:
        truth = self._truth[action.event_id]

        if action.action is ActionKind.ABSTAIN:
            return ExecutionResult(action.authorization_id, False, 0, "abstained")

        attempt_no = self._attempts.get(action.event_id, 0) + 1
        self._attempts[action.event_id] = attempt_no

        hours = (action.scheduled_for - truth.occurred_at).total_seconds() / 3600.0
        p = (
            params.BASE_RECOVERABILITY[truth.root_cause]
            * params.action_fit(truth.root_cause, action.action)
            * params.attempt_decay(attempt_no)
            * params.timing_multiplier(hours)
            * truth.responsiveness
        )
        p = max(0.0, min(1.0, p))

        draw = _uniform(self.seed, action.event_id, attempt_no, action.action.value)
        recovered = draw < p
        return ExecutionResult(
            authorization_id=action.authorization_id,
            succeeded=recovered,
            recovered_paise=truth.amount_paise if recovered else 0,
            detail=f"p={p:.4f} draw={draw:.4f} attempt={attempt_no} hours={hours:.1f}",
        )
