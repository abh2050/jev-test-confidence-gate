"""Billing subgraph: judge the charge, then let code decide about the money."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from ...engines import BILLING
from ..policy import refund_amount, refund_requires_approval
from ..state import BillingState, SubgraphInput, SubgraphOutput, trace_entry, usage_entry


def assess(state: BillingState, config: RunnableConfig) -> dict[str, Any]:
    engine = config["configurable"]["engine"]
    judgment = engine.ask(state["ticket"]["state"], BILLING)

    billing_judgment = {
        "action": judgment["action"]["value"],
        "action_confidence": judgment["action"]["confidence"],
        "action_probabilities": judgment["action"]["probabilities"],
        "policy_exception": judgment["policy_exception"]["p"],
    }
    return {
        "billing_judgment": billing_judgment,
        "trace": [trace_entry("billing.assess", judgment, **billing_judgment)],
        "usage": [usage_entry("billing.assess", judgment)],
    }


def decide(state: BillingState) -> dict[str, Any]:
    judgment = state["billing_judgment"]
    action = judgment["action"]
    order_total = state["ticket"]["state"]["account"]["disputed_amount_usd"]

    amount = refund_amount(action, order_total)
    needs_approval, approval_reason = refund_requires_approval(
        action, amount, judgment["policy_exception"]
    )

    resolution = {
        "department": "billing",
        "action": action,
        "refund_usd": amount,
        "requires_approval": needs_approval,
        "approval_reason": approval_reason,
        "confidence": judgment["action_confidence"],
    }
    return {
        "resolution": resolution,
        "trace": [trace_entry("billing.decide", **resolution)],
    }


def build() -> Any:
    graph = StateGraph(
        BillingState, input_schema=SubgraphInput, output_schema=SubgraphOutput
    )
    graph.add_node("assess", assess)
    graph.add_node("decide", decide)
    graph.add_edge(START, "assess")
    graph.add_edge("assess", "decide")
    graph.add_edge("decide", END)
    return graph.compile()
