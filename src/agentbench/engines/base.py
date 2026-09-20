"""The seam the benchmark swaps.

An engine answers a QuestionSet over a state object. It returns probabilities
and typed values only: it never decides what the application does. Policy lives
in the graph nodes so both engines are held to the same downstream rules.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..types import Judgment
from .questions import QuestionSet


@runtime_checkable
class DecisionEngine(Protocol):
    name: str

    def ask(self, state: dict[str, Any], questions: QuestionSet) -> Judgment:
        """Answer every question in `questions` over `state` in one request."""
        ...


def normalized_answer(
    values: dict[str, Any], qid: str, fallback: Any
) -> Any:
    """Read an answer, falling back when an engine omitted or malformed it."""
    value = values.get(qid)
    return fallback if value is None else value
