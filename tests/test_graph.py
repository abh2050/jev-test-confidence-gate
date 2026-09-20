"""End-to-end graph behavior, driven by a scripted engine."""

from __future__ import annotations

import pytest

from agentbench.data import by_id
from agentbench.engines import build_engine
from agentbench.graph import build_graph, run_ticket
from agentbench.graph.supervisor import DEPARTMENTS

from .conftest import ScriptedEngine, choice, noul, score


@pytest.fixture
def graph():
    return build_graph()


def run(graph, engine, ticket_id="T-001"):
    ticket, _ = by_id(ticket_id)
    return run_ticket(graph, ticket, engine)


def test_graph_compiles_with_subgraphs_attached(graph):
    nodes = set(graph.get_graph().nodes)
    for name in ("triage", "gate", "finalize", *DEPARTMENTS):
        assert name in nodes


def test_confident_billing_ticket_runs_the_billing_subgraph(graph, engine):
    final = run(graph, engine)

    assert engine.asked == ["triage", "billing"]
    assert final["route"] == "billing"
    assert final["resolution"]["department"] == "billing"
    assert final["resolution"]["action"] == "full_refund"


def test_one_request_per_node_not_one_per_question(graph, engine):
    """Five triage judgments must cost one request, not five."""
    final = run(graph, engine)
    triage_usage = [u for u in final["usage"] if u["node"] == "supervisor.triage"]
    assert len(triage_usage) == 1
    assert triage_usage[0]["requests"] == 1


def test_trace_accumulates_across_parent_and_subgraph(graph, engine):
    final = run(graph, engine)
    nodes = [entry["node"] for entry in final["trace"]]
    assert nodes == [
        "supervisor.triage",
        "supervisor.gate",
        "billing.assess",
        "billing.decide",
        "supervisor.finalize",
    ]


def test_sla_and_priority_are_attached_by_finalize(graph, engine):
    final = run(graph, engine)
    resolution = final["resolution"]
    assert resolution["priority_label"] == "elevated"
    assert resolution["sla_hours"] == 8


def test_low_confidence_is_rerouted_to_escalation(graph, script):
    script["triage"]["department"] = choice(
        "billing", 0.40, {"billing": 0.40, "technical": 0.35, "escalation": 0.25}
    )
    engine = ScriptedEngine(script)
    final = run(graph, engine)

    assert engine.asked == ["triage", "escalation"]
    assert final["route"] == "escalation"
    assert "uncertain" in final["resolution"]["routed_here_because"]


def test_critical_ticket_bypasses_its_department(graph, script):
    script["triage"]["department"] = choice(
        "technical", 0.95, {"billing": 0.02, "technical": 0.95, "escalation": 0.03}
    )
    script["triage"]["priority"] = score(3.0)
    script["triage"]["needs_human"] = noul(0.95)
    engine = ScriptedEngine(script)
    final = run(graph, engine)

    assert final["route"] == "escalation"
    assert final["resolution"]["sla_hours"] == 1


def test_technical_branch_pages_oncall_on_severity(graph, script):
    script["triage"]["department"] = choice(
        "technical", 0.95, {"billing": 0.02, "technical": 0.95, "escalation": 0.03}
    )
    script["triage"]["needs_human"] = noul(0.1)
    engine = ScriptedEngine(script)
    final = run(graph, engine)

    assert final["route"] == "technical"
    assert final["resolution"]["page_oncall"] is True


def test_data_loss_pages_oncall_even_when_severity_is_low(graph, script):
    script["triage"]["department"] = choice(
        "technical", 0.95, {"billing": 0.02, "technical": 0.95, "escalation": 0.03}
    )
    script["triage"]["needs_human"] = noul(0.1)
    script["technical"]["severity"] = score(0.2)
    script["technical"]["data_loss_risk"] = noul(0.8)
    engine = ScriptedEngine(script)
    final = run(graph, engine)

    assert final["resolution"]["page_oncall"] is True


def test_legal_exposure_overrides_the_tier_choice(graph, script):
    script["triage"]["department"] = choice(
        "escalation", 0.9, {"billing": 0.05, "technical": 0.05, "escalation": 0.9}
    )
    script["escalation"]["legal_exposure"] = noul(0.85)
    engine = ScriptedEngine(script)
    final = run(graph, engine)

    # The model chose tier_two; code overrode it because legal is a separate
    # condition, not something a score should average away.
    assert final["resolution"]["assigned_to"] == "legal_review"


def test_large_refund_is_held_for_approval(graph, script):
    engine = ScriptedEngine(script)
    final = run(graph, engine, ticket_id="T-003")  # $588 annual plan

    assert final["resolution"]["refund_usd"] == 588.0
    assert final["resolution"]["requires_approval"] is True


def test_fake_engine_runs_the_whole_graph_without_keys(graph):
    engine = build_engine("fake")
    ticket, _ = by_id("T-006")
    final = run_ticket(graph, ticket, engine)

    assert final["route"] in DEPARTMENTS
    assert "sla_hours" in final["resolution"]


def test_fake_engine_is_deterministic(graph):
    ticket, _ = by_id("T-013")
    first = run_ticket(graph, ticket, build_engine("fake"))
    second = run_ticket(graph, ticket, build_engine("fake"))
    assert first["triage"] == second["triage"]


def test_timings_are_recorded_and_ordered(graph, engine):
    final = run(graph, engine)

    # The scripted engine reports 10ms per call and there are two calls.
    assert final["wall_ms"] > 0
    assert final["time_to_route_ms"] > 0
    # The routing decision must land before the run finishes.
    assert final["time_to_route_ms"] <= final["wall_ms"]


def test_time_to_route_covers_triage_but_not_the_subgraph(graph, engine):
    final = run(graph, engine)
    engine_ms = sum(u["latency_ms"] for u in final["usage"])

    # Two engine calls at 10ms each; the decision is made after only the first.
    assert engine_ms == 20.0
    assert final["time_to_route_ms"] < engine_ms


def test_gate_records_the_decision_time_in_the_trace(graph, engine):
    final = run(graph, engine)
    gate_entry = next(e for e in final["trace"] if e["node"] == "supervisor.gate")
    assert "time_to_route_ms" in gate_entry
    assert gate_entry["time_to_route_ms"] > 0
