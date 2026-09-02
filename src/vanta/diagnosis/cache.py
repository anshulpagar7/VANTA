"""On-disk diagnosis cache, committed to the repository.

`--no-llm` replays this file, so anyone can reproduce the published numbers
with no API key and no spend. A run that would need a live call in replay mode
fails loudly rather than silently substituting a fallback -- a quietly
degraded arm C would invalidate the whole comparison.

Each entry records WHICH provider produced it. With a fallback chain, arm C
can silently become a two-model ensemble; provenance makes that visible in the
report instead of hidden in an average.
"""
from __future__ import annotations

import json
import pathlib
from collections import Counter

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
        entry = self._data.get(key)
        if not entry:
            return None
        return Recommendation(**entry["recommendation"])

    def provider_of(self, key: str) -> str | None:
        entry = self._data.get(key)
        return entry.get("provider") if entry else None

    def provider_mix(self) -> dict[str, int]:
        """How many buckets each provider produced. Reported, never averaged away."""
        return dict(Counter(e.get("provider", "unknown") for e in self._data.values()))

    def put(self, key: str, rec: Recommendation, provider: str = "unknown") -> None:
        self._data[key] = {
            "recommendation": rec.model_dump(mode="json"),
            "provider": provider,
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, indent=1, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
