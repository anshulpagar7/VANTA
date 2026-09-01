"""Intervention cost lookup, loaded from costs.yaml.

Every value carries a `sourced`/`assumed` provenance marker in the YAML and is
a sensitivity-sweep axis. See LIMITATIONS.md -- recovery efficiency is only as
defensible as this denominator.
"""
from __future__ import annotations

import pathlib

import yaml

from vanta.types import ActionKind

_PATH = pathlib.Path(__file__).resolve().parents[3] / "costs.yaml"


def load_costs(path: pathlib.Path | None = None) -> dict[ActionKind, int]:
    data = yaml.safe_load((path or _PATH).read_text(encoding="utf-8"))
    out: dict[ActionKind, int] = {}
    for k, v in data["intervention_costs_paise"].items():
        out[ActionKind(k)] = int(v["value"])
    return out


COSTS = load_costs()


def cost_of(action: ActionKind) -> int:
    return COSTS.get(action, 0)
