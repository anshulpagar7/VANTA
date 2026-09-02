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


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1] if "\n" in t else t
        t = t.removeprefix("json").removeprefix("```")
    return t.removesuffix("```").strip()


def _bucket_to_prompt(key: str) -> str:
    reason, source, step, method, size, attempt = key.split("|")
    return (
        f"reason={reason}\nsource={source}\nstep={step}\nmethod={method}\n"
        f"amount_band={size}\nattempt_band={attempt}"
    )


@dataclass
class AnthropicProvider:
    """Anthropic Messages API. Requires ANTHROPIC_API_KEY."""
    name: str = "anthropic"
    model: str = "claude-haiku-4-5-20251001"
    url: str = "https://api.anthropic.com/v1/messages"

    def diagnose_bucket(self, key: str) -> Recommendation:
        body = json.dumps({
            "model": self.model, "max_tokens": 300,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": _bucket_to_prompt(key)}],
        }).encode()
        req = urllib.request.Request(
            self.url, data=body,
            headers={"content-type": "application/json",
                     "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                     "anthropic-version": "2023-06-01"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read())
        text = "".join(b.get("text", "") for b in payload["content"])
        return Recommendation(**json.loads(_strip_fences(text)))


@dataclass
class OpenAICompatProvider:
    """Any OpenAI-compatible chat-completions endpoint.

    Gemini, Grok, GitHub Models and most free tiers all speak this shape, so
    one class covers the lot. See GEMINI / GROK below for presets.
    """
    name: str
    base_url: str
    model: str
    api_key_env: str

    def diagnose_bucket(self, key: str) -> Recommendation:
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _bucket_to_prompt(key)},
            ],
            "temperature": 0,
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions", data=body,
            headers={"content-type": "application/json",
                     "authorization": f"Bearer {os.environ[self.api_key_env]}"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read())
        text = payload["choices"][0]["message"]["content"]
        return Recommendation(**json.loads(_strip_fences(text)))


def gemini(model: str = "gemini-2.5-flash") -> OpenAICompatProvider:
    return OpenAICompatProvider(
        name=f"gemini:{model}",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        model=model, api_key_env="GEMINI_API_KEY",
    )


def grok(model: str = "grok-4.3") -> OpenAICompatProvider:
    return OpenAICompatProvider(
        name=f"grok:{model}", base_url="https://api.x.ai/v1",
        model=model, api_key_env="XAI_API_KEY",
    )


def github_models(model: str = "gpt-4o-mini") -> OpenAICompatProvider:
    return OpenAICompatProvider(
        name=f"github:{model}", base_url="https://models.inference.ai.azure.com",
        model=model, api_key_env="GITHUB_TOKEN",
    )


@dataclass
class FallbackChain:
    """Try providers in order; the first that answers wins.

    Per-bucket fallback keeps a cache build alive through a rate limit or an
    outage, but it means arm C can end up an accidental two-model ensemble.
    Every entry therefore records which provider served it, and the report
    prints the mix. A build that is 50/50 across two models is a finding to
    disclose, not an average to hide.
    """
    providers: list
    name: str = "fallback"
    errors: dict = field(default_factory=dict)

    @property
    def last_provider(self) -> str:
        return self._last

    def __post_init__(self) -> None:
        self._last = "unknown"

    def diagnose_bucket(self, key: str) -> Recommendation:
        last_exc: Exception | None = None
        for provider in self.providers:
            try:
                rec = provider.diagnose_bucket(key)
                self._last = provider.name
                return rec
            except Exception as exc:  # noqa: BLE001 - any provider failure falls through
                self.errors.setdefault(provider.name, []).append(f"{type(exc).__name__}")
                last_exc = exc
        raise RuntimeError(
            f"every provider failed for bucket {key!r}: "
            + "; ".join(f"{k} x{len(v)}" for k, v in self.errors.items())
        ) from last_exc


@dataclass
class CachedProvider:
    cache: DiagnosisCache = field(default_factory=DiagnosisCache)
    source: LiveProvider | None = None
    # Falling back to RULES (not to another model) would make arm C secretly
    # arm B+. Off by default; every use is counted and reported.
    allow_rules_fallback: bool = False

    calls: int = 0
    hits: int = 0
    provider_failures: int = 0
    rules_fallbacks: int = 0

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
            provider = getattr(self.source, "last_provider", None) or getattr(
                self.source, "name", "unknown")
        except Exception:
            self.provider_failures += 1
            if not self.allow_rules_fallback:
                raise
            self.rules_fallbacks += 1
            rec = rules_diagnose(key.split("|")[0])
            provider = "rules-fallback"
        self.cache.put(key, rec, provider=provider)
        return rec


class _StubProvider:
    """TEST DOUBLE ONLY.

    Returns a fixed low-confidence recommendation so the arm-C code path can be
    exercised without network access. It is NOT a model and must never be used
    to produce published numbers -- any results table built on this is fiction.
    Guarded by tests/test_stub_not_in_cache.py.
    """
    MARKER = "STUB-NOT-A-MODEL"
    name = "stub"

    def diagnose_bucket(self, key: str) -> Recommendation:
        return Recommendation(
            root_cause=RootCause.UNKNOWN, recoverable=Recoverability.UNKNOWN,
            suggested_action=ActionKind.ABSTAIN, confidence=0.1,
            rationale=self.MARKER,
        )
