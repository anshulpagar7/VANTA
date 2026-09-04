"""VANTA command line.

    vanta build-cache               populate data/diagnosis_cache.json (needs a key)
    vanta evaluate --suite development [--no-llm]
    vanta evaluate --suite holdout     refuses without POLICIES_FROZEN (ADR-003)
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

from vanta import BUILD, __version__

FREEZE_MARKER = pathlib.Path("POLICIES_FROZEN")


def _guard_holdout(suite: str) -> None:
    if suite == "holdout" and not FREEZE_MARKER.exists():
        sys.exit(
            "refusing to run holdout: POLICIES_FROZEN marker absent.\n"
            "Freeze the policies first (ADR-003). One shot, no re-tuning."
        )


def _live_chain(gemini_model: str | None = None, grok_model: str | None = None,
                min_interval: float | None = None, groq_model: str | None = None):
    """Build a fallback chain from whichever API keys are present.

    Order is fixed and explicit so a build is reproducible: the same keys
    always produce the same preference. Each bucket records which provider
    actually answered.
    """
    from vanta.config import load_dotenv, present_keys, redact
    from vanta.diagnosis.provider import (
        DEFAULT_MIN_INTERVAL_S,
        AnthropicProvider,
        FallbackChain,
        gemini,
        github_models,
        grok,
        groq,
        openrouter,
    )

    interval = DEFAULT_MIN_INTERVAL_S if min_interval is None else min_interval

    load_dotenv()
    found = present_keys()
    if found:
        print("keys found: " + ", ".join(f"{k}={redact(os.environ[k])}" for k in found))

    chain = []
    if os.getenv("GEMINI_API_KEY"):
        chain.append(gemini(gemini_model, min_interval_s=interval))
    if os.getenv("GROQ_API_KEY"):
        chain.append(groq(groq_model) if groq_model else groq())
    if os.getenv("OPENROUTER_API_KEY"):
        chain.append(openrouter())
    if os.getenv("XAI_API_KEY"):
        chain.append(grok(grok_model) if grok_model else grok())
    if os.getenv("ANTHROPIC_API_KEY"):
        chain.append(AnthropicProvider())
    if os.getenv("GITHUB_TOKEN"):
        chain.append(github_models())
    if not chain:
        sys.exit(
            "no API key found. Set one of GEMINI_API_KEY, GROQ_API_KEY, "
            "OPENROUTER_API_KEY, XAI_API_KEY, ANTHROPIC_API_KEY or GITHUB_TOKEN "
            "in the environment, or copy .env.example to .env and fill it in."
        )
    return FallbackChain(chain)


def _provider(live: bool):
    from vanta.diagnosis.provider import CachedProvider

    return CachedProvider(source=_live_chain() if live else None)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="vanta")
    ap.add_argument("--version", action="version",
                    version=f"vanta {__version__} (build {BUILD})")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ev = sub.add_parser("evaluate")
    ev.add_argument("--suite", choices=["development", "holdout"], default="development")
    ev.add_argument("--events", type=int, default=1000)
    ev.add_argument("--no-llm", action="store_true",
                    help="replay the committed diagnosis cache; no key, no spend")
    ev.add_argument("--skip-llm-arm", action="store_true",
                    help="run arms A/B/B+ only (before the diagnosis cache exists)")
    ev.add_argument("--audit", default=None, help="path for the SQLite audit log")
    ev.add_argument("--report", default=None, help="path for the generated HTML report")

    ck = sub.add_parser(
        "check-provider",
        help="one call against one bucket, with the provider's raw error. "
             "Debug here, not inside a 144-bucket loop.",
    )
    ck.add_argument("--gemini-model", default=None)
    ck.add_argument("--grok-model", default=None)
    ck.add_argument("--groq-model", default=None)
    ck.add_argument("--list-models", action="store_true",
                    help="ask the endpoint which model ids it accepts")

    bc = sub.add_parser("build-cache")
    bc.add_argument("--events", type=int, default=2000)
    bc.add_argument("--gemini-model", default=None, help="override the Gemini model id")
    bc.add_argument("--grok-model", default=None, help="override the Grok model id")
    bc.add_argument("--groq-model", default=None, help="override the Groq model id")
    bc.add_argument("--min-interval", type=float, default=None,
                    help="seconds between calls (default 3.5, ~17 req/min; raise "
                         "this if the free-tier quota is lower)")

    args = ap.parse_args(argv)

    print(f"vanta {__version__} build {BUILD}")

    if args.cmd == "check-provider":
        from vanta.diagnosis.provider import ProviderError, list_models

        chain = _live_chain(args.gemini_model, args.grok_model,
                            groq_model=args.groq_model)
        probe = "gateway_timeout|gateway|payment_authorization|card|small|first"
        for provider in chain.providers:
            print(f"\n--- {provider.name} ---")
            if args.list_models and hasattr(provider, "base_url"):
                try:
                    models = list_models(provider.base_url, provider.api_key_env)
                    print(f"  accepts {len(models)} models, e.g.:")
                    for m in models[:25]:
                        print(f"    {m}")
                except (ProviderError, KeyError) as exc:
                    print(f"  could not list models: {exc}")
            try:
                rec = provider.diagnose_bucket(probe)
                print(f"  OK -> {rec.root_cause.value} / {rec.suggested_action.value} "
                      f"(confidence {rec.confidence})")
            except Exception as exc:  # noqa: BLE001 - this command exists to show it
                print(f"  FAILED: {exc}")
        return

    if args.cmd == "build-cache":
        from vanta.eval.build_cache import build

        chain = _live_chain(args.gemini_model, args.grok_model, args.min_interval,
                            args.groq_model)
        print("provider order: " + " -> ".join(p.name for p in chain.providers))
        build(chain, n_events=args.events)
        return

    _guard_holdout(args.suite)
    from vanta.eval.harness import evaluate

    audit = args.audit or f"results/{args.suite}/audit.sqlite3"
    report = args.report or f"results/{args.suite}/report.html"
    pathlib.Path(audit).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(audit).unlink(missing_ok=True)
    evaluate(
        suite=args.suite, n_events=args.events,
        provider=_provider(live=not args.no_llm),
        log_path=audit, report_path=report, skip_llm_arm=args.skip_llm_arm,
    )
