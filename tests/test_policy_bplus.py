
from vanta.authorization.limits import DEFAULT_LIMITS
from vanta.eval.runner import run_arm
from vanta.events.models import CustomerState
from vanta.recommendation import beliefs
from vanta.recommendation.policy_ladder import RuleLadderPolicy
from vanta.recommendation.policy_vanta_norag import VantaNoLLMPolicy
from vanta.types import CONTACT_ACTIONS, RootCause
from vanta.world import params
from vanta.world.generator import generate


def test_policy_beliefs_are_not_the_world_truth():
    """If these matched, arm B+ would be an oracle wearing a policy's clothes."""
    diffs = [
        abs(beliefs.BELIEVED_RECOVERABILITY[c] - params.BASE_RECOVERABILITY[c])
        for c in RootCause
    ]
    assert max(diffs) > 0.02, "belief table looks copied from the world"


def test_bplus_beats_the_rule_ladder_on_dev_seeds():
    ladder = run_arm(RuleLadderPolicy(), seed=11, n_events=600)
    bplus = run_arm(VantaNoLLMPolicy(), seed=11, n_events=600)
    assert bplus.recovered_paise > ladder.recovered_paise


def test_bplus_never_schedules_a_contact_into_quiet_hours():
    events, _ = generate(13, 400)
    pol = VantaNoLLMPolicy()
    for e in events[:200]:
        state = CustomerState(e.customer_id)
        req = pol.propose(e, state, e.occurred_at)
        if req and req.action in CONTACT_ACTIONS:
            h = req.scheduled_for.hour
            assert not (h >= DEFAULT_LIMITS.quiet_hours_start or h < DEFAULT_LIMITS.quiet_hours_end)


def test_bplus_abstains_rather_than_spending_on_low_value_events():
    s = run_arm(VantaNoLLMPolicy(), seed=12, n_events=600)
    assert s.abstained > 0


def test_bplus_respects_contact_cap_without_relying_on_the_engine():
    """Guardrail-aware scheduling: it should not waste budget on refusals."""
    s = run_arm(VantaNoLLMPolicy(), seed=11, n_events=600)
    assert s.blocked == 0
