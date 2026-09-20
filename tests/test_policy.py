"""Policy is the part that must behave identically for both engines."""

from __future__ import annotations

import pytest

from agentbench.graph import policy


def triage(department="billing", confidence=0.9, needs_human=0.2, priority=1.0):
    return {
        "department": department,
        "department_confidence": confidence,
        "needs_human": needs_human,
        "priority": priority,
    }


def test_confident_ticket_goes_to_its_department():
    route, reason = policy.route_from_triage(triage())
    assert route == "billing"
    assert "0.90" in reason


def test_uncertain_department_is_handed_to_a_human():
    route, reason = policy.route_from_triage(triage(confidence=0.4))
    assert route == "escalation"
    assert "uncertain" in reason


def test_confidence_floor_is_inclusive_from_above():
    below = policy.DEPARTMENT_CONFIDENCE_FLOOR - 0.001
    assert policy.route_from_triage(triage(confidence=below))[0] == "escalation"
    at = policy.DEPARTMENT_CONFIDENCE_FLOOR
    assert policy.route_from_triage(triage(confidence=at))[0] == "billing"


def test_critical_and_human_needed_overrides_department():
    route, reason = policy.route_from_triage(
        triage(department="technical", priority=3.0, needs_human=0.9)
    )
    assert route == "escalation"
    assert "urgent" in reason


def test_critical_alone_does_not_escalate():
    # High priority that automation can still handle stays in its queue.
    route, _ = policy.route_from_triage(
        triage(department="technical", priority=3.0, needs_human=0.1)
    )
    assert route == "technical"


def test_needs_human_alone_does_not_escalate():
    route, _ = policy.route_from_triage(
        triage(department="technical", priority=1.0, needs_human=0.99)
    )
    assert route == "technical"


@pytest.mark.parametrize(
    "score,label,hours",
    [(0.0, "routine", 72), (1.2, "normal", 24), (2.4, "elevated", 8), (2.6, "critical", 1)],
)
def test_priority_ladder(score, label, hours):
    assert policy.priority_label(score) == label
    assert policy.sla_hours(score) == hours


def test_priority_helpers_clamp_out_of_range_scores():
    assert policy.priority_label(99.0) == "critical"
    assert policy.priority_label(-5.0) == "routine"
    assert policy.sla_hours(99.0) == 1
    assert policy.sla_hours(-5.0) == 72


def test_large_refund_needs_approval_however_confident_the_model_was():
    needed, reason = policy.refund_requires_approval("full_refund", 588.0, 0.01)
    assert needed
    assert "exceeds" in reason


def test_policy_exception_needs_approval_even_when_small():
    needed, reason = policy.refund_requires_approval("full_refund", 10.0, 0.9)
    assert needed
    assert "exception" in reason


def test_small_clean_refund_is_automatic():
    assert policy.refund_requires_approval("full_refund", 10.0, 0.05) == (False, "")


@pytest.mark.parametrize("action", ["explain_charge", "request_info"])
def test_non_payouts_never_need_refund_approval(action):
    assert policy.refund_requires_approval(action, 99999.0, 0.99)[0] is False
    assert policy.refund_amount(action, 100.0) == 0.0


def test_refund_amounts():
    assert policy.refund_amount("full_refund", 100.0) == 100.0
    assert policy.refund_amount("partial_credit", 100.0) == 50.0
