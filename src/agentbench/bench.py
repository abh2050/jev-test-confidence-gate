"""Run the same graph over the same tickets with each engine, then compare.

The headline number is accuracy, but it is the least interesting one here. A
routing layer that is wrong 10% of the time and *knows which 10%* is worth more
than one that is wrong 5% of the time with uniform swagger, because the first can
hand its uncertain cases to a human and the second cannot. That is what the
calibration and abstention columns are for.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field
from typing import Any

from .data import Case, load_cases
from .engines import build_engine
from .graph import build_graph, run_ticket
from .graph.policy import NEEDS_HUMAN_THRESHOLD
from .pricing import price_for
from .types import GoldLabel, Ticket


@dataclass
class CaseResult:
    ticket_id: str
    gold: dict[str, Any]
    predicted_department: str
    department_confidence: float
    department_probabilities: dict[str, float]
    final_route: str
    route_reason: str
    priority: float
    priority_confidence: float
    needs_human: float
    resolution: dict[str, Any]
    # Sum of the engine call latencies: what the judgment layer cost.
    engine_ms: float
    # Wall clock around the whole graph invocation: time to a final answer.
    wall_ms: float
    # Wall clock up to the routing decision, which is what an SLA starts on.
    time_to_route_ms: float
    input_tokens: int
    output_tokens: int
    requests: int
    error: str | None = None

    @property
    def overhead_ms(self) -> float:
        """Everything that was not waiting on the engine."""
        return max(0.0, self.wall_ms - self.engine_ms)


@dataclass
class EngineReport:
    engine: str
    model: str
    results: list[CaseResult] = field(default_factory=list)

    # --- accuracy --------------------------------------------------------
    @property
    def scored(self) -> list[CaseResult]:
        return [r for r in self.results if r.error is None]

    @property
    def department_accuracy(self) -> float:
        rows = self.scored
        if not rows:
            return 0.0
        hits = sum(r.predicted_department == r.gold["department"] for r in rows)
        return hits / len(rows)

    @property
    def priority_mae(self) -> float:
        rows = self.scored
        if not rows:
            return 0.0
        return statistics.fmean(abs(r.priority - r.gold["priority"]) for r in rows)

    @property
    def needs_human_accuracy(self) -> float:
        rows = self.scored
        if not rows:
            return 0.0
        hits = sum(
            (r.needs_human >= NEEDS_HUMAN_THRESHOLD) == r.gold["needs_human"]
            for r in rows
        )
        return hits / len(rows)

    # --- calibration -----------------------------------------------------
    @property
    def calibration_error(self) -> float:
        """Expected calibration error on the department choice.

        Bin predictions by stated confidence and compare each bin's mean
        confidence with how often it was actually right. Zero means the stated
        numbers mean what they say. With ~24 tickets this is indicative only;
        it needs hundreds of cases to be stable.
        """
        rows = self.scored
        if not rows:
            return 0.0

        bins: dict[int, list[CaseResult]] = {}
        for r in rows:
            index = min(9, int(r.department_confidence * 10))
            bins.setdefault(index, []).append(r)

        total = 0.0
        for bucket in bins.values():
            mean_confidence = statistics.fmean(r.department_confidence for r in bucket)
            accuracy = statistics.fmean(
                float(r.predicted_department == r.gold["department"]) for r in bucket
            )
            total += len(bucket) * abs(mean_confidence - accuracy)
        return total / len(rows)

    @property
    def confidence_separation(self) -> float:
        """Mean confidence when right minus mean confidence when wrong.

        The single most useful number for a routing layer: if it is near zero,
        confidence carries no signal and a confidence gate cannot work.
        """
        rows = self.scored
        right = [r.department_confidence for r in rows if r.predicted_department == r.gold["department"]]
        wrong = [r.department_confidence for r in rows if r.predicted_department != r.gold["department"]]
        if not right or not wrong:
            return float("nan")
        return statistics.fmean(right) - statistics.fmean(wrong)

    @property
    def abstention_rate(self) -> float:
        """How often the confidence gate sent a ticket to a human."""
        rows = self.scored
        if not rows:
            return 0.0
        return sum("uncertain" in r.route_reason for r in rows) / len(rows)

    @property
    def caught_errors(self) -> float:
        """Of the tickets it got wrong, how many did the gate catch anyway?"""
        wrong = [r for r in self.scored if r.predicted_department != r.gold["department"]]
        if not wrong:
            return float("nan")
        return sum("uncertain" in r.route_reason for r in wrong) / len(wrong)

    # --- speed -----------------------------------------------------------
    def _percentile(self, values: list[float], fraction: float) -> float:
        ordered = sorted(values)
        if not ordered:
            return 0.0
        return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]

    @property
    def mean_time_to_route_ms(self) -> float:
        """Time to decision: how long until the ticket had somewhere to go."""
        rows = self.scored
        return statistics.fmean(r.time_to_route_ms for r in rows) if rows else 0.0

    @property
    def p95_time_to_route_ms(self) -> float:
        return self._percentile([r.time_to_route_ms for r in self.scored], 0.95)

    @property
    def mean_wall_ms(self) -> float:
        """End to end, including the subgraph's own engine call."""
        rows = self.scored
        return statistics.fmean(r.wall_ms for r in rows) if rows else 0.0

    @property
    def p50_wall_ms(self) -> float:
        return self._percentile([r.wall_ms for r in self.scored], 0.50)

    @property
    def p95_wall_ms(self) -> float:
        return self._percentile([r.wall_ms for r in self.scored], 0.95)

    @property
    def mean_engine_ms(self) -> float:
        rows = self.scored
        return statistics.fmean(r.engine_ms for r in rows) if rows else 0.0

    @property
    def mean_overhead_ms(self) -> float:
        """Wall clock that was not spent waiting on the engine."""
        rows = self.scored
        return statistics.fmean(r.overhead_ms for r in rows) if rows else 0.0

    # --- cost ------------------------------------------------------------

    @property
    def input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.scored)

    @property
    def output_tokens(self) -> int:
        """The column TypeSafe's parallel-sampling claim lives in.

        A System One model emits its whole answer at once, so this should stay
        tiny; an autoregressive engine has to write the JSON out token by token.
        """
        return sum(r.output_tokens for r in self.scored)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost_usd(self) -> float:
        """Cost at list price, or NaN when no price is on file for the model."""
        price = price_for(self.model)
        if price is None:
            return float("nan")
        return price.cost(self.input_tokens, self.output_tokens)

    @property
    def cost_per_1k_tickets_usd(self) -> float:
        rows = self.scored
        if not rows:
            return 0.0
        return self.cost_usd / len(rows) * 1000

    @property
    def mean_requests(self) -> float:
        rows = self.scored
        return statistics.fmean(r.requests for r in rows) if rows else 0.0

    def summary(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "model": self.model,
            "cases": len(self.scored),
            "errors": len(self.results) - len(self.scored),
            "department_accuracy": self.department_accuracy,
            "priority_mae": self.priority_mae,
            "needs_human_accuracy": self.needs_human_accuracy,
            "calibration_error": self.calibration_error,
            "confidence_separation": self.confidence_separation,
            "abstention_rate": self.abstention_rate,
            "caught_errors": self.caught_errors,
            "mean_time_to_route_ms": self.mean_time_to_route_ms,
            "p95_time_to_route_ms": self.p95_time_to_route_ms,
            "mean_wall_ms": self.mean_wall_ms,
            "p50_wall_ms": self.p50_wall_ms,
            "p95_wall_ms": self.p95_wall_ms,
            "mean_engine_ms": self.mean_engine_ms,
            "mean_overhead_ms": self.mean_overhead_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
            "cost_per_1k_tickets_usd": self.cost_per_1k_tickets_usd,
            "mean_requests": self.mean_requests,
        }


def _run_case(graph: Any, ticket: Ticket, gold: GoldLabel, engine: Any) -> CaseResult:
    gold_dict = asdict(gold)
    try:
        final = run_ticket(graph, ticket, engine)
    except Exception as exc:  # a failed engine call should not abort the sweep
        return CaseResult(
            ticket_id=ticket.id,
            gold=gold_dict,
            predicted_department="",
            department_confidence=0.0,
            department_probabilities={},
            final_route="",
            route_reason="",
            priority=0.0,
            priority_confidence=0.0,
            needs_human=0.0,
            resolution={},
            engine_ms=0.0,
            wall_ms=0.0,
            time_to_route_ms=0.0,
            input_tokens=0,
            output_tokens=0,
            requests=0,
            error=f"{type(exc).__name__}: {exc}",
        )

    triage = final["triage"]
    usage_rows = final.get("usage", [])
    return CaseResult(
        ticket_id=ticket.id,
        gold=gold_dict,
        predicted_department=triage["department"],
        department_confidence=triage["department_confidence"],
        department_probabilities=triage["department_probabilities"],
        final_route=final["route"],
        route_reason=final["route_reason"],
        priority=triage["priority"],
        priority_confidence=triage["priority_confidence"],
        needs_human=triage["needs_human"],
        resolution=final.get("resolution", {}),
        engine_ms=sum(u["latency_ms"] for u in usage_rows),
        wall_ms=final.get("wall_ms", 0.0),
        time_to_route_ms=final.get("time_to_route_ms", 0.0),
        input_tokens=sum(u["input_tokens"] for u in usage_rows),
        output_tokens=sum(u["output_tokens"] for u in usage_rows),
        requests=sum(u["requests"] for u in usage_rows),
    )


def run_engine(
    engine_name: str,
    cases: list[Case] | None = None,
    model: str | None = None,
    on_case: Any = None,
) -> EngineReport:
    """Run every case through one engine."""
    cases = cases if cases is not None else load_cases()
    engine = build_engine(engine_name, model=model)
    graph = build_graph()

    report = EngineReport(engine=engine_name, model=getattr(engine, "model", "?"))
    try:
        for ticket, gold in cases:
            result = _run_case(graph, ticket, gold, engine)
            report.results.append(result)
            if on_case:
                on_case(result)
    finally:
        close = getattr(engine, "close", None)
        if close:
            close()
    return report


def comparable(reports: list[EngineReport]) -> tuple[bool, str]:
    """Say whether these columns can be read against each other.

    An engine that failed on some tickets is scored only on the ones it
    completed, which silently changes the denominator — and failures are not
    random, since the hardest or latest tickets are the ones that time out or
    get throttled. Better to say so than to print a tidy table.
    """
    counts = {r.engine: len(r.scored) for r in reports}
    if len(set(counts.values())) <= 1:
        return True, ""

    best = max(counts.values())
    short = {name: n for name, n in counts.items() if n < best}
    detail = ", ".join(f"{name} scored {n}/{best}" for name, n in short.items())
    return False, detail


def common_subset(reports: list[EngineReport]) -> list[EngineReport]:
    """Restrict every report to the tickets all of them completed."""
    if not reports:
        return []
    shared = set.intersection(*({r.ticket_id for r in rep.scored} for rep in reports))
    return [
        EngineReport(
            engine=rep.engine,
            model=rep.model,
            results=[r for r in rep.scored if r.ticket_id in shared],
        )
        for rep in reports
    ]


def agreement(a: EngineReport, b: EngineReport) -> dict[str, float]:
    """How often the two engines picked the same department and route."""
    a_by_id = {r.ticket_id: r for r in a.scored}
    b_by_id = {r.ticket_id: r for r in b.scored}
    shared = sorted(set(a_by_id) & set(b_by_id))
    if not shared:
        return {"cases": 0, "department": 0.0, "route": 0.0}

    same_department = sum(
        a_by_id[i].predicted_department == b_by_id[i].predicted_department for i in shared
    )
    same_route = sum(a_by_id[i].final_route == b_by_id[i].final_route for i in shared)
    return {
        "cases": len(shared),
        "department": same_department / len(shared),
        "route": same_route / len(shared),
    }


def disagreements(a: EngineReport, b: EngineReport) -> list[dict[str, Any]]:
    """The tickets where the engines differ, with who was right."""
    a_by_id = {r.ticket_id: r for r in a.scored}
    b_by_id = {r.ticket_id: r for r in b.scored}
    rows = []
    for ticket_id in sorted(set(a_by_id) & set(b_by_id)):
        left, right = a_by_id[ticket_id], b_by_id[ticket_id]
        if left.predicted_department == right.predicted_department:
            continue
        gold = left.gold["department"]
        rows.append(
            {
                "ticket_id": ticket_id,
                "gold": gold,
                a.engine: left.predicted_department,
                f"{a.engine}_confidence": round(left.department_confidence, 2),
                b.engine: right.predicted_department,
                f"{b.engine}_confidence": round(right.department_confidence, 2),
                "winner": (
                    a.engine
                    if left.predicted_department == gold
                    else b.engine
                    if right.predicted_department == gold
                    else "neither"
                ),
            }
        )
    return rows
