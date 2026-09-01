# ADR-003: Frozen world, dev/holdout split

**Status:** accepted (2026-08-26)

## Context
We author both the world and the agents that act in it. Nothing stops us from
tuning reality until our policy wins -- and nothing proves to a reader that we
didn't.

## Decision
1. **Freeze the world first.** `vanta.world` is written and committed before
   any policy code exists. Tag `v0.1-frozen-world`. Git history is the proof
   of ordering. No policy code -- not even one `if` -- lands before that tag.
2. **Dev/holdout seeds.** Development: 11-15. Holdout: 101-105. Policies are
   tuned against development only.
3. **Mechanical seal.** `vanta evaluate --suite holdout` refuses to run unless
   `POLICIES_FROZEN` exists. `results/holdout/` is gitignored until then. The
   holdout run happens in CI on the freeze commit so its timestamp is
   externally witnessed.
4. **One shot.** If VANTA loses on holdout, we publish that. We do not re-tune
   and re-run; the git history would show it regardless.

## Arms
| arm | diagnosis | decision |
|---|---|---|
| A naive | none | fixed retry ladder 1h/6h/24h |
| B ladder | deterministic source/step/reason map | rule ladder |
| B+ vanta-norag | deterministic map | expected-recovery-value scoring |
| C vanta | LLM | expected-recovery-value scoring |

`C - B+` isolates the LLM's contribution. Without B+ we could not tell whether
any win came from the model or from better decision maths. B+ beating C is a
publishable result, not a failure.
