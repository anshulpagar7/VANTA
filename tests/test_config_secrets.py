"""Secrets must never be committed, and never printed."""
from __future__ import annotations

import pathlib

from vanta.config import load_dotenv, redact

REPO = pathlib.Path(__file__).resolve().parents[1]


def test_no_api_key_literal_is_committed_in_source():
    """A key pasted into source would survive in git history forever."""
    prefixes = ("sk-ant-", "xai-", "AIzaSy", "ghp_", "github_pat_")
    offenders = []
    for py in list((REPO / "src").rglob("*.py")) + list((REPO / "tests").rglob("*.py")):
        text = py.read_text(encoding="utf-8")
        for prefix in prefixes:
            if prefix in text and "prefixes" not in text:
                offenders.append(f"{py.name} contains {prefix!r}")
    assert not offenders, offenders


def test_env_file_is_gitignored():
    ignored = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in ignored


def test_dotenv_does_not_override_an_explicit_environment_variable(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "from-environment")
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=from-file\n", encoding="utf-8")
    load_dotenv(env)
    import os
    assert os.environ["GEMINI_API_KEY"] == "from-environment"


def test_dotenv_loads_when_the_variable_is_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text('XAI_API_KEY="value-from-file"\n# comment\n\n', encoding="utf-8")
    assert load_dotenv(env) == 1
    import os
    assert os.environ["XAI_API_KEY"] == "value-from-file"


def test_redaction_never_reveals_a_usable_key():
    secret = "xai-" + "A" * 60
    shown = redact(secret)
    assert secret not in shown and len(shown) < 20
