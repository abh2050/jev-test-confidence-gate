"""Escalation subgraph: decide who takes the ticket over, and who gets warned.

This is also where the parent sends anything it could not route confidently, so
the tier judgment has to cope with tickets that are merely ambiguous rather than
genuinely severe.
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from ...engines import ESCALATION
from ..state import EscalationState, SubgraphInput, SubgraphOutput, trace_entry, usage_entry

# "Wavering" or worse on the churn rubric brings in a commercial owner.
CHURN_ALERT_SCORE = 2.0
LEGAL_THRESHOLD = 0.5


def assess(state: EscalationState, config: RunnableConfig) -> dict[str, Any]:
    engine = config["configurable"]["engine"]
    judgment = engine.ask(state["ticket"]["state"], ESCALATION)

    escalation_judgment = {
        "tier": judgment["tier"]["value"],
        "tier_confidence": judgment["tier"]["confidence"],
        "tier_probabilities": judgment["tier"]["probabilities"],
        "churn_risk": judgment["churn_risk"]["value"],
        "churn_confidence": judgment["churn_risk"]["confidence"],
        "legal_exposure": judgment["legal_exposure"]["p"],
    }
    return {
        "escalation_judgment": escalation_judgment,
        "trace": [trace_entry("escalation.assess", judgment, **escalation_judgment)],
        "usage": [usage_entry("escalation.assess", judgment)],
    }


def decide(state: EscalationState) -> dict[str, Any]:
    judgment = state["escalation_judgment"]
    legal = judgment["legal_exposure"]

    # Legal exposure overrides the tier choice: it is a separate condition, not
    # something a weighted score should be able to average away.
    tier = "legal_review" if legal >= LEGAL_THRESHOLD else judgment["tier"]

    resolution = {
        "department": "escalation",
        "assigned_to": tier,
        "notify_account_manager": judgment["churn_risk"] >= CHURN_ALERT_SCORE,
        "churn_risk": round(judgment["churn_risk"], 2),
        "legal_exposure": round(legal, 2),
        "confidence": judgment["tier_confidence"],
        "routed_here_because": state.get("route_reason", ""),
    }
    return {
        "resolution": resolution,
        "trace": [trace_entry("escalation.decide", **resolution)],
    }


def build() -> Any:
    graph = StateGraph(
        EscalationState, input_schema=SubgraphInput, output_schema=SubgraphOutput
    )
    graph.add_node("assess", assess)
    graph.add_node("decide", decide)
    graph.add_edge(START, "assess")
    graph.add_edge("assess", "decide")
    graph.add_edge("decide", END)
    return graph.compile()
