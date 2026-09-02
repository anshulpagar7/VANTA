"""The CLI must actually use the fallback chain.

This exists because an edit to cli.py once failed to apply silently, shipping
a build-cache path that went straight to Anthropic and ignored every other
key. Nothing caught it: the chain was tested, the providers were tested, but
the wiring between the CLI and the chain was not.
"""
from __future__ import annotations

import pytest

from vanta.cli import _live_chain


def test_gemini_key_alone_builds_a_gemini_chain(monkeypatch):
    for var in ("XAI_API_KEY", "ANTHROPIC_API_KEY", "GITHUB_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    chain = _live_chain()
    assert [p.name for p in chain.providers] == ["gemini:gemini-2.5-flash"]


def test_provider_order_is_gemini_then_grok(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "GITHUB_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "a")
    monkeypatch.setenv("XAI_API_KEY", "b")
    names = [p.name for p in _live_chain().providers]
    assert names[0].startswith("gemini") and names[1].startswith("grok")


def test_model_overrides_are_honoured(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "a")
    chain = _live_chain(gemini_model="gemini-2.5-flash-lite")
    assert chain.providers[0].model == "gemini-2.5-flash-lite"


def test_no_keys_exits_with_a_useful_message(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)          # no .env to pick up
    for var in ("GEMINI_API_KEY", "XAI_API_KEY", "ANTHROPIC_API_KEY", "GITHUB_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(SystemExit, match="no API key found"):
        _live_chain()
