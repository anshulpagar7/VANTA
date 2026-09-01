"""Architecture-as-test.

Diagnosis and recommendation layers must not be able to reach execution.
Enforced by AST inspection so it holds even for imports inside functions.
"""
from __future__ import annotations

import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "vanta"

# vanta.world is the answer key: it holds the true root-cause distribution and
# the action-fit matrix. A policy that imports it is not a policy, it is an
# oracle -- and the benchmark would be meaningless.
FORBIDDEN = {
    "diagnosis": ("vanta.execution", "vanta.authorization", "vanta.world"),
    "recommendation": ("vanta.execution", "vanta.world"),
    "authorization": ("vanta.world",),
}


def _imported_modules(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


def test_layers_cannot_import_downstream():
    violations = []
    for layer, banned in FORBIDDEN.items():
        for py in (SRC / layer).rglob("*.py"):
            for mod in _imported_modules(py):
                if any(mod == b or mod.startswith(b + ".") for b in banned):
                    violations.append(f"{py.relative_to(SRC)} imports {mod}")
    assert not violations, "layer boundary violated:\n" + "\n".join(violations)
