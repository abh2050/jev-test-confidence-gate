"""Shared plumbing for the prompt-and-parse engines.

OpenAI and Gemini both get the same system prompt, the same rendered rubrics and
the same JSON schema, built from the same QuestionSpecs that Jev compiles into
System One primitives. If these diverged, the benchmark would be measuring
prompt wording rather than the judgment layer.
"""

from __future__ import annotations

from typing import Any

from .questions import QuestionSet, QuestionSpec

SYSTEM_PROMPT = (
    "You are a decision layer inside a support-routing system. You answer a fixed "
    "set of independent judgment questions about one ticket and return nothing but "
    "the required JSON.\n\n"
    "Answer each question only from the state you are given. Treat the questions as "
    "independent: do not let your answer to one justify another.\n\n"
    "Probabilities must reflect genuine uncertainty. Use the full range — if two "
    "options are nearly equally supported, say so rather than committing to one. "
    "Probabilities within a single question must sum to 1."
)


def _probability_schema(keys: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {k: {"type": "number"} for k in keys},
        "required": keys,
        "additionalProperties": False,
    }


def _question_schema(spec: QuestionSpec) -> dict[str, Any]:
    if spec.kind == "noul":
        return {
            "type": "object",
            "description": spec.instructions,
            "properties": {
                "p": {
                    "type": "number",
                    "description": "Probability the answer is yes, from 0 to 1.",
                }
            },
            "required": ["p"],
            "additionalProperties": False,
        }

    if spec.kind == "choice":
        options = list(spec.criteria or [])
        return {
            "type": "object",
            "description": spec.instructions,
            "properties": {
                "value": {"type": "string", "enum": options},
                "confidence": {
                    "type": "number",
                    "description": "How certain you are of the selected option, 0 to 1.",
                },
                "probabilities": _probability_schema(options),
            },
            "required": ["value", "confidence", "probabilities"],
            "additionalProperties": False,
        }

    levels = list(spec.criteria or [])
    indices = [str(i) for i in range(len(levels))]
    return {
        "type": "object",
        "description": spec.instructions,
        "properties": {
            "value": {
                "type": "number",
                "description": (
                    "Probability-weighted position across the levels, from 0 to "
                    f"{len(levels) - 1}. It may fall between whole levels."
                ),
            },
            "confidence": {"type": "number"},
            "probabilities": _probability_schema(indices),
        },
        "required": ["value", "confidence", "probabilities"],
        "additionalProperties": False,
    }


def object_schema(questions: QuestionSet) -> dict[str, Any]:
    """The bare JSON schema for a question set's answers."""
    properties = {spec.id: _question_schema(spec) for spec in questions.questions}
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def openai_response_format(questions: QuestionSet) -> dict[str, Any]:
    """The schema wrapped the way OpenAI's strict json_schema mode wants it."""
    return {
        "name": f"{questions.name}_judgments",
        "strict": True,
        "schema": object_schema(questions),
    }


def render_questions(questions: QuestionSet) -> str:
    """Spell out each question's criteria, since a schema alone loses the rubric."""
    lines: list[str] = []
    for spec in questions.questions:
        lines.append(f"- `{spec.id}` ({spec.kind}): {spec.instructions}")
        if spec.kind == "noul" and isinstance(spec.criteria, dict):
            lines.append(f"    yes means: {spec.criteria.get('true')}")
            lines.append(f"    no means: {spec.criteria.get('false')}")
        elif spec.kind == "choice" and isinstance(spec.criteria, dict):
            for option, description in spec.criteria.items():
                lines.append(f"    {option}: {description}")
        elif spec.kind == "score" and isinstance(spec.criteria, list):
            for index, level in enumerate(spec.criteria):
                lines.append(f"    level {index}: {level}")
    return "\n".join(lines)


def user_message(state: dict[str, Any], questions: QuestionSet) -> str:
    import json

    return (
        "State:\n"
        f"{json.dumps(state, indent=2)}\n\n"
        "Answer each of these questions about the state above:\n"
        f"{render_questions(questions)}"
    )


def parse_answers(parsed: dict[str, Any], questions: QuestionSet) -> dict[str, Any]:
    """Normalize a model's JSON into the shape the graph consumes.

    Missing or malformed answers fall back to maximal uncertainty rather than
    raising, so one bad field does not throw away the rest of the request.
    """
    values: dict[str, Any] = {}
    for spec in questions.questions:
        answer = parsed.get(spec.id) or {}

        if spec.kind == "noul":
            values[spec.id] = {"p": _number(answer.get("p"), 0.5)}
        elif spec.kind == "choice":
            options = list(spec.criteria or [])
            value = answer.get("value")
            values[spec.id] = {
                "value": value if value in options else options[0],
                "confidence": _number(answer.get("confidence"), 0.0),
                "probabilities": {
                    k: _number(v, 0.0)
                    for k, v in (answer.get("probabilities") or {}).items()
                },
            }
        else:
            # Re-key level probabilities from strings to ints so every engine
            # hands the graph the same shape.
            probabilities: dict[int, float] = {}
            for k, v in (answer.get("probabilities") or {}).items():
                try:
                    probabilities[int(k)] = _number(v, 0.0)
                except (TypeError, ValueError):
                    continue
            values[spec.id] = {
                "value": _number(answer.get("value"), 0.0),
                "confidence": _number(answer.get("confidence"), 0.0),
                "probabilities": probabilities,
            }
    return values


def _number(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
