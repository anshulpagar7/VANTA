"""Offline tooling: enumerate diagnosis buckets and populate the cache.

Lives in eval/, not diagnosis/, because it imports the world generator to
enumerate buckets. diagnosis/ must stay free of any world dependency at
runtime -- enforced by tests/test_import_boundaries.py, which caught this
module in the wrong package.

Holdout discipline: buckets are enumerated from DEVELOPMENT seeds only. The
reason mix is seed-independent, so dev buckets should cover holdout; run
`coverage_gap()` before the freeze to confirm. Enumerating from holdout would
mean touching holdout data before the policies were frozen.
"""
from __future__ import annotations

from vanta.diagnosis.cache import DiagnosisCache
from vanta.diagnosis.context import bucket_key
from vanta.diagnosis.provider import CachedProvider
from vanta.world.generator import DEV_SEEDS, HOLDOUT_SEEDS, generate

MAX_ATTEMPT = 5


def enumerate_buckets(seeds=DEV_SEEDS, n_events: int = 2000, max_attempt: int = MAX_ATTEMPT) -> list[str]:
    keys: set[str] = set()
    for seed in seeds:
        events, _ = generate(seed, n_events)
        for e in events:
            for attempt in range(1, max_attempt + 1):
                keys.add(bucket_key(e, attempt))
    return sorted(keys)


def coverage_gap(n_events: int = 2000) -> list[str]:
    """Holdout buckets not covered by the dev-built cache. Should be empty.

    This inspects bucket KEYS only -- never holdout outcomes -- so it does not
    break the seal in ADR-003.
    """
    dev = set(enumerate_buckets(DEV_SEEDS, n_events))
    hold = set(enumerate_buckets(HOLDOUT_SEEDS, n_events))
    return sorted(hold - dev)


def build(provider_source, n_events: int = 2000) -> DiagnosisCache:
    cache = DiagnosisCache()
    cached = CachedProvider(cache=cache, source=provider_source)
    keys = enumerate_buckets(DEV_SEEDS, n_events)
    for i, key in enumerate(keys, 1):
        cached.diagnose(key)
        if i % 25 == 0:
            cache.save()
            print(f"  {i}/{len(keys)} buckets")
    cache.save()
    mix = cache.provider_mix()
    print(f"cache built: {len(cache)} buckets, {cached.calls} live calls")
    print("provider mix: " + ", ".join(f"{k} {v}" for k, v in sorted(mix.items())))
    if len(mix) > 1:
        print(
            "NOTE: more than one provider served this cache. Arm C is a mixed\n"
            "      ensemble, not a single model. Disclose the mix in the report\n"
            "      and in LIMITATIONS rather than describing it as one LLM."
        )
    return cache
