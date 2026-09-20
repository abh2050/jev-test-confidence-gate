"""TypeSafe System One engine.

Every QuestionSet becomes one `system_one` request. The questions inside a set
are independent judgments over the same state, so they run in parallel and
cannot see one another's answers — which is exactly what the graph wants.
"""

from __future__ import annotations

import time
from typing import Any

from ..config import load_env, require, typesafe_model
from ..types import Judgment, Usage
from .questions import QuestionSet, QuestionSpec


def _build_question(spec: QuestionSpec) -> Any:
    from typesafe_sdk import Choice, Noul, Score

    if spec.kind == "noul":
        return Noul(instructions=spec.instructions, criteria=spec.criteria)
    if spec.kind == "choice":
        return Choice(instructions=spec.instructions, criteria=spec.criteria)
    if spec.kind == "score":
        return Score(instructions=spec.instructions, criteria=list(spec.criteria or []))
    raise ValueError(f"unknown question kind: {spec.kind}")


class JevEngine:
    """Answers question sets with TypeSafe's System One models."""

    name = "jev"

    def __init__(self, model: str | None = None) -> None:
        load_env()
        require(
            "TYPESAFE_API_KEY",
            "Put your TypeSafe key in .env as TYPESAFE_API_KEY=...",
        )
        from typesafe_sdk import TypeSafeClient

        self.model = model or typesafe_model()
        self._client = TypeSafeClient(model=self.model)

    def ask(self, state: dict[str, Any], questions: QuestionSet) -> Judgment:
        payload = {spec.id: _build_question(spec) for spec in questions.questions}

        started = time.perf_counter()
        result = self._client.system_one(state, payload)
        latency_ms = (time.perf_counter() - started) * 1000

        values: dict[str, Any] = {}
        for spec in questions.questions:
            if spec.kind == "noul":
                values[spec.id] = {"p": float(result.nouls[spec.id].noul)}
            elif spec.kind == "choice":
                answer = result.choices[spec.id]
                values[spec.id] = {
                    "value": answer.choice,
                    "confidence": float(answer.confidence),
                    "probabilities": {
                        k: float(v) for k, v in answer.probabilities.items()
                    },
                }
            else:
                answer = result.scores[spec.id]
                # Score levels are 0-indexed and probabilities are keyed by the
                # level index as a string; `score` is their weighted average and
                # is deliberately allowed to sit between levels.
                values[spec.id] = {
                    "value": float(answer.score),
                    "confidence": float(answer.confidence),
                    "probabilities": {
                        int(k): float(v) for k, v in answer.probabilities.items()
                    },
                }

        usage = Usage(
            input_tokens=result.usage.input_tokens or 0,
            output_tokens=result.usage.output_tokens or 0,
            requests=1,
        )
        return Judgment(values=values, latency_ms=latency_ms, usage=usage)

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close:
            close()
