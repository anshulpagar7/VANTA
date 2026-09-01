"""On-disk diagnosis cache, committed to the repository.

`--no-llm` replays this file, so anyone can reproduce the published numbers
with no API key and no spend. A run that would need a live call in replay mode
fails loudly rather than silently substituting a fallback -- a quietly
degraded arm C would invalidate the whole comparison.
"""
from __future__ import annotations

import json
import pathlib

from vanta.diagnosis.schema import Recommendation

DEFAULT_PATH = pathlib.Path(__file__).resolve().parents[3] / "data" / "diagnosis_cache.json"


class CacheMiss(RuntimeError):
    pass


class DiagnosisCache:
    def __init__(self, path: pathlib.Path = DEFAULT_PATH) -> None:
        self.path = path
        self._data: dict[str, dict] = {}
        if path.exists():
            self._data = json.loads(path.read_text(encoding="utf-8"))

    def __len__(self) -> int:
        return len(self._data)

    def get(self, key: str) -> Recommendation | None:
        raw = self._data.get(key)
        return Recommendation(**raw) if raw else None

    def put(self, key: str, rec: Recommendation) -> None:
        self._data[key] = rec.model_dump(mode="json")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, indent=1, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
