from vanta.eval.runner import run_arm
from vanta.recommendation.policy_ladder import RuleLadderPolicy
from vanta.recommendation.policy_naive import NaiveRetryPolicy
from vanta.store.audit import AuditLog


def test_run_is_reproducible():
    a = run_arm(NaiveRetryPolicy(), seed=11, n_events=300)
    b = run_arm(NaiveRetryPolicy(), seed=11, n_events=300)
    assert a.recovered_paise == b.recovered_paise
    assert a.authorized == b.authorized


def test_rule_ladder_beats_naive_on_dev_seeds():
    naive = run_arm(NaiveRetryPolicy(), seed=11, n_events=500)
    ladder = run_arm(RuleLadderPolicy(), seed=11, n_events=500)
    assert ladder.recovered_paise > naive.recovered_paise


def test_every_decision_is_audited():
    log = AuditLog()
    s = run_arm(RuleLadderPolicy(), seed=12, n_events=200, log=log)
    total = s.authorized + s.blocked + s.abstained + s.review_required
    rows = log.conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
    assert rows == total


def test_abstention_is_recorded_not_silent():
    s = run_arm(RuleLadderPolicy(), seed=11, n_events=500)
    assert s.abstained > 0


def test_recovered_never_exceeds_at_risk():
    for seed in (11, 12, 13):
        s = run_arm(RuleLadderPolicy(), seed=seed, n_events=300)
        assert 0 <= s.recovered_paise <= s.at_risk_paise
