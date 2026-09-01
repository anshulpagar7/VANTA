"""Deterministic executor used for ALL benchmark runs.

Outcome dynamics live in vanta.world (frozen). This class only routes an
AuthorizedAction into that world -- it holds no policy of its own.
"""
from __future__ import annotations

from vanta.execution.types import AuthorityError, AuthorizedAction, ExecutionResult


class SimulatedExecutor:
    def __init__(self, world) -> None:
        self.world = world

    def execute(self, action: AuthorizedAction) -> ExecutionResult:
        if not isinstance(action, AuthorizedAction):
            raise AuthorityError("executor accepts AuthorizedAction only")
        return self.world.resolve(action)
