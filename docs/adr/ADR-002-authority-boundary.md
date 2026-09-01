# ADR-002: The model cannot manufacture authority

**Status:** accepted (2026-08-26)

## Context
An LLM in a money-moving loop is the central risk. "We prompt it carefully" is
not an answer. The architecture must make unauthorized action structurally
impossible, not merely unlikely.

## Decision
Four layers, four separate packages:

    diagnosis  ->  recommendation  ->  authorization  ->  execution

- `diagnosis` emits a `Recommendation`: closed enums, confidence in [0,1],
  sanitised rationale, `extra="forbid"`. It describes; it does not act.
- `recommendation` emits an `AuthorizationRequest`. Still no authority.
- `authorization.PolicyEngine.authorize()` is the ONLY holder of
  `_POLICY_TOKEN` and therefore the only code path that can mint an
  `AuthorizedAction`.
- `execution` accepts `AuthorizedAction` and nothing else.

Enforced by tests, not by convention:
- `test_authorized_action_requires_policy_token`
- `test_executor_rejects_non_authorized_action`
- `test_layers_cannot_import_downstream` (AST-level, catches function-local imports)
- Hypothesis: over 400 generated states, a blocked request never yields an action.

## Honest limit
This bounds *authority*, not *quality*. A hallucinated diagnosis cannot exceed
its permissions, but it can consume a permitted retry or contact on an
unrecoverable event. That cost is real and we measure it as `diagnosis error
rate` and its downstream `wasted contact` count -- see LIMITATIONS.md.
