"""OpenAI structured-output engine.

The same QuestionSet is asked in a single chat completion under a strict JSON
schema, so the request count matches Jev's. The model is asked for verbalized
probabilities alongside each answer; comparing those against Jev's trained
probabilities is the point of the calibration report.
"""

from __future__ import annotations

import json
import time
from typing import Any

from ..config import load_env, openai_model, require
from ..types import Judgment, Usage
from .questions import QuestionSet
from .structured import (
    SYSTEM_PROMPT,
    openai_response_format,
    parse_answers,
    user_message,
)


class OpenAIEngine:
    """Answers question sets with an OpenAI model in strict JSON mode."""

    name = "openai"

    def __init__(self, model: str | None = None) -> None:
        load_env()
        require(
            "OPENAI_API_KEY",
            "Put your OpenAI key in .env as OPENAI_API_KEY=...",
        )
        from openai import OpenAI

        self.model = model or openai_model()
        self._client = OpenAI()

    def ask(self, state: dict[str, Any], questions: QuestionSet) -> Judgment:
        started = time.perf_counter()
        completion = self._client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message(state, questions)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": openai_response_format(questions),
            },
        )
        latency_ms = (time.perf_counter() - started) * 1000

        parsed = json.loads(completion.choices[0].message.content or "{}")

        usage_obj = completion.usage
        usage = Usage(
            input_tokens=getattr(usage_obj, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage_obj, "completion_tokens", 0) or 0,
            requests=1,
        )
        return Judgment(
            values=parse_answers(parsed, questions),
            latency_ms=latency_ms,
            usage=usage,
        )

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close:
            close()
