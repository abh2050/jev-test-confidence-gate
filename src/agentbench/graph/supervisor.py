"""The parent graph.

One supervisor judgment routes the ticket into one of three compiled subgraphs,
which are attached directly as nodes because they share the parent's state keys.
The engine travels in `config`, not in state, so the graph stays serializable and
the same compiled graph can be run against either engine.
"""

from __future__ import annotations

import time
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from ..engines import TRIAGE
from ..engines.base import DecisionEngine
from ..types import DEPARTMENTS, Ticket
from .policy import priority_label, route_from_triage, sla_hours
from .state import SharedState, trace_entry, usage_entry
from .subgraphs import billing, escalation, technical


def triage(state: SharedState, config: RunnableConfig) -> dict[str, Any]:
    """Ask every supervisor question at once.

    `refund_eligible` is speculative here — it only matters if this turns out to
    be a billing ticket. Asking it in the same parallel request is cheaper than a
    second round trip on the branch that needs it.
    """
    engine = config["configurable"]["engine"]
    judgment = engine.ask(state["ticket"]["state"], TRIAGE)

    triage_result = {
        "department": judgment["department"]["value"],
        "department_confidence": judgment["department"]["confidence"],
        "department_probabilities": judgment["department"]["probabilities"],
        "priority": judgment["priority"]["value"],
        "priority_label": priority_label(judgment["priority"]["value"]),
        "priority_confidence": judgment["priority"]["confidence"],
        "needs_human": judgment["needs_human"]["p"],
        "refund_eligible": judgment["refund_eligible"]["p"],
        "angry_customer": judgment["angry_customer"]["p"],
    }
    return {
        "triage": triage_result,
        "trace": [trace_entry("supervisor.triage", judgment, **triage_result)],
        "usage": [usage_entry("supervisor.triage", judgment)],
    }


def gate(state: SharedState) -> dict[str, Any]:
    """Turn the triage probabilities into a branch, in ordinary code."""
    route, reason = route_from_triage(state["triage"])
    # Time to decision: the ticket now has somewhere to go. Everything after
    # this is carrying it out, so this is the number an SLA cares about.
    elapsed_ms = (time.perf_counter() - state["started_at"]) * 1000
    return {
        "route": route,
        "route_reason": reason,
        "time_to_route_ms": elapsed_ms,
        "trace": [
            trace_entry(
                "supervisor.gate",
                route=route,
                reason=reason,
                time_to_route_ms=round(elapsed_ms, 1),
            )
        ],
    }


def pick_branch(state: SharedState) -> str:
    return state["route"]


def finalize(state: SharedState) -> dict[str, Any]:
    """Attach the SLA and fold the per-node usage into one summary."""
    triage_result = state["triage"]
    resolution = dict(state.get("resolution") or {})
    resolution["priority"] = round(triage_result["priority"], 2)
    resolution["priority_label"] = triage_result["priority_label"]
    resolution["sla_hours"] = sla_hours(triage_result["priority"])
    resolution["needs_human"] = triage_result["needs_human"]

    return {
        "resolution": resolution,
        "trace": [trace_entry("supervisor.finalize", sla_hours=resolution["sla_hours"])],
    }


def build_graph() -> Any:
    """Compile the supervisor with its three subgraphs attached as nodes."""
    graph = StateGraph(SharedState)

    graph.add_node("triage", triage)
    graph.add_node("gate", gate)
    graph.add_node("billing", billing.build())
    graph.add_node("technical", technical.build())
    graph.add_node("escalation", escalation.build())
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "triage")
    graph.add_edge("triage", "gate")
    graph.add_conditional_edges(
        "gate", pick_branch, {name: name for name in DEPARTMENTS}
    )
    for name in DEPARTMENTS:
        graph.add_edge(name, "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


def run_ticket(graph: Any, ticket: Ticket, engine: DecisionEngine) -> dict[str, Any]:
    """Run one ticket end to end and return the final state.

    Adds `wall_ms`, measured around the whole invocation. Compared with the sum
    of the engine call latencies it separates what the judgment layer cost from
    what the graph itself cost.
    """
    started = time.perf_counter()
    initial: SharedState = {
        "ticket": {"id": ticket.id, "state": ticket.as_state()},
        "started_at": started,
        "trace": [],
        "usage": [],
    }
    final = graph.invoke(initial, config={"configurable": {"engine": engine}})
    final["wall_ms"] = (time.perf_counter() - started) * 1000
    return final
