"""VANTA command line.

    vanta build-cache               populate data/diagnosis_cache.json (needs a key)
    vanta evaluate --suite development [--no-llm]
    vanta evaluate --suite holdout     refuses without POLICIES_FROZEN (ADR-003)
"""
from __future__ import annotations

import argparse
import pathlib
import sys

FREEZE_MARKER = pathlib.Path("POLICIES_FROZEN")


def _guard_holdout(suite: str) -> None:
    if suite == "holdout" and not FREEZE_MARKER.exists():
        sys.exit(
            "refusing to run holdout: POLICIES_FROZEN marker absent.\n"
            "Freeze the policies first (ADR-003). One shot, no re-tuning."
        )


def _provider(live: bool):
    import os

    from vanta.diagnosis.provider import (
        AnthropicProvider,
        CachedProvider,
        OpenAICompatProvider,
    )
    source = None
    if live:
        source = OpenAICompatProvider() if os.getenv("VANTA_LLM_BASE_URL") else AnthropicProvider()
    return CachedProvider(source=source)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="vanta")
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

    bc = sub.add_parser("build-cache")
    bc.add_argument("--events", type=int, default=2000)

    args = ap.parse_args(argv)

    if args.cmd == "build-cache":
        import os

        from vanta.diagnosis.provider import AnthropicProvider, OpenAICompatProvider
        from vanta.eval.build_cache import build
        src = OpenAICompatProvider() if os.getenv("VANTA_LLM_BASE_URL") else AnthropicProvider()
        build(src, n_events=args.events)
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
