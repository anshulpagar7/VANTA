"""FROZEN EVALUATION WORLD.

Nothing in this package may be edited after the `v0.1-frozen-world` tag.
Outcome probabilities were authored BEFORE any policy existed, so no policy
can be tuned by bending reality. Parameter provenance is marked `sourced` or
`assumed` in params.py; every `assumed` value is a sensitivity-sweep axis.

Modules:
  params.py     -- frozen probability tables (root cause, action fit, decay, timing)
  generator.py  -- event batches + hidden ground truth; dev seeds 11-15, holdout 101-105
  outcome.py    -- OutcomeModel.resolve(action) -> ExecutionResult

Determinism: draws are keyed on (seed, event_id, attempt_no, action) via
blake2b, never a shared stream, so every arm faces an identical world
regardless of how many calls it makes or in what order.
"""
