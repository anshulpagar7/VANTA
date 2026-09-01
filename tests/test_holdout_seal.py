import pytest

from vanta.cli import _guard_holdout


def test_holdout_refuses_without_freeze_marker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        _guard_holdout("holdout")


def test_development_suite_always_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _guard_holdout("development")
