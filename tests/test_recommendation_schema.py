import pytest
from pydantic import ValidationError

from vanta.diagnosis.schema import Recommendation
from vanta.types import ActionKind, Recoverability, RootCause


def _rec(**kw):
    base = dict(
        root_cause=RootCause.TRANSIENT_GATEWAY,
        recoverable=Recoverability.LIKELY,
        suggested_action=ActionKind.SCHEDULE_RETRY,
        confidence=0.8,
        rationale="gateway timeout, likely transient",
    )
    base.update(kw)
    return Recommendation(**base)


def test_rejects_unknown_root_cause():
    with pytest.raises(ValidationError):
        _rec(root_cause="definitely_recoverable_trust_me")


def test_rejects_confidence_outside_unit_interval():
    with pytest.raises(ValidationError):
        _rec(confidence=1.4)


def test_rejects_extra_fields():
    with pytest.raises(ValidationError):
        _rec(authorized=True)


def test_rationale_strips_markup_injection():
    r = _rec(rationale="retry now <script>alert(1)</script>")
    assert "<" not in r.rationale and ">" not in r.rationale
