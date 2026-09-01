"""FROZEN EVENT GENERATOR.

Generates a batch of revenue-at-risk events plus the hidden ground truth the
outcome model resolves against. Part of the frozen world: policies are tuned
against development seeds and never see holdout events before the freeze.
"""
from __future__ import annotations

import hashlib
import struct
from datetime import datetime, timedelta

from vanta.events.models import RevenueEvent
from vanta.types import FailureSource, FailureStep
from vanta.world import params
from vanta.world.outcome import GroundTruth

DEV_SEEDS = (11, 12, 13, 14, 15)
HOLDOUT_SEEDS = (101, 102, 103, 104, 105)

EPOCH = datetime(2026, 6, 1, 0, 0)

# reason slug -> (source, step, method pool, share of batch). provenance:
# slugs and source/step axes sourced from Razorpay error docs; the mix is assumed.
REASON_MIX: tuple[tuple[str, FailureSource, FailureStep, tuple[str, ...], float], ...] = (
    ("payment_failed",          FailureSource.BANK,     FailureStep.PAYMENT_AUTHORIZATION, ("card", "upi"), 0.22),
    ("gateway_timeout",         FailureSource.GATEWAY,  FailureStep.PAYMENT_AUTHORIZATION,
     ("card", "netbanking"), 0.10),
    ("gateway_technical_error", FailureSource.GATEWAY, FailureStep.PAYMENT_INITIATION,
     ("netbanking",), 0.05),
    ("insufficient_funds",      FailureSource.BANK,    FailureStep.PAYMENT_AUTHORIZATION,
     ("card", "upi", "emandate"), 0.12),
    ("invalid_otp",             FailureSource.CUSTOMER, FailureStep.PAYMENT_AUTHENTICATION,("card",), 0.08),
    ("payment_timeout",         FailureSource.CUSTOMER, FailureStep.PAYMENT_AUTHENTICATION,("upi",), 0.07),
    ("card_declined",           FailureSource.BANK,     FailureStep.PAYMENT_AUTHORIZATION, ("card",), 0.08),
    ("method_unsupported",      FailureSource.BUSINESS, FailureStep.PAYMENT_INITIATION,    ("wallet",), 0.03),
    ("mandate_revoked",         FailureSource.CUSTOMER, FailureStep.MANDATE_DEBIT,         ("emandate",), 0.05),
    ("checkout_abandoned",      FailureSource.CUSTOMER, FailureStep.CHECKOUT,              ("card", "upi"), 0.14),
    ("invoice_overdue",         FailureSource.BUSINESS, FailureStep.INVOICE_DUE,           ("netbanking",), 0.06),
)


def _u(seed: int, *parts) -> float:
    key = ("|".join([str(seed), *map(str, parts)])).encode()
    return struct.unpack("<Q", hashlib.blake2b(key, digest_size=8).digest())[0] / 2**64


def _pick(u: float, weighted: dict) -> object:
    total = sum(weighted.values())
    acc = 0.0
    for key, w in weighted.items():
        acc += w / total
        if u < acc:
            return key
    return list(weighted)[-1]


def generate(seed: int, n: int) -> tuple[list[RevenueEvent], dict[str, GroundTruth]]:
    events: list[RevenueEvent] = []
    truth: dict[str, GroundTruth] = {}

    mix = {row[0]: row[4] for row in REASON_MIX}
    meta = {row[0]: row for row in REASON_MIX}
    lo, hi = params.RESPONSIVENESS_RANGE

    for i in range(n):
        eid = f"evt_{seed}_{i:06d}"
        cid = f"cust_{seed}_{i // 3:06d}"          # ~3 events per customer
        reason = _pick(_u(seed, "reason", i), mix)
        _, source, step, methods, _w = meta[reason]
        method = methods[int(_u(seed, "method", i) * len(methods)) % len(methods)]

        # Log-ish amount spread: most small, a few large.
        u_amt = _u(seed, "amount", i)
        amount = int(20_000 * (1.0 + 60.0 * u_amt**3))     # paise: ~200 to ~120k

        occurred = EPOCH + timedelta(hours=_u(seed, "when", i) * 24 * 30)

        # Hidden ground truth: the true root cause is sampled from the
        # ambiguity distribution of the reason slug. Policies see the slug.
        root = _pick(_u(seed, "root", i), params.REASON_TO_ROOT_CAUSE[reason])
        responsiveness = lo + (hi - lo) * _u(seed, "resp", cid)

        events.append(RevenueEvent(
            event_id=eid, customer_id=cid, amount_paise=amount,
            occurred_at=occurred, source=source, step=step,
            reason=reason, method=method, attempt_no=1,
        ))
        truth[eid] = GroundTruth(
            root_cause=root, responsiveness=responsiveness,
            occurred_at=occurred, amount_paise=amount,
        )

    return events, truth
