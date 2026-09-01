# ADR-001: Align guardrail vocabulary with Razorpay's published agent principles

**Status:** accepted (2026-08-26)

## Context
Razorpay shipped Agent Studio in March 2026 (Claude Agent SDK), including a
Subscription Recovery Agent and a Cart Abandonment Recovery Agent, and
published a detailed post on principles, guardrails and merchant control.
VANTA occupies exactly this problem space. Inventing a parallel vocabulary
would read as not having done the homework.

Source: https://razorpay.com/blog/razorpay-agent-studio-principles-guardrails-and-merchant-control/

## Mapping

| Razorpay published principle | VANTA implementation | Status |
|---|---|---|
| Merchant defines permitted actions; scope checks block out-of-scope actions | `MerchantConfig.allowed_actions` + `rule_agent_scope` | mirrored |
| Review-first mode: agent does the work, merchant makes the final call | `Outcome.REVIEW_REQUIRED` + `MerchantConfig.review_first` | mirrored |
| Irreversible/sensitive actions never auto-approved | `REVIEW_REQUIRED_ACTIONS` | mirrored |
| Agent can be turned off, one tap, immediate | `MerchantConfig.enabled` + `rule_agent_enabled` | mirrored |
| Agents do not invent discounts; offers come from merchant coupon config | `rule_offer_within_merchant_ceiling` (`UNAPPROVED_OFFER`) | mirrored |
| Merchant's configured discount ceiling is the ceiling | same rule (`OFFER_EXCEEDS_MERCHANT_CEILING`) | mirrored |
| No escalation loop with bigger offers / more urgent language | `rule_no_escalating_offers` | mirrored |
| Amount validation against merchant configuration | `rule_spend_cap` | mirrored |
| Opt-out permanently suppressed, no exceptions | `rule_opted_out`, `CustomerState.suppressed_permanently` | mirrored |
| No dark patterns per India's Dark Patterns Guidelines, 2023 | `dark_patterns.screen()` + `rule_no_dark_patterns` | mirrored |
| Genuinely time-bound offers may be stated truthfully | `offer_time_bound` suppresses the false-urgency screen | mirrored |
| Every action logged with a full audit trail | `store/audit.py` (append-only) | in progress |
| Verified first-party data only | n/a -- synthetic world, no external data | out of scope |
| Certification, pricing, DPDPA/SOC2/PCI posture | n/a -- platform concerns | out of scope |

### VANTA additions beyond the published set
- Per-episode **attempt cap** (`rule_attempt_cap`)
- **Quiet hours** and **contact cooldown** (`rule_quiet_hours`, `rule_cooldown`)
- **Promise-to-pay** suppression window (`rule_promise_to_pay`)
- The **authority boundary itself** (ADR-002): Razorpay validates actions at the
  platform layer; VANTA makes it type-impossible for the model to mint one.

## Consequence
VANTA is not pitched as a novel agent -- Razorpay already ships these agents.
It is pitched as the **evaluation harness** for this class of agent: the thing
they have not published. Every guardrail above is a measured axis in the
benchmark, including its false-positive cost.
