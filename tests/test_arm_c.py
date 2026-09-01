
import pytest

from vanta.diagnosis.cache import DEFAULT_PATH, CacheMiss, DiagnosisCache
from vanta.diagnosis.deterministic import diagnose as rules_diagnose
from vanta.diagnosis.provider import CachedProvider, _StubProvider
from vanta.eval.build_cache import coverage_gap, enumerate_buckets
from vanta.eval.runner import run_arm
from vanta.recommendation.policy_vanta import VantaLLMPolicy
from vanta.recommendation.policy_vanta_norag import VantaNoLLMPolicy


def _rules_filled_cache(tmp_path) -> DiagnosisCache:
    """A cache where every bucket holds the RULES answer."""
    cache = DiagnosisCache(tmp_path / "c.json")
    for key in enumerate_buckets(n_events=500):
        cache.put(key, rules_diagnose(key.split("|")[0]))
    return cache


def test_arm_c_matches_bplus_when_given_identical_diagnoses(tmp_path):
    """Ablation integrity: with the same diagnoses, C and B+ must be the same
    program. Any divergence means the arms differ in more than the LLM, and
    C minus B+ would no longer isolate the model's contribution."""
    provider = CachedProvider(cache=_rules_filled_cache(tmp_path))
    c = run_arm(VantaLLMPolicy(provider), seed=11, n_events=400)
    b = run_arm(VantaNoLLMPolicy(), seed=11, n_events=400)
    assert c.recovered_paise == b.recovered_paise
    assert c.authorized == b.authorized and c.abstained == b.abstained


def test_replay_mode_fails_loudly_on_a_cache_miss(tmp_path):
    provider = CachedProvider(cache=DiagnosisCache(tmp_path / "empty.json"))
    with pytest.raises(CacheMiss):
        provider.diagnose("payment_failed|bank|payment_authorization|card|medium|first")


def test_live_provider_writes_through_to_cache(tmp_path):
    provider = CachedProvider(cache=DiagnosisCache(tmp_path / "c.json"),
                              source=_StubProvider())
    key = "invalid_otp|customer|payment_authentication|card|small|first"
    provider.diagnose(key)
    provider.diagnose(key)
    assert provider.calls == 1 and provider.hits == 1


def test_stub_output_never_reaches_the_committed_cache():
    """The stub is a test double, not a model. Numbers built on it are fiction."""
    if not DEFAULT_PATH.exists():
        pytest.skip("no committed cache yet")
    assert _StubProvider.MARKER not in DEFAULT_PATH.read_text(encoding="utf-8")


def test_bucket_count_is_small_enough_for_a_free_tier():
    assert len(enumerate_buckets(n_events=2000)) < 500


def test_dev_buckets_cover_the_holdout_suite():
    """If holdout needs a bucket the dev-built cache lacks, the holdout run
    would either fail or require a live call at the worst possible moment."""
    assert coverage_gap(2000) == []
