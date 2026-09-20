"""Technical subgraph: judge the report, then let code decide who gets woken up."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from ...engines import TECHNICAL
from ..state import TechnicalState, SubgraphInput, SubgraphOutput, trace_entry, usage_entry

# An unusable product or any sign of data loss pages the on-call engineer.
UNUSABLE_SEVERITY = 2.5
DATA_LOSS_THRESHOLD = 0.5


def assess(state: TechnicalState, config: RunnableConfig) -> dict[str, Any]:
    engine = config["configurable"]["engine"]
    judgment = engine.ask(state["ticket"]["state"], TECHNICAL)

    technical_judgment = {
        "action": judgment["action"]["value"],
        "action_confidence": judgment["action"]["confidence"],
        "action_probabilities": judgment["action"]["probabilities"],
        "severity": judgment["severity"]["value"],
        "severity_confidence": judgment["severity"]["confidence"],
        "data_loss_risk": judgment["data_loss_risk"]["p"],
    }
    return {
        "technical_judgment": technical_judgment,
        "trace": [trace_entry("technical.assess", judgment, **technical_judgment)],
        "usage": [usage_entry("technical.assess", judgment)],
    }


def decide(state: TechnicalState) -> dict[str, Any]:
    judgment = state["technical_judgment"]
    severity = judgment["severity"]
    data_loss = judgment["data_loss_risk"]

    page_oncall = (
        severity >= UNUSABLE_SEVERITY
        or data_loss >= DATA_LOSS_THRESHOLD
        or judgment["action"] == "platform_outage"
    )

    resolution = {
        "department": "technical",
        "action": judgment["action"],
        "severity": round(severity, 2),
        "page_oncall": page_oncall,
        "data_loss_risk": round(data_loss, 2),
        "confidence": judgment["action_confidence"],
    }
    return {
        "resolution": resolution,
        "trace": [trace_entry("technical.decide", **resolution)],
    }


def build() -> Any:
    graph = StateGraph(
        TechnicalState, input_schema=SubgraphInput, output_schema=SubgraphOutput
    )
    graph.add_node("assess", assess)
    graph.add_node("decide", decide)
    graph.add_edge(START, "assess")
    graph.add_edge("assess", "decide")
    graph.add_edge("decide", END)
    return graph.compile()
