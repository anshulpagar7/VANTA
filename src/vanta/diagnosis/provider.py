"""Diagnosis providers.

Layering:
    CachedProvider(source=<live provider or None>, cache=<on-disk cache>)

In replay mode (`--no-llm`) source is None and a miss raises CacheMiss. In
build mode the live provider is called once per bucket and the result is
written to the cache, which is then committed.

Model output is parsed through the strict Recommendation schema. A response
that does not validate is a PROVIDER FAILURE and is counted, not silently
patched -- see LIMITATIONS.md. The fallback to rules-based diagnosis exists
only so a run can complete, and every fallback is reported.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

from vanta.diagnosis.cache import CacheMiss, DiagnosisCache
from vanta.diagnosis.deterministic import diagnose as rules_diagnose
from vanta.diagnosis.schema import Recommendation
from vanta.types import ActionKind, Recoverability, RootCause

SYSTEM_PROMPT = """You triage failed payment events for an Indian payment gateway.
Given a payment failure described by Razorpay's error axes (source, step, reason)
plus the payment method, size band and attempt band, identify the most likely
root cause and the single intervention most likely to recover the money.

Reply with JSON only. No prose, no markdown fences. Schema:
{{"root_cause": <one of: {causes}>,
 "recoverable": "likely"|"unlikely"|"unknown",
 "suggested_action": <one of: {actions}>,
 "confidence": <float 0..1>,
 "rationale": "<max 30 words, no angle brackets>"}}

Be honest about confidence. If the reason slug is ambiguous, say so with a low
confidence rather than guessing high. Prefer "abstain" when the expected
recovery does not justify contacting the customer.""".format(
    causes=", ".join(c.value for c in RootCause),
    actions=", ".join(a.value for a in ActionKind),
)


class LiveProvider(Protocol):
    def diagnose_bucket(self, key: str) -> Recommendation: ...


def _bucket_to_prompt(key: str) -> str:
    reason, source, step, method, size, attempt = key.split("|")
    return (
        f"reason={reason}\nsource={source}\nstep={step}\nmethod={method}\n"
        f"amount_band={size}\nattempt_band={attempt}"
    )


@dataclass
class AnthropicProvider:
    """Live provider. Requires ANTHROPIC_API_KEY. Never used in CI."""
    model: str = "claude-sonnet-4-6"
    url: str = "https://api.anthropic.com/v1/messages"

    def diagnose_bucket(self, key: str) -> Recommendation:
        api_key = os.environ["ANTHROPIC_API_KEY"]
        body = json.dumps({
            "model": self.model, "max_tokens": 300,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": _bucket_to_prompt(key)}],
        }).encode()
        req = urllib.request.Request(
            self.url, data=body,
            headers={"content-type": "application/json",
                     "x-api-key": api_key, "anthropic-version": "2023-06-01"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read())
        text = "".join(b.get("text", "") for b in payload["content"])
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        return Recommendation(**json.loads(text))


@dataclass
class OpenAICompatProvider:
    """For free tiers exposing an OpenAI-compatible endpoint (e.g. GitHub Models).

    Set VANTA_LLM_BASE_URL, VANTA_LLM_MODEL and VANTA_LLM_API_KEY.
    """
    def diagnose_bucket(self, key: str) -> Recommendation:
        base = os.environ["VANTA_LLM_BASE_URL"].rstrip("/")
        body = json.dumps({
            "model": os.environ["VANTA_LLM_MODEL"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _bucket_to_prompt(key)},
            ],
            "temperature": 0,
        }).encode()
        req = urllib.request.Request(
            f"{base}/chat/completions", data=body,
            headers={"content-type": "application/json",
                     "authorization": f"Bearer {os.environ['VANTA_LLM_API_KEY']}"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read())
        text = payload["choices"][0]["message"]["content"].strip()
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```")
        return Recommendation(**json.loads(text))


@dataclass
class CachedProvider:
    cache: DiagnosisCache = field(default_factory=DiagnosisCache)
    source: LiveProvider | None = None
    allow_fallback: bool = False

    calls: int = 0
    hits: int = 0
    provider_failures: int = 0
    fallbacks: int = 0

    def diagnose(self, key: str) -> Recommendation:
        cached = self.cache.get(key)
        if cached is not None:
            self.hits += 1
            return cached
        if self.source is None:
            raise CacheMiss(
                f"no cached diagnosis for bucket {key!r} and no live provider. "
                "Rebuild the cache with `vanta build-cache`, or run an arm that "
                "does not need an LLM."
            )
        try:
            self.calls += 1
            rec = self.source.diagnose_bucket(key)
        except Exception:
            self.provider_failures += 1
            if not self.allow_fallback:
                raise
            self.fallbacks += 1
            rec = rules_diagnose(key.split("|")[0])
        self.cache.put(key, rec)
        return rec


class _StubProvider:
    """TEST DOUBLE ONLY.

    Returns a fixed low-confidence recommendation so the arm-C code path can be
    exercised without network access. It is NOT a model and must never be used
    to produce published numbers -- any results table built on this is fiction.
    Guarded by tests/test_stub_not_in_cache.py.
    """
    MARKER = "STUB-NOT-A-MODEL"

    def diagnose_bucket(self, key: str) -> Recommendation:
        return Recommendation(
            root_cause=RootCause.UNKNOWN, recoverable=Recoverability.UNKNOWN,
            suggested_action=ActionKind.ABSTAIN, confidence=0.1,
            rationale=self.MARKER,
        )
