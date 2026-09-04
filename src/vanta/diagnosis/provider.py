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
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

from vanta.diagnosis.cache import CacheMiss, DiagnosisCache
from vanta.diagnosis.deterministic import diagnose as rules_diagnose
from vanta.diagnosis.schema import Recommendation
from vanta.types import ActionKind, Recoverability, RootCause

# Some providers sit behind Cloudflare, which fingerprints and blocks the
# default urllib User-Agent (bare "Python-urllib/3.x") as a bot -- surfacing
# as an opaque Cloudflare 403 (error code 1010), not a provider auth error.
DEFAULT_HEADERS = {"user-agent": "vanta-benchmark/0.1 (+https://github.com)"}

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


class ProviderError(RuntimeError):
    """Carries the provider's response body, which is where the real reason is."""


# Transient: the provider is fine, it is just busy or throttling us.
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
MAX_ATTEMPTS = 8

# Free tiers are quota-limited per minute. Pacing requests below the limit is
# cheaper than discovering it: a 429 costs a call AND a wait, and on a 144
# bucket build that compounds into an aborted run.
DEFAULT_MIN_INTERVAL_S = 3.5

_RETRY_AFTER = re.compile(r"retry in ([0-9.]+)s", re.I)


class _Throttle:
    """Minimum spacing between calls to one provider."""

    def __init__(self, min_interval: float = DEFAULT_MIN_INTERVAL_S) -> None:
        self.min_interval = min_interval
        self._last = 0.0

    def wait(self, sleep=time.sleep) -> None:
        gap = time.monotonic() - self._last
        if self._last and gap < self.min_interval:
            sleep(self.min_interval - gap)
        self._last = time.monotonic()


def _post(req: urllib.request.Request, provider: str, *,
          max_attempts: int = MAX_ATTEMPTS, sleep=time.sleep,
          throttle: _Throttle | None = None) -> dict:
    """POST with exponential backoff on transient failures.

    A 144-bucket build will meet a 429 or a 503 sooner or later. Aborting the
    whole run on one of them wastes every call already made, so transient
    statuses are retried with jitter and only a persistent failure is raised.
    """
    delay = 2.0
    last: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        if throttle is not None:
            throttle.wait(sleep)
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:600]
            last = ProviderError(f"{provider} HTTP {exc.code}: {body}")
            if exc.code not in RETRYABLE_STATUS or attempt == max_attempts:
                raise last from exc
            # Providers often state exactly how long to wait. Believe them:
            # guessing shorter just burns another call against the quota.
            stated = _RETRY_AFTER.search(body)
            wait = float(stated.group(1)) + 1.0 if stated else (
                delay + random.uniform(0, delay / 2))
            print(f"    {provider} HTTP {exc.code}, retry {attempt}/{max_attempts - 1} "
                  f"in {wait:.0f}s")
            sleep(wait)
            delay = min(delay * 2, 60.0)
        except urllib.error.URLError as exc:
            last = ProviderError(f"{provider} network error: {exc.reason}")
            if attempt == max_attempts:
                raise last from exc
            sleep(delay)
            delay = min(delay * 2, 60.0)
    raise last  # pragma: no cover


def list_models(base_url: str, api_key_env: str) -> list[str]:
    """Ask an OpenAI-compatible endpoint what model ids it will accept."""
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/models",
        headers={**DEFAULT_HEADERS, "authorization": f"Bearer {os.environ[api_key_env]}"},
    )
    payload = _post(req, "models-list")
    return sorted(m.get("id", "?") for m in payload.get("data", []))


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
            headers={**DEFAULT_HEADERS, "content-type": "application/json",
                     "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                     "anthropic-version": "2023-06-01"},
        )
        payload = _post(req, self.name)
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
    min_interval_s: float = DEFAULT_MIN_INTERVAL_S
    _throttle: _Throttle | None = None

    def __post_init__(self) -> None:
        self._throttle = _Throttle(self.min_interval_s)

    def diagnose_bucket(self, key: str) -> Recommendation:
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _bucket_to_prompt(key)},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions", data=body,
            headers={**DEFAULT_HEADERS, "content-type": "application/json",
                     "authorization": f"Bearer {os.environ[self.api_key_env]}"},
        )
        payload = _post(req, self.name, throttle=self._throttle)
        text = payload["choices"][0]["message"]["content"]
        return Recommendation(**json.loads(_strip_fences(text)))


@dataclass
class GeminiNativeProvider:
    """Google's own generateContent endpoint.

    Used in preference to Google's OpenAI-compatibility shim, which returned
    404 in practice. Native also supports responseMimeType=application/json,
    so the model is constrained to emit JSON rather than asked politely.
    """
    name: str = "gemini"
    model: str = "gemini-3.6-flash"
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    api_key_env: str = "GEMINI_API_KEY"
    min_interval_s: float = DEFAULT_MIN_INTERVAL_S
    _throttle: _Throttle | None = None

    def __post_init__(self) -> None:
        self._throttle = _Throttle(self.min_interval_s)

    def diagnose_bucket(self, key: str) -> Recommendation:
        url = f"{self.base_url}/models/{self.model}:generateContent"
        body = json.dumps({
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": _bucket_to_prompt(key)}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "maxOutputTokens": 2048,
            },
        }).encode()
        req = urllib.request.Request(
            url, data=body,
            headers={**DEFAULT_HEADERS, "content-type": "application/json",
                     "x-goog-api-key": os.environ[self.api_key_env]},
        )
        payload = _post(req, self.name, throttle=self._throttle)
        try:
            parts = payload["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError) as exc:
            raise ProviderError(
                f"{self.name}: unexpected response shape: {json.dumps(payload)[:400]}"
            ) from exc
        if not text.strip():
            raise ProviderError(f"{self.name}: empty response: {json.dumps(payload)[:400]}")
        return Recommendation(**json.loads(_strip_fences(text)))


def gemini(model: str | None = None,
           min_interval_s: float = DEFAULT_MIN_INTERVAL_S) -> GeminiNativeProvider:
    m = model or GeminiNativeProvider.model
    return GeminiNativeProvider(name=f"gemini:{m}", model=m,
                                min_interval_s=min_interval_s)


def grok(model: str = "grok-4.3") -> OpenAICompatProvider:
    return OpenAICompatProvider(
        name=f"grok:{model}", base_url="https://api.x.ai/v1",
        model=model, api_key_env="XAI_API_KEY",
    )


def groq(model: str = "llama-3.3-70b-versatile",
         min_interval_s: float = 2.5) -> OpenAICompatProvider:
    """Groq (not Grok). Free tier, OpenAI-compatible, very fast."""
    return OpenAICompatProvider(
        name=f"groq:{model}", base_url="https://api.groq.com/openai/v1",
        model=model, api_key_env="GROQ_API_KEY", min_interval_s=min_interval_s,
    )


def openrouter(model: str = "meta-llama/llama-3.3-70b-instruct:free",
               min_interval_s: float = 3.0) -> OpenAICompatProvider:
    """OpenRouter. Models suffixed ':free' cost nothing."""
    return OpenAICompatProvider(
        name=f"openrouter:{model}", base_url="https://openrouter.ai/api/v1",
        model=model, api_key_env="OPENROUTER_API_KEY", min_interval_s=min_interval_s,
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
                self.errors.setdefault(provider.name, []).append(str(exc)[:400])
                last_exc = exc
        detail = "\n".join(f"  {k}: {v[-1]}" for k, v in self.errors.items())
        raise RuntimeError(
            f"every provider failed for bucket {key!r}:\n{detail}"
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
