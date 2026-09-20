"""A deterministic offline engine.

It answers from keyword heuristics, costs nothing, and needs no API key. Its
purpose is to exercise the graph and the harness — as a decision layer it is
deliberately crude, and its place in a benchmark run is as a floor that a real
engine should beat comfortably.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..types import Judgment, Usage
from .questions import QuestionSet, QuestionSpec

KEYWORDS: dict[str, tuple[str, ...]] = {
    "billing": ("charge", "charged", "invoice", "refund", "billed", "card", "price", "plan", "vat"),
    "technical": ("error", "crash", "broken", "slow", "bug", "500", "export", "load", "fails"),
    "escalation": ("legal", "cancel", "counsel", "gdpr", "compromised", "unacceptable", "competitor"),
}


def _text(state: dict[str, Any]) -> str:
    return json.dumps(state).lower()


def _weights(text: str) -> dict[str, float]:
    raw = {
        name: 1.0 + sum(text.count(word) for word in words)
        for name, words in KEYWORDS.items()
    }
    total = sum(raw.values())
    return {name: value / total for name, value in raw.items()}


def _jitter(text: str, spec_id: str) -> float:
    """Stable pseudo-random value in [0, 1) so runs are reproducible."""
    digest = hashlib.sha256(f"{spec_id}:{text}".encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _answer(spec: QuestionSpec, text: str) -> dict[str, Any]:
    if spec.kind == "noul":
        return {"p": round(_jitter(text, spec.id), 3)}

    if spec.kind == "choice":
        options = list(spec.criteria or [])
        if set(options) == set(KEYWORDS):
            probabilities = {k: round(v, 3) for k, v in _weights(text).items()}
        else:
            base = _jitter(text, spec.id)
            scores = [abs(((base * 7 + i) % 1.0)) for i in range(len(options))]
            total = sum(scores) or 1.0
            probabilities = {
                option: round(score / total, 3)
                for option, score in zip(options, scores)
            }
        best = max(probabilities, key=probabilities.__getitem__)
        return {
            "value": best,
            "confidence": probabilities[best],
            "probabilities": probabilities,
        }

    levels = list(spec.criteria or [])
    top = len(levels) - 1
    value = round(_jitter(text, spec.id) * top, 2)
    probabilities = {i: 0.0 for i in range(len(levels))}
    low, high = int(value), min(top, int(value) + 1)
    fraction = value - low
    probabilities[low] = round(1 - fraction, 3)
    probabilities[high] = round(fraction, 3) if high != low else probabilities[high]
    return {"value": value, "confidence": 0.5, "probabilities": probabilities}


class FakeEngine:
    """Offline stand-in with the same interface as the real engines."""

    name = "fake"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or "keyword-heuristic"

    def ask(self, state: dict[str, Any], questions: QuestionSet) -> Judgment:
        text = _text(state)
        values = {spec.id: _answer(spec, text) for spec in questions.questions}
        return Judgment(values=values, latency_ms=0.0, usage=Usage(0, 0, 1))

    def close(self) -> None:
        return None
