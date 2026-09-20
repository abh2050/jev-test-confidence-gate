"""State schemas for the parent graph and its subgraphs.

Subgraphs are attached as plain nodes, which works because they share these
keys with the parent. Each subgraph adds private keys of its own; those stay
inside the subgraph and never surface in the parent's state.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, NotRequired, TypedDict


class SharedState(TypedDict):
    """The keys the parent graph and every subgraph agree on."""

    ticket: dict[str, Any]
    triage: NotRequired[dict[str, Any]]
    route: NotRequired[str]
    route_reason: NotRequired[str]
    resolution: NotRequired[dict[str, Any]]
    # perf_counter() at the moment the ticket entered the graph, so nodes can
    # report elapsed time rather than only their own duration.
    started_at: float
    # Elapsed ms at the point the routing decision was made.
    time_to_route_ms: NotRequired[float]
    # Append-only so a subgraph's entries merge with the parent's instead of
    # overwriting them.
    trace: Annotated[list[dict[str, Any]], operator.add]
    usage: Annotated[list[dict[str, Any]], operator.add]


class SubgraphInput(TypedDict):
    """What a subgraph is given.

    Deliberately excludes `trace` and `usage`. If a subgraph inherited those
    lists it would re-emit them on the way out, and the parent's `operator.add`
    reducer would append the parent's own entries a second time. Starting each
    subgraph with empty accumulators means it returns only what it added.
    """

    ticket: dict[str, Any]
    triage: NotRequired[dict[str, Any]]
    route: NotRequired[str]
    route_reason: NotRequired[str]


class SubgraphOutput(TypedDict):
    """What a subgraph hands back to the parent."""

    resolution: NotRequired[dict[str, Any]]
    trace: Annotated[list[dict[str, Any]], operator.add]
    usage: Annotated[list[dict[str, Any]], operator.add]


class BillingState(SharedState):
    billing_judgment: NotRequired[dict[str, Any]]


class TechnicalState(SharedState):
    technical_judgment: NotRequired[dict[str, Any]]


class EscalationState(SharedState):
    escalation_judgment: NotRequired[dict[str, Any]]


def trace_entry(node: str, judgment: Any = None, **fields: Any) -> dict[str, Any]:
    """One row of the execution trace, used by the CLI and the benchmark."""
    entry: dict[str, Any] = {"node": node, **fields}
    if judgment is not None:
        entry["latency_ms"] = round(judgment.latency_ms, 1)
    return entry


def usage_entry(node: str, judgment: Any) -> dict[str, Any]:
    return {
        "node": node,
        "input_tokens": judgment.usage.input_tokens,
        "output_tokens": judgment.usage.output_tokens,
        "requests": judgment.usage.requests,
        "latency_ms": judgment.latency_ms,
    }
