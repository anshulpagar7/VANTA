"""Discrete-event simulation loop.

Events are processed in chronological order of their next decision point, not
grouped by event, because contact caps and cooldowns are per-customer and
events for the same customer interleave in time. A per-event loop would let a
policy contact one customer six times on the same day without ever tripping
the cap.
"""
from __future__ import annotations

import heapq
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from vanta.authorization.engine import PolicyEngine
from vanta.authorization.limits import DEFAULT_LIMITS, Limits
from vanta.authorization.merchant import DEFAULT_MERCHANT, MerchantConfig
from vanta.events.models import CustomerState, EventState
from vanta.execution.simulated import SimulatedExecutor
from vanta.store.audit import AuditLog, AuditRecord
from vanta.types import CONTACT_ACTIONS, MONEY_ACTIONS, Outcome
from vanta.world.generator import generate
from vanta.world.outcome import OutcomeModel

MAX_DECISIONS_PER_EVENT = 8


@dataclass
class RunStats:
    arm: str
    seed: int
    n_events: int = 0
    at_risk_paise: int = 0
    recovered_paise: int = 0
    recovered_events: int = 0
    authorized: int = 0
    blocked: int = 0
    abstained: int = 0
    review_required: int = 0
    contacts: int = 0
    money_actions: int = 0
    intervention_cost_paise: int = 0
    diagnosis_errors: int = 0
    diagnosed: int = 0
    block_reasons: dict[str, int] = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)

    @property
    def recovery_rate(self) -> float:
        return self.recovered_paise / self.at_risk_paise if self.at_risk_paise else 0.0

    @property
    def efficiency(self) -> float:
        c = self.intervention_cost_paise
        return self.recovered_paise / c if c else float("inf")

    @property
    def contacts_per_recovery(self) -> float:
        return self.contacts / self.recovered_events if self.recovered_events else float("inf")


def run_arm(
    policy,
    seed: int,
    n_events: int,
    log: AuditLog | None = None,
    run_id: str | None = None,
    limits: Limits = DEFAULT_LIMITS,
    merchant: MerchantConfig = DEFAULT_MERCHANT,
) -> RunStats:
    events, truth = generate(seed, n_events)
    world = OutcomeModel(seed, truth)
    executor = SimulatedExecutor(world)
    engine = PolicyEngine(limits=limits, merchant=merchant)
    run_id = run_id or uuid.uuid4().hex[:8]

    states: dict[str, CustomerState] = {}
    by_id = {e.event_id: e for e in events}
    stats = RunStats(arm=policy.name, seed=seed, n_events=len(events))
    stats.at_risk_paise = sum(e.amount_paise for e in events)
    resolved: set[str] = set()

    heap: list[tuple[datetime, int, str]] = []
    for i, e in enumerate(events):
        heapq.heappush(heap, (e.occurred_at, i, e.event_id))

    decisions: dict[str, int] = {}
    event_states: dict[str, EventState] = {e.event_id: EventState(e.event_id) for e in events}

    while heap:
        now, tiebreak, event_id = heapq.heappop(heap)
        if event_id in resolved:
            continue
        if decisions.get(event_id, 0) >= MAX_DECISIONS_PER_EVENT:
            continue
        decisions[event_id] = decisions.get(event_id, 0) + 1

        event = by_id[event_id]
        state = states.setdefault(event.customer_id, CustomerState(event.customer_id))
        es = event_states[event_id]
        # Project this event's facts into the state the guardrails read.
        state.attempts_on_event = es.attempts
        state.already_paid = es.paid

        request = policy.propose(event, state, now)
        if request is None:
            continue

        act_at = max(request.scheduled_for, now)
        decision = engine.authorize(request, state, act_at)

        rec = AuditRecord(
            run_id=run_id, arm=policy.name, seed=seed, decided_at=act_at,
            event_id=event_id, customer_id=event.customer_id,
            attempt_no=es.attempts + 1, reason_slug=event.reason,
            amount_paise=event.amount_paise,
            requested_action=request.action.value, outcome=decision.outcome.value,
            block_reason=decision.block_reason.value if decision.block_reason else None,
            cost_paise=request.cost_paise,
            rationale=request.justification or None,
        )

        if decision.outcome is Outcome.BLOCKED:
            stats.blocked += 1
            key = decision.block_reason.value
            stats.block_reasons[key] = stats.block_reasons.get(key, 0) + 1
        elif decision.outcome is Outcome.ABSTAINED:
            stats.abstained += 1
            resolved.add(event_id)   # a considered stop closes the episode
        elif decision.outcome is Outcome.REVIEW_REQUIRED:
            stats.review_required += 1
        else:
            stats.authorized += 1
            action = decision.authorized
            result = executor.execute(action)
            rec.authorization_id = action.authorization_id
            rec.succeeded = result.succeeded
            rec.recovered_paise = result.recovered_paise
            rec.world_trace = result.detail

            es.attempts += 1
            state.attempts_on_event = es.attempts
            state.spend_used_paise += request.cost_paise
            stats.intervention_cost_paise += request.cost_paise
            if request.action in CONTACT_ACTIONS:
                state.contacts_last_7d += 1
                state.last_contact_at = act_at
                stats.contacts += 1
            if request.action in MONEY_ACTIONS:
                state.last_attempt_at = act_at
                stats.money_actions += 1

            if result.succeeded:
                stats.recovered_paise += result.recovered_paise
                stats.recovered_events += 1
                es.paid = True
                state.already_paid = True
                resolved.add(event_id)

        if log is not None:
            log.append(rec)

        if event_id not in resolved:
            backoff = timedelta(hours=2) if decision.outcome is Outcome.BLOCKED else timedelta(minutes=1)
            heapq.heappush(heap, (act_at + backoff, tiebreak, event_id))

    stats.unresolved = [e.event_id for e in events if e.event_id not in resolved]
    if log is not None:
        log.commit()
    return stats
