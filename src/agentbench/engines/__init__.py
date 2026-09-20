"""Swappable judgment engines."""

from __future__ import annotations

from .base import DecisionEngine
from .questions import (
    BILLING,
    ESCALATION,
    QUESTION_SETS,
    TECHNICAL,
    TRIAGE,
    QuestionSet,
    QuestionSpec,
)

ENGINE_NAMES = ("jev", "openai", "fake")
# `fake` is opt-in: it is a harness fixture, not a contender.
DEFAULT_BENCH_ENGINES = ("jev", "openai")


def build_engine(name: str, model: str | None = None) -> DecisionEngine:
    """Construct an engine by name, importing its SDK only when asked for."""
    if name == "fake":
        from .fake import FakeEngine

        return FakeEngine(model=model)
    if name == "jev":
        from .jev import JevEngine

        return JevEngine(model=model)
    if name == "openai":
        from .openai_engine import OpenAIEngine

        return OpenAIEngine(model=model)
    raise ValueError(f"unknown engine {name!r}; expected one of {ENGINE_NAMES}")


__all__ = [
    "BILLING",
    "DEFAULT_BENCH_ENGINES",
    "ENGINE_NAMES",
    "ESCALATION",
    "QUESTION_SETS",
    "TECHNICAL",
    "TRIAGE",
    "DecisionEngine",
    "QuestionSet",
    "QuestionSpec",
    "build_engine",
]
