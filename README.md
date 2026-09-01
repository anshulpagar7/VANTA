# VANTA

**Verified Authority for Transaction Actions** — an AI revenue-recovery control
plane, and a benchmark for whether agentic recovery actually beats deterministic
recovery.

> The model cannot manufacture authority.

## What this is

Razorpay ships revenue-recovery agents. What nobody publishes is *how you would
prove one recovery policy beats another*. VANTA is that harness:

- a **frozen simulation world**, authored before any policy existed (`v0.1-frozen-world`)
- **four competing policies**, including an ablation arm that isolates the LLM's contribution
- a **dev/holdout seed split** so policies cannot be overfitted to the benchmark
- an **authority boundary** enforced by tests, not by prose

## Architecture

    diagnosis  ──▶  recommendation  ──▶  authorization  ──▶  execution
    (LLM; no      (proposes an       (ONLY holder of      (accepts
     authority)    AuthorizationRequest)  _POLICY_TOKEN)    AuthorizedAction)

A `Recommendation` can never become an `AuthorizedAction`. It must pass through
`PolicyEngine.authorize()`, which applies deterministic guardrails and mints
authority or refuses. See [ADR-002](docs/adr/ADR-002-authority-boundary.md).

Failure taxonomy mirrors Razorpay's error object (`source` × `step` × `reason`)
so the simulator speaks the same language as the real API —
<https://razorpay.com/docs/errors/>.

## Reproduce the results without an API key

    pip install -e ".[dev]"
    vanta evaluate --suite development --no-llm --skip-llm-arm

See [QUICKSTART.md](QUICKSTART.md) for Docker and for building the arm-C cache.

The diagnosis cache ships in the repo. `--no-llm` replays it, so anyone
reproduces the exact published table with zero credentials and zero cost.

## The arms

| arm | diagnosis | decision logic |
|---|---|---|
| A `naive` | none | fixed 1h / 6h / 24h retry |
| B `ladder` | deterministic map | rule ladder |
| B+ `vanta-norag` | deterministic map | expected-recovery-value scoring |
| C `vanta` | LLM | expected-recovery-value scoring |

**C − B+ is the LLM's actual contribution.** If B+ wins, that is the finding and
it gets published.

## Metrics

Primary: **₹ recovered** (holdout, mean ± CI over 5 seeds).
Secondary: recovery efficiency (₹ recovered / intervention cost), contacts per
recovery, false-positive intervention rate, abstention rate.
Full set in the generated report.

**Abstention is a first-class outcome.** A policy that declines to spend
customer attention where expected return is low is working, not failing.

## Status

World frozen. Arms A, B and B+ implemented and measured on development seeds.
Arm C implemented but has no results until the diagnosis cache is built with a
real model. Holdout untouched. See [LIMITATIONS.md](LIMITATIONS.md).

### Development-seed results (1000 events x 5 seeds)

| arm | Rs recovered | rate | contacts/recovery | blocked |
|---|---|---|---|---|
| A naive | 615,463 | 19.1% | - | 0 |
| B ladder | 1,118,796 | 34.7% | 2.23 | 1,800 |
| B+ vanta-norag | 1,421,423 | 44.1% | 2.19 | 0 |
| C vanta | pending cache build | | | |

These are development numbers used for tuning. They are not the result. The
holdout suite runs once, after the policy freeze.
