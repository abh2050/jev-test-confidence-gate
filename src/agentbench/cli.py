"""Command line: run one ticket, or benchmark the engines against each other."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from .bench import (
    EngineReport,
    agreement,
    common_subset,
    comparable,
    disagreements,
    run_engine,
)
from .config import load_env
from .data import by_id, load_cases
from .engines import DEFAULT_BENCH_ENGINES, ENGINE_NAMES, build_engine
from .graph import build_graph, run_ticket

console = Console()


def _fmt(value: Any, digits: int = 3) -> str:
    if isinstance(value, float):
        if value != value:  # NaN
            return "–"
        return f"{value:.{digits}f}"
    return str(value)


def cmd_run(args: argparse.Namespace) -> int:
    """Run one ticket through the graph and print the trace."""
    ticket, gold = by_id(args.ticket)
    engine = build_engine(args.engine, model=args.model)
    graph = build_graph()

    final = run_ticket(graph, ticket, engine)

    console.print(f"\n[bold]{ticket.id}[/bold]  {ticket.subject}")
    console.print(f"[dim]{ticket.body}[/dim]\n")

    for entry in final["trace"]:
        node = entry.pop("node")
        latency = entry.pop("latency_ms", None)
        suffix = f"  [dim]{latency}ms[/dim]" if latency else ""
        console.print(f"[cyan]{node}[/cyan]{suffix}")
        for key, value in entry.items():
            console.print(f"    {key}: {_fmt(value)}")

    engine_ms = sum(u["latency_ms"] for u in final.get("usage", []))
    wall_ms = final.get("wall_ms", 0.0)
    console.print(
        f"\n[bold]timing[/bold]: decision in {final.get('time_to_route_ms', 0.0):.0f}ms, "
        f"end to end {wall_ms:.0f}ms "
        f"({engine_ms:.0f}ms engine + {max(0.0, wall_ms - engine_ms):.0f}ms graph)"
    )
    console.print(f"[bold]resolution[/bold]: {json.dumps(final['resolution'], indent=2)}")
    console.print(
        f"[bold]gold[/bold]: department={gold.department} "
        f"priority={gold.priority} needs_human={gold.needs_human}"
    )
    return 0


def _summary_table(reports: list[EngineReport]) -> Table:
    table = Table(title="Engine comparison", header_style="bold")
    table.add_column("metric")
    for report in reports:
        table.add_column(f"{report.engine}\n[dim]{report.model}[/dim]", justify="right")

    rows: list[tuple[str, str, int]] = [
        ("cases", "cases", 0),
        ("errors", "errors", 0),
        ("department accuracy ↑", "department_accuracy", 3),
        ("priority MAE ↓", "priority_mae", 3),
        ("needs_human accuracy ↑", "needs_human_accuracy", 3),
        ("calibration error ↓", "calibration_error", 3),
        ("confidence separation ↑", "confidence_separation", 3),
        ("abstention rate", "abstention_rate", 3),
        ("errors caught by gate ↑", "caught_errors", 3),
        ("time to decision ms ↓", "mean_time_to_route_ms", 1),
        ("  p95 ↓", "p95_time_to_route_ms", 1),
        ("end-to-end ms ↓", "mean_wall_ms", 1),
        ("  p50 ↓", "p50_wall_ms", 1),
        ("  p95 ↓", "p95_wall_ms", 1),
        ("  of which engine ↓", "mean_engine_ms", 1),
        ("  of which graph ↓", "mean_overhead_ms", 1),
        ("input tokens ↓", "input_tokens", 0),
        ("output tokens ↓", "output_tokens", 0),
        ("requests per ticket ↓", "mean_requests", 2),
        ("cost, 24 tickets ↓", "cost_usd", 5),
        ("$ / 1k tickets ↓", "cost_per_1k_tickets_usd", 3),
    ]

    summaries = [r.summary() for r in reports]
    for label, key, digits in rows:
        table.add_row(label, *[_fmt(s[key], digits) for s in summaries])
    return table


def cmd_bench(args: argparse.Namespace) -> int:
    cases = load_cases(limit=args.limit)
    engines = args.engines or list(DEFAULT_BENCH_ENGINES)
    overrides = {"jev": args.jev_model, "openai": args.openai_model}

    reports: list[EngineReport] = []
    for name in engines:
        console.print(f"[bold]running {name}[/bold] over {len(cases)} tickets…")

        def progress(result: Any) -> None:
            mark = "[green]✓[/green]" if result.error is None else "[red]✗[/red]"
            console.print(f"  {mark} {result.ticket_id}", end="  ")
            sys.stdout.flush()

        try:
            report = run_engine(
                name, cases=cases, model=overrides.get(name), on_case=progress
            )
        except RuntimeError as exc:
            console.print(f"\n[yellow]skipping {name}: {exc}[/yellow]\n")
            continue
        console.print()
        reports.append(report)

    if not reports:
        console.print("[red]no engine could run; check your API keys in .env[/red]")
        return 1

    console.print()
    console.print(_summary_table(reports))

    ok, detail = comparable(reports)
    if not ok:
        console.print(
            f"\n[yellow]⚠ columns are not comparable: {detail}. "
            "Failed tickets are excluded, which changes the denominator — and "
            "failures are not random.[/yellow]"
        )
        shared = common_subset(reports)
        if shared and len(shared[0].scored):
            console.print(
                f"[dim]same {len(shared[0].scored)} tickets, all engines:[/dim]"
            )
            console.print(_summary_table(shared))
            reports = shared
        else:
            console.print("[yellow]no ticket was completed by every engine.[/yellow]")

    if len(reports) == 2:
        stats = agreement(reports[0], reports[1])
        console.print(
            f"\n[bold]agreement[/bold] over {stats['cases']} tickets: "
            f"department {stats['department']:.2f}, final route {stats['route']:.2f}"
        )

        rows = disagreements(reports[0], reports[1])
        if rows:
            table = Table(title="Where they disagree", header_style="bold")
            for column in rows[0]:
                table.add_column(column)
            for row in rows:
                table.add_row(*[str(v) for v in row.values()])
            console.print(table)

    if args.out:
        payload = {
            "summaries": [r.summary() for r in reports],
            "results": {r.engine: [asdict(c) for c in r.results] for r in reports},
        }
        if len(reports) == 2:
            payload["agreement"] = agreement(reports[0], reports[1])
            payload["disagreements"] = disagreements(reports[0], reports[1])
        Path(args.out).write_text(json.dumps(payload, indent=2))
        console.print(f"\n[dim]wrote {args.out}[/dim]")

    return 0


def cmd_graph(args: argparse.Namespace) -> int:
    """Print the compiled topology, subgraphs expanded."""
    drawable = build_graph().get_graph(xray=1)
    if args.ascii:
        # Needs grandalf, which is not a dependency; say so rather than trace.
        try:
            console.print(drawable.draw_ascii())
        except ImportError:
            console.print("[yellow]ascii layout needs grandalf: uv add grandalf[/yellow]")
            return 1
    else:
        print(drawable.draw_mermaid())
    return 0


def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = argparse.ArgumentParser(prog="agentbench", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one ticket and show the trace")
    run.add_argument("ticket", help="ticket id, e.g. T-013")
    run.add_argument("--engine", default="jev", choices=list(ENGINE_NAMES))
    run.add_argument("--model", default=None)
    run.set_defaults(func=cmd_run)

    bench = sub.add_parser("bench", help="compare engines over the labeled set")
    bench.add_argument(
        "--engines", nargs="*", choices=list(ENGINE_NAMES), default=None
    )
    bench.add_argument("--limit", type=int, default=None)
    bench.add_argument("--jev-model", default=None, help="e.g. jev-latest")
    bench.add_argument("--openai-model", default=None, help="e.g. gpt-4o-mini")
    bench.add_argument("--out", default=None, help="write full results to this JSON file")
    bench.set_defaults(func=cmd_bench)

    graph = sub.add_parser("graph", help="print the graph topology")
    graph.add_argument("--ascii", action="store_true", help="ascii layout (needs grandalf)")
    graph.set_defaults(func=cmd_graph)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
