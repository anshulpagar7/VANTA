"""The ONLY shape a model may emit.

This module must never import vanta.execution -- enforced by
tests/test_import_boundaries.py. Diagnosis describes the world; it does not
act on it.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vanta.types import ActionKind, Recoverability, RootCause

_CONTROL_OR_MARKUP = re.compile(r"[<>\x00-\x1f\x7f]")
MAX_RATIONALE_CHARS = 400


class Recommendation(BaseModel):
    """A suggestion. Carries no authority whatsoever."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    root_cause: RootCause
    recoverable: Recoverability
    suggested_action: ActionKind
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(max_length=MAX_RATIONALE_CHARS)

    @field_validator("rationale")
    @classmethod
    def _sanitise(cls, v: str) -> str:
        """Rationale is free text that reaches the audit log and report.

        The model cannot manufacture authority -- it also cannot inject markup
        into anything downstream that renders it.
        """
        return _CONTROL_OR_MARKUP.sub("", v).strip()
