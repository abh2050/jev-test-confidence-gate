"""Shared fixtures: a scripted engine so graph tests never touch the network."""

from __future__ import annotations

from typing import Any

import pytest

from agentbench.engines.questions import QuestionSet
from agentbench.types import Judgment, Usage


def choice(value: str, confidence: float, probabilities: dict[str, float]) -> dict[str, Any]:
    return {"value": value, "confidence": confidence, "probabilities": probabilities}


def score(value: float, confidence: float = 0.8) -> dict[str, Any]:
    return {"value": value, "confidence": confidence, "probabilities": {}}


def noul(p: float) -> dict[str, Any]:
    return {"p": p}


class ScriptedEngine:
    """Returns fixed answers per question set, and records what it was asked."""

    name = "scripted"
    model = "scripted"

    def __init__(self, script: dict[str, dict[str, Any]]) -> None:
        self.script = script
        self.asked: list[str] = []

    def ask(self, state: dict[str, Any], questions: QuestionSet) -> Judgment:
        self.asked.append(questions.name)
        return Judgment(
            values=self.script[questions.name],
            latency_ms=10.0,
            usage=Usage(input_tokens=100, output_tokens=20, requests=1),
        )

    def close(self) -> None:
        return None


BASE_SCRIPT: dict[str, dict[str, Any]] = {
    "triage": {
        "department": choice(
            "billing", 0.88, {"billing": 0.88, "technical": 0.08, "escalation": 0.04}
        ),
        "priority": score(2.1),
        "needs_human": noul(0.8),
        "refund_eligible": noul(0.9),
        "angry_customer": noul(0.3),
    },
    "billing": {
        "action": choice(
            "full_refund",
            0.8,
            {"full_refund": 0.8, "partial_credit": 0.1, "explain_charge": 0.05, "request_info": 0.05},
        ),
        "policy_exception": noul(0.2),
    },
    "technical": {
        "action": choice(
            "known_issue",
            0.7,
            {"known_issue": 0.7, "config_fix": 0.1, "needs_repro": 0.1, "platform_outage": 0.1},
        ),
        "severity": score(2.8),
        "data_loss_risk": noul(0.05),
    },
    "escalation": {
        "tier": choice(
            "tier_two",
            0.6,
            {"tier_two": 0.6, "tier_three": 0.2, "account_manager": 0.1, "legal_review": 0.1},
        ),
        "churn_risk": score(2.4),
        "legal_exposure": noul(0.1),
    },
}


@pytest.fixture
def script() -> dict[str, dict[str, Any]]:
    """A fresh deep-ish copy so a test can mutate one answer safely."""
    return {name: dict(answers) for name, answers in BASE_SCRIPT.items()}


@pytest.fixture
def engine(script) -> ScriptedEngine:
    return ScriptedEngine(script)
