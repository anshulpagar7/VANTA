"""Execution boundary.

An AuthorizedAction is the ONLY thing an executor accepts, and it can only be
constructed by vanta.authorization.engine. A Recommendation can never become
an AuthorizedAction directly -- it must pass through
PolicyEngine.authorize(). The model cannot manufacture authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from vanta.types import ActionKind

# Module-private sentinel. Only the policy engine holds a reference to it.
_POLICY_TOKEN = object()


class AuthorityError(PermissionError):
    """Raised when something tries to fabricate or execute unauthorized action."""


@dataclass(frozen=True)
class AuthorizedAction:
    action: ActionKind
    event_id: str
    customer_id: str
    amount_paise: int
    scheduled_for: datetime
    authorization_id: str
    policy_name: str

    def __post_init__(self) -> None:  # pragma: no cover - see _mint
        pass


def _mint(token: object, **kwargs) -> AuthorizedAction:
    """Internal factory. Importing this does not help you: you need the token."""
    if token is not _POLICY_TOKEN:
        raise AuthorityError(
            "AuthorizedAction may only be constructed by the policy engine"
        )
    return AuthorizedAction(**kwargs)


class Executor(Protocol):
    def execute(self, action: AuthorizedAction) -> ExecutionResult: ...


@dataclass(frozen=True)
class ExecutionResult:
    authorization_id: str
    succeeded: bool
    recovered_paise: int
    detail: str = ""
