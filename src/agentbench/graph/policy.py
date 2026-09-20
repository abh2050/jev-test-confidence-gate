"""Deterministic policy.

Nothing here calls a model. Thresholds, money rules and SLAs are ordinary code
so that both engines are judged against identical downstream behavior — the only
difference between two benchmark runs is the numbers the judgment layer fed in.

Tune these against your own data and consequences; the values below are starting
points, not defaults anyone validated for your domain.
"""

from __future__ import annotations

from typing import Any

from ..types import PRIORITY_LEVELS

# Below this, the department choice is too close to call and a human routes it.
DEPARTMENT_CONFIDENCE_FLOOR = 0.55
# Above this probability, treat "needs a human" as settled.
NEEDS_HUMAN_THRESHOLD = 0.65
# Priority is an expected score over PRIORITY_LEVELS; 2.5 sits between
# "elevated" and "critical".
CRITICAL_PRIORITY = 2.5

# Refunds above this need a supervisor regardless of how confident the model is.
REFUND_APPROVAL_LIMIT_USD = 200.0
# A refund the model itself flags as a policy exception needs approval too.
POLICY_EXCEPTION_THRESHOLD = 0.6

SLA_HOURS = {0: 72, 1: 24, 2: 8, 3: 1}


def priority_label(score: float) -> str:
    """Name the nearest level for display, keeping the fractional score intact."""
    index = max(0, min(len(PRIORITY_LEVELS) - 1, round(score)))
    return PRIORITY_LEVELS[index]


def sla_hours(score: float) -> int:
    index = max(0, min(len(SLA_HOURS) - 1, round(score)))
    return SLA_HOURS[index]


def route_from_triage(triage: dict[str, Any]) -> tuple[str, str]:
    """Pick the branch, and say why.

    Confidence-gated routing: an uncertain department choice is not a reason to
    guess, it is a reason to send the ticket somewhere a human will see it.
    """
    department = triage["department"]
    confidence = triage["department_confidence"]
    needs_human = triage["needs_human"]
    priority = triage["priority"]

    if confidence < DEPARTMENT_CONFIDENCE_FLOOR:
        return (
            "escalation",
            f"department choice was uncertain ({confidence:.2f} < "
            f"{DEPARTMENT_CONFIDENCE_FLOOR}); routed to a human",
        )

    if priority >= CRITICAL_PRIORITY and needs_human >= NEEDS_HUMAN_THRESHOLD:
        return (
            "escalation",
            f"priority {priority:.2f} with needs_human {needs_human:.2f}; "
            "too urgent for the standard queue",
        )

    return department, f"department {department} at confidence {confidence:.2f}"


def refund_requires_approval(
    action: str, amount_usd: float, policy_exception: float
) -> tuple[bool, str]:
    """Money rules stay in code; the model only described the situation."""
    if action not in ("full_refund", "partial_credit"):
        return False, ""
    if amount_usd > REFUND_APPROVAL_LIMIT_USD:
        return True, f"amount ${amount_usd:.2f} exceeds ${REFUND_APPROVAL_LIMIT_USD:.2f}"
    if policy_exception >= POLICY_EXCEPTION_THRESHOLD:
        return True, f"flagged as a policy exception ({policy_exception:.2f})"
    return False, ""


def refund_amount(action: str, order_total_usd: float) -> float:
    if action == "full_refund":
        return order_total_usd
    if action == "partial_credit":
        return round(order_total_usd * 0.5, 2)
    return 0.0
