"""The metrics have to distinguish being right from merely sounding certain."""

from __future__ import annotations

import math

from agentbench.bench import CaseResult, EngineReport, agreement, disagreements


def result(
    ticket_id: str,
    gold_department: str,
    predicted: str,
    confidence: float,
    *,
    reason: str = "",
    priority: float = 2.0,
    gold_priority: int = 2,
    needs_human: float = 0.9,
    gold_needs_human: bool = True,
    engine_ms: float = 100.0,
    wall_ms: float = 120.0,
    time_to_route_ms: float = 60.0,
) -> CaseResult:
    return CaseResult(
        ticket_id=ticket_id,
        gold={
            "department": gold_department,
            "priority": gold_priority,
            "needs_human": gold_needs_human,
        },
        predicted_department=predicted,
        department_confidence=confidence,
        department_probabilities={},
        final_route=predicted,
        route_reason=reason,
        priority=priority,
        priority_confidence=0.8,
        needs_human=needs_human,
        resolution={},
        engine_ms=engine_ms,
        wall_ms=wall_ms,
        time_to_route_ms=time_to_route_ms,
        input_tokens=50,
        output_tokens=10,
        requests=1,
    )


def report(*results: CaseResult, name: str = "e") -> EngineReport:
    return EngineReport(engine=name, model="m", results=list(results))


def test_accuracy_and_zero_calibration_error_when_perfect():
    r = report(
        result("T-1", "billing", "billing", 1.0),
        result("T-2", "technical", "technical", 1.0),
    )
    assert r.department_accuracy == 1.0
    assert r.calibration_error == 0.0


def test_overconfidence_shows_up_as_calibration_error():
    r = report(
        result("T-1", "billing", "technical", 1.0),
        result("T-2", "technical", "technical", 1.0),
    )
    assert r.department_accuracy == 0.5
    # Claimed ~1.0, delivered 0.5.
    assert r.calibration_error > 0.4


def test_honest_uncertainty_scores_better_than_overconfidence():
    overconfident = report(
        result("T-1", "billing", "technical", 0.99),
        result("T-2", "technical", "technical", 0.99),
    )
    honest = report(
        result("T-1", "billing", "technical", 0.51),
        result("T-2", "technical", "technical", 0.99),
    )
    assert honest.calibration_error < overconfident.calibration_error


def test_confidence_separation_rewards_knowing_when_you_are_wrong():
    r = report(
        result("T-1", "billing", "billing", 0.9),
        result("T-2", "technical", "billing", 0.4),
    )
    assert math.isclose(r.confidence_separation, 0.5)


def test_confidence_separation_is_nan_without_both_outcomes():
    all_right = report(result("T-1", "billing", "billing", 0.9))
    assert math.isnan(all_right.confidence_separation)


def test_gate_catching_an_error_is_counted():
    r = report(
        result("T-1", "billing", "technical", 0.4, reason="department choice was uncertain"),
        result("T-2", "technical", "technical", 0.9, reason="department technical at 0.90"),
    )
    assert r.abstention_rate == 0.5
    assert r.caught_errors == 1.0


def test_caught_errors_is_nan_when_nothing_was_wrong():
    r = report(result("T-1", "billing", "billing", 0.9))
    assert math.isnan(r.caught_errors)


def test_priority_mae_uses_the_fractional_score():
    r = report(result("T-1", "billing", "billing", 0.9, priority=2.5, gold_priority=2))
    assert math.isclose(r.priority_mae, 0.5)


def test_needs_human_uses_the_policy_threshold():
    r = report(
        result("T-1", "billing", "billing", 0.9, needs_human=0.9, gold_needs_human=True),
        result("T-2", "billing", "billing", 0.9, needs_human=0.1, gold_needs_human=True),
    )
    assert r.needs_human_accuracy == 0.5


def test_failed_cases_are_excluded_not_counted_as_wrong():
    broken = result("T-2", "billing", "", 0.0)
    broken.error = "APIError: boom"
    r = report(result("T-1", "billing", "billing", 1.0), broken)

    assert len(r.scored) == 1
    assert r.department_accuracy == 1.0
    assert r.summary()["errors"] == 1


def test_empty_report_does_not_divide_by_zero():
    r = report()
    assert r.department_accuracy == 0.0
    assert r.priority_mae == 0.0
    assert r.total_tokens == 0
    assert r.p95_wall_ms == 0.0
    assert r.mean_time_to_route_ms == 0.0
    assert r.mean_overhead_ms == 0.0


def test_timing_metrics_separate_engine_from_graph():
    r = report(
        result("T-1", "billing", "billing", 0.9,
               engine_ms=300.0, wall_ms=340.0, time_to_route_ms=210.0),
        result("T-2", "billing", "billing", 0.9,
               engine_ms=100.0, wall_ms=160.0, time_to_route_ms=90.0),
    )
    assert r.mean_engine_ms == 200.0
    assert r.mean_wall_ms == 250.0
    assert r.mean_overhead_ms == 50.0
    assert r.mean_time_to_route_ms == 150.0


def test_time_to_decision_precedes_end_to_end():
    r = result("T-1", "billing", "billing", 0.9,
               engine_ms=300.0, wall_ms=340.0, time_to_route_ms=210.0)
    assert r.time_to_route_ms < r.wall_ms
    assert r.overhead_ms == 40.0


def test_overhead_never_goes_negative_on_clock_noise():
    r = result("T-1", "billing", "billing", 0.9, engine_ms=120.0, wall_ms=100.0)
    assert r.overhead_ms == 0.0


def test_agreement_and_disagreement_attribution():
    a = report(
        result("T-1", "billing", "billing", 0.9),
        result("T-2", "technical", "technical", 0.9),
        name="jev",
    )
    b = report(
        result("T-1", "billing", "technical", 0.9),
        result("T-2", "technical", "technical", 0.9),
        name="openai",
    )

    assert agreement(a, b)["department"] == 0.5

    rows = disagreements(a, b)
    assert len(rows) == 1
    assert rows[0]["ticket_id"] == "T-1"
    assert rows[0]["winner"] == "jev"


def test_disagreement_where_both_are_wrong():
    a = report(result("T-1", "escalation", "billing", 0.9), name="jev")
    b = report(result("T-1", "escalation", "technical", 0.9), name="openai")
    assert disagreements(a, b)[0]["winner"] == "neither"
