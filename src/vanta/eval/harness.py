"""Run every arm across a seed suite and print the comparison table."""
from __future__ import annotations

from statistics import mean, stdev

from vanta.eval.runner import RunStats, run_arm
from vanta.recommendation.policy_ladder import RuleLadderPolicy
from vanta.recommendation.policy_naive import NaiveRetryPolicy
from vanta.recommendation.policy_vanta import VantaLLMPolicy
from vanta.recommendation.policy_vanta_norag import VantaNoLLMPolicy
from vanta.store.audit import AuditLog
from vanta.world.generator import DEV_SEEDS, HOLDOUT_SEEDS

SUITES = {"development": DEV_SEEDS, "holdout": HOLDOUT_SEEDS}


def _ci95(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    return 1.96 * stdev(xs) / len(xs) ** 0.5


def evaluate(
    suite: str,
    n_events: int,
    provider,
    log_path: str | None = None,
    report_path: str | None = None,
    skip_llm_arm: bool = False,
) -> dict[str, list[RunStats]]:
    seeds = SUITES[suite]
    arms = [NaiveRetryPolicy(), RuleLadderPolicy(), VantaNoLLMPolicy()]
    if not skip_llm_arm:
        arms.append(VantaLLMPolicy(provider))
    log = AuditLog(log_path) if log_path else None
    results: dict[str, list[RunStats]] = {}

    for pol in arms:
        runs = [run_arm(pol, seed=s, n_events=n_events, log=log) for s in seeds]
        results[pol.name] = runs

    print(f"\nsuite={suite}  seeds={seeds}  events/seed={n_events}\n")
    header = f"{'arm':22}{'Rs recovered':>20}{'rate':>8}{'contacts/rec':>14}{'abstain%':>10}"
    print(header)
    print("-" * len(header))
    for name, runs in results.items():
        rec = [r.recovered_paise / 100 for r in runs]
        cpr = [r.contacts_per_recovery for r in runs if r.recovered_events]
        decisions = [r.authorized + r.blocked + r.abstained + r.review_required for r in runs]
        absr = [r.abstained / d if d else 0 for r, d in zip(runs, decisions, strict=True)]
        print(f"{name:22}{mean(rec):>13,.0f}±{_ci95(rec):>6,.0f}"
              f"{mean(r.recovery_rate for r in runs):>8.1%}"
              f"{(mean(cpr) if cpr else 0):>14.2f}{mean(absr):>10.1%}")

    b_plus = results.get("Bplus_vanta_norag")
    c = results.get("C_vanta")
    if b_plus and c:
        delta = mean(r.recovered_paise for r in c) - mean(r.recovered_paise for r in b_plus)
        print(f"\nC - B+ (the LLM's isolated contribution): Rs{delta/100:+,.0f}")
    if report_path:
        from vanta.eval.report import generate
        out = generate(results, suite=suite, n_events=n_events, seeds=tuple(seeds),
                       audit_path=log_path, out_path=__import__("pathlib").Path(report_path))
        print(f"\nreport written to {out}")
    if log:
        log.close()
    return results
