"""Secrets loading.

Keys are read from the environment, or from a local `.env` that is gitignored.
No key is ever written to a source file: this repository is public, and a key
committed once stays in git history even after it is deleted.
"""
from __future__ import annotations

import os
import pathlib

ENV_FILE = pathlib.Path(".env")

KEY_VARS = ("GEMINI_API_KEY", "XAI_API_KEY", "ANTHROPIC_API_KEY", "GITHUB_TOKEN")


def load_dotenv(path: pathlib.Path = ENV_FILE) -> int:
    """Load KEY=value lines from .env into the environment. Returns count loaded.

    Existing environment variables win, so an explicitly exported key always
    overrides the file.
    """
    if not path.exists():
        return 0
    loaded = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded


def present_keys() -> list[str]:
    return [k for k in KEY_VARS if os.getenv(k)]


def redact(value: str) -> str:
    """Never print a key. Show enough to identify it, not enough to use it."""
    if len(value) < 10:
        return "***"
    return f"{value[:4]}...{value[-4:]}"
