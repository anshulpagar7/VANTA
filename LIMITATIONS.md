# Limitations

Written before the results, updated with them. Nothing here gets deleted to
make a number look better.

## Structural

- **The world is synthetic.** Outcome probabilities are authored, not observed.
  Where a parameter has a published source it is marked `sourced` in
  `costs.yaml`; everything else is marked `assumed` and swept in the
  sensitivity analysis. A result that survives only at one parameter setting
  is not a result.
- **We author both the world and the agents.** Mitigated by freezing the world
  first (git-tagged, see ADR-003) and by a held-out seed suite, but not
  eliminated. Read the freeze commit timestamp, not our word for it.
- **One holdout run.** By design. If the numbers disappoint, they stand.

## Scope of the safety claim

The authority boundary bounds **what the model may do**, not **how well it
reasons**. A hallucinated diagnosis cannot exceed its permissions. It *can*
spend a permitted retry or customer contact on an unrecoverable event. That is
real cost and we report it (`diagnosis error rate`, wasted-contact count)
rather than claiming hallucination is harmless.

## The dark-pattern screen is lexical, not semantic

`dark_patterns.screen()` is a regex screen, not a classifier. It will miss
paraphrase and it will fire on innocent copy. Its false-positive rate is
measured and reported alongside the recovery numbers. A screen that never
fires is not a control; a screen with unreported false positives is not honest.

## Arm C has no results yet

`data/diagnosis_cache.json` is not committed. Until it is built with a real
model, arm C cannot run and no C number exists. The `_StubProvider` in
provider.py is a TEST DOUBLE that returns a fixed low-confidence abstention so
the code path can be exercised offline -- it is not a model, and any results
table built on it would be fiction. A test asserts its marker string never
appears in the committed cache.

Replay mode (`--no-llm`) raises `CacheMiss` rather than falling back to
rules-based diagnosis. A silently degraded arm C would look like an LLM
result while being a rules result, which is the single most misleading failure
this benchmark could have.

## Platform

Tested on Linux and Windows (Python 3.12). All text I/O is explicitly UTF-8:
the default on Windows is cp1252, which cannot encode the rupee sign, so a
locale-dependent write would fail on one platform and not the other. CI runs
both. Results are byte-identical across platforms because outcome draws are
keyed with blake2b rather than Python's per-process salted `hash()`.

## Not built

- Live Razorpay execution is an integration proof on the demo path only; it is
  never part of the benchmark and never runs in CI.
- No real customer data of any kind. No PII exists in this repository.
- Cost model denominators are assumptions (see `costs.yaml`); recovery
  efficiency should be read as directional, not absolute.

## Known open questions

- Does the deterministic `source × step × reason` map (arm B+) match the LLM
  (arm C)? If it does, the honest conclusion is that a well-structured error
  taxonomy beats a language model on this task, at a fraction of the cost.

## What the frozen world does and does not model

Modelled: root-cause ambiguity (the Razorpay reason slug does not uniquely
determine the true cause), action fit, attempt decay, a timing curve, and a
hidden per-customer responsiveness draw that no policy can read.

Not modelled: customer churn as a downstream cost of over-contacting, seasonal
effects, issuer-side policy changes over time, and any correlation between
amount and recoverability. Each of these would likely narrow the gap between
arms, so the benchmark should be read as an upper bound on the achievable
spread, not a forecast.

Calibration probe, SINGLE-ACTION budget (dev seeds, 1000 events): a naive
retry-at-+1h recovers ~11-12% of at-risk value; an oracle reading the hidden
root cause and acting at ideal timing recovers ~28%.

That 28% is NOT a ceiling for multi-attempt policies, and we initially misread
it as one. Under the real runner (up to 8 decisions per event) arm B reaches
~35%, which is not a leak -- it is a larger action budget. The single-action
oracle is a useful reference point, not an upper bound. A true multi-attempt
oracle bound has not been computed; until it is, no arm's score should be
described as "close to optimal".
