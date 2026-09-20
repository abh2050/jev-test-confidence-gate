"""Rate-limit retry, and refusing to compare columns of different sizes."""

from __future__ import annotations

import pytest

from agentbench.bench import EngineReport, common_subset, comparable
from agentbench.engines.retry import with_rate_limit_retry

from .test_metrics import result


class RateLimited(Exception):
    def __init__(self) -> None:
        super().__init__("429 RESOURCE_EXHAUSTED")
        self.code = 429


def test_retry_succeeds_after_transient_rate_limits():
    calls = {"n": 0}
    slept: list[float] = []

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RateLimited()
        return "ok"

    assert with_rate_limit_retry(flaky, sleep=slept.append) == "ok"
    assert calls["n"] == 3
    assert len(slept) == 2
    assert slept[1] > slept[0]  # backoff grows


def test_retry_gives_up_and_reraises():
    def always():
        raise RateLimited()

    with pytest.raises(RateLimited):
        with_rate_limit_retry(always, attempts=3, sleep=lambda _: None)


def test_non_rate_limit_errors_are_not_retried():
    calls = {"n": 0}

    def broken():
        calls["n"] += 1
        raise ValueError("bad schema")

    with pytest.raises(ValueError):
        with_rate_limit_retry(broken, sleep=lambda _: None)
    assert calls["n"] == 1


def test_rate_limit_detected_from_message_without_a_code():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("ClientError: 429 quota exceeded")
        return "ok"

    assert with_rate_limit_retry(flaky, sleep=lambda _: None) == "ok"


def report(engine: str, *ticket_ids: str, failed: tuple[str, ...] = ()) -> EngineReport:
    results = []
    for ticket_id in ticket_ids:
        row = result(ticket_id, "billing", "billing", 0.9)
        if ticket_id in failed:
            row.error = "ClientError: 429"
        results.append(row)
    return EngineReport(engine=engine, model="m", results=results)


def test_equal_case_counts_are_comparable():
    a = report("jev", "T-1", "T-2")
    b = report("openai", "T-1", "T-2")
    assert comparable([a, b])[0] is True


def test_unequal_case_counts_are_flagged():
    a = report("jev", "T-1", "T-2", "T-3")
    b = report("gemini", "T-1", "T-2", "T-3", failed=("T-2", "T-3"))

    ok, detail = comparable([a, b])
    assert ok is False
    assert "gemini scored 1/3" in detail


def test_common_subset_restricts_every_engine_to_shared_tickets():
    a = report("jev", "T-1", "T-2", "T-3")
    b = report("gemini", "T-1", "T-2", "T-3", failed=("T-3",))

    shared = common_subset([a, b])
    assert [len(r.scored) for r in shared] == [2, 2]
    assert {r.ticket_id for r in shared[0].scored} == {"T-1", "T-2"}
    assert comparable(shared)[0] is True


def test_common_subset_can_be_empty():
    a = report("jev", "T-1")
    b = report("gemini", "T-2")
    assert [len(r.scored) for r in common_subset([a, b])] == [0, 0]
