"""Transient provider failures must not lose a whole cache build."""
from __future__ import annotations

import io
import urllib.error
import urllib.request

import pytest

from vanta.diagnosis.provider import ProviderError, _post


class _FakeHTTPError(urllib.error.HTTPError):
    def __init__(self, code):
        super().__init__("http://x", code, "err", {}, io.BytesIO(b'{"error":"x"}'))


def _opener(sequence):
    """Yield each item: an int status raises, a dict returns."""
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        item = sequence[calls["n"]]
        calls["n"] += 1
        if isinstance(item, int):
            raise _FakeHTTPError(item)

        class R:
            def __enter__(self_inner): return self_inner
            def __exit__(self_inner, *a): return False
            def read(self_inner): return b'{"ok": true}'
        return R()

    return fake_urlopen, calls


def test_retries_a_503_then_succeeds(monkeypatch):
    fake, calls = _opener([503, 503, {}])
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    out = _post(urllib.request.Request("http://x"), "test", sleep=lambda s: None)
    assert out == {"ok": True} and calls["n"] == 3


def test_retries_a_429(monkeypatch):
    fake, calls = _opener([429, {}])
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    _post(urllib.request.Request("http://x"), "test", sleep=lambda s: None)
    assert calls["n"] == 2


def test_does_not_retry_a_404(monkeypatch):
    """A retired model id will not fix itself; failing fast is correct."""
    fake, calls = _opener([404, {}])
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    with pytest.raises(ProviderError, match="404"):
        _post(urllib.request.Request("http://x"), "test", sleep=lambda s: None)
    assert calls["n"] == 1


def test_gives_up_after_max_attempts(monkeypatch):
    fake, calls = _opener([503] * 10)
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    with pytest.raises(ProviderError, match="503"):
        _post(urllib.request.Request("http://x"), "test",
              max_attempts=4, sleep=lambda s: None)
    assert calls["n"] == 4


def test_throttle_spaces_calls(monkeypatch):
    from vanta.diagnosis.provider import _Throttle
    slept = []
    t = _Throttle(min_interval=3.0)
    t.wait(sleep=slept.append)          # first call: nothing to wait for
    assert slept == []
    t.wait(sleep=slept.append)          # second: must pause close to 3s
    assert len(slept) == 1 and 2.5 < slept[0] <= 3.0


def test_stated_retry_delay_is_honoured(monkeypatch):
    """Google says 'Please retry in 39.6s'. Guessing 2s just burns quota."""
    import io
    import urllib.error
    import urllib.request

    from vanta.diagnosis.provider import _post

    body = b'{"error":{"message":"Quota exceeded. Please retry in 39.6s."}}'
    calls = {"n": 0}
    waits = []

    def fake(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError("http://x", 429, "e", {}, io.BytesIO(body))

        class R:
            def __enter__(s): return s
            def __exit__(s, *a): return False
            def read(s): return b'{"ok":true}'
        return R()

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    _post(urllib.request.Request("http://x"), "t", sleep=waits.append)
    assert any(39 <= w <= 42 for w in waits), waits
