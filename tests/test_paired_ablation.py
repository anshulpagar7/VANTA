"""The ablation verdict must be a statistical claim, not a sign check.

A prior version declared "the LLM earns its place" whenever C's mean beat
B+'s mean, even when the effect was smaller than either arm's own noise band.
The correct comparison uses the PAIRED per-seed difference, since B+ and C run
on identical seeds (common random numbers).
"""
from __future__ import annotations

from vanta.eval.report import _paired_delta_ci
from vanta.eval.runner import RunStats


def _stats(recovered: list[int]) -> list[RunStats]:
    out = []
    for r in recovered:
        s = RunStats(arm="x", seed=0, n_events=1)
        s.recovered_paise = r
        s.at_risk_paise = 1
        out.append(s)
    return out


def test_identical_arms_have_zero_paired_delta():
    a = _stats([100, 200, 300, 400, 500])
    b = _stats([100, 200, 300, 400, 500])
    mean_d, ci, n = _paired_delta_ci(a, b)
    assert mean_d == 0.0 and n == 5


def test_consistent_small_edge_is_detected_as_significant():
    """Same absolute edge on every seed -- low variance, real effect."""
    a = _stats([1000, 1000, 1000, 1000, 1000])
    b = _stats([1050, 1050, 1050, 1050, 1050])
    mean_d, ci, n = _paired_delta_ci(a, b)
    assert mean_d == 50.0 and ci == 0.0        # zero variance -> zero CI
    assert abs(mean_d) > ci                     # clears its own interval


def test_noisy_edge_the_size_of_its_own_ci_is_not_significant():
    """This is the exact failure mode the old sign-only verdict missed:
    a positive mean masking a swing bigger than the mean itself."""
    a = _stats([1000, 1000, 1000, 1000, 1000])
    b = _stats([1200, 800, 1300, 700, 1100])   # mean +20, wildly noisy
    mean_d, ci, n = _paired_delta_ci(a, b)
    assert mean_d > 0
    assert ci > abs(mean_d)                     # noise dwarfs the point estimate


def test_ablation_html_flags_a_noisy_result_as_not_significant():
    from vanta.eval.report import _ablation
    a = _stats([1000] * 5)
    b = _stats([1200, 800, 1300, 700, 1100])
    html = _ablation({"Bplus_vanta_norag": a, "C_vanta": b})
    assert "not distinguishable from noise" in html
    assert "earns its place" not in html


def test_ablation_html_flags_a_consistent_result_as_significant():
    from vanta.eval.report import _ablation
    a = _stats([1000] * 5)
    b = _stats([1500] * 5)
    html = _ablation({"Bplus_vanta_norag": a, "C_vanta": b})
    assert "distinguishable from zero" in html
    assert "the LLM earns its place" in html
