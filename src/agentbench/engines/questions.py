"""The judgment questions, defined once, engine-neutral.

Both engines compile these same specs: Jev into System One primitives, OpenAI
into a strict JSON schema plus a prompt. Nothing about the wording differs
between engines, so the benchmark measures the judgment layer and not the
prompt engineering around it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ..types import (
    BILLING_ACTIONS,
    DEPARTMENTS,
    ESCALATION_TIERS,
    PRIORITY_LEVELS,
    TECHNICAL_ACTIONS,
)

QuestionKind = Literal["noul", "choice", "score"]


@dataclass(frozen=True)
class QuestionSpec:
    """One narrow, coherent judgment.

    `instructions` carries the full meaning; the id is for code only and is
    never shown to a model, per the TypeSafe question guidance.
    """

    id: str
    kind: QuestionKind
    instructions: str
    criteria: dict[str, Any] | list[str] | None = None


@dataclass(frozen=True)
class QuestionSet:
    """A group of questions asked together over one shared state."""

    name: str
    questions: tuple[QuestionSpec, ...]

    def by_id(self) -> dict[str, QuestionSpec]:
        return {q.id: q for q in self.questions}


# --- Supervisor -------------------------------------------------------------
# Independent judgments over the same state, so they go in a single request.
# `refund_eligible` is deliberately speculative: it only matters on the billing
# branch, but asking it up front costs one parallel question instead of a whole
# extra round trip. Code consumes it only where it applies.

TRIAGE = QuestionSet(
    name="triage",
    questions=(
        QuestionSpec(
            id="department",
            kind="choice",
            instructions=(
                "Which support team should own this ticket? Judge by what the "
                "customer actually needs resolved, not by which words appear."
            ),
            criteria={
                "billing": (
                    "Charges, invoices, refunds, plan pricing, payment methods, "
                    "or subscription changes."
                ),
                "technical": (
                    "The product is broken, erroring, slow, or behaving unexpectedly, "
                    "and a fix or workaround is what the customer needs."
                ),
                "escalation": (
                    "The ticket needs authority this queue does not have: threats of "
                    "legal action or churn, regulatory or privacy demands, executive "
                    "contacts, or a repeatedly failed prior resolution."
                ),
            },
        ),
        QuestionSpec(
            id="priority",
            kind="score",
            instructions=(
                "How urgently does a human need to act on this ticket, considering "
                "both the customer's situation and the business exposure?"
            ),
            criteria=[
                "Routine. Nothing is blocked and no deadline is near; answering "
                "within a few days costs nothing.",
                "Normal. The customer is inconvenienced or waiting on an answer, "
                "but has a workaround or is not blocked.",
                "Elevated. The customer is blocked from real work, or money is in "
                "dispute, or a second contact about the same unresolved problem.",
                "Critical. Active revenue loss, a broken production system, a legal "
                "or regulatory deadline, or a customer stating they are leaving now.",
            ],
        ),
        QuestionSpec(
            id="needs_human",
            kind="noul",
            instructions=(
                "Does resolving this ticket require a human agent, rather than an "
                "automated reply or self-service answer?"
            ),
            criteria={
                "true": (
                    "It needs judgment, an exception to policy, an apology with "
                    "authority behind it, or access to systems automation lacks."
                ),
                "false": (
                    "A documented answer, a status lookup, or a standard automated "
                    "action fully resolves it."
                ),
            },
        ),
        QuestionSpec(
            id="refund_eligible",
            kind="noul",
            instructions=(
                "Assuming this ticket is a billing matter, does the customer's "
                "account describe a charge that should be given back to them?"
            ),
            criteria={
                "true": "The customer was charged for something they did not receive or agree to.",
                "false": "The charge matches what the customer bought and used.",
            },
        ),
        QuestionSpec(
            id="angry_customer",
            kind="noul",
            instructions=(
                "Is the customer expressing anger or serious frustration, as opposed "
                "to stating a problem neutrally?"
            ),
        ),
    ),
)


# --- Billing subgraph -------------------------------------------------------

BILLING = QuestionSet(
    name="billing",
    questions=(
        QuestionSpec(
            id="action",
            kind="choice",
            instructions="What should the billing agent do about this charge?",
            criteria={
                "full_refund": "Return the entire disputed amount.",
                "partial_credit": (
                    "Return part of the amount or apply account credit, because the "
                    "customer received some of the value."
                ),
                "explain_charge": (
                    "The charge is correct; the customer needs it explained, not reversed."
                ),
                "request_info": (
                    "There is not enough in the ticket to decide; a specific missing "
                    "detail must be asked for first."
                ),
            },
        ),
        QuestionSpec(
            id="policy_exception",
            kind="noul",
            instructions=(
                "Would granting what the customer is asking for require an exception "
                "to standard refund policy, rather than falling within it?"
            ),
        ),
    ),
)


# --- Technical subgraph -----------------------------------------------------

TECHNICAL = QuestionSet(
    name="technical",
    questions=(
        QuestionSpec(
            id="action",
            kind="choice",
            instructions="What is the right first technical response to this report?",
            criteria={
                "known_issue": "This matches a defect the team already tracks; the customer needs status and a workaround.",
                "config_fix": "The product is working correctly and the customer's own settings or usage need changing.",
                "needs_repro": "The report is too vague to act on; specific reproduction details must be gathered.",
                "platform_outage": "This looks like a service-wide failure affecting many customers at once.",
            },
        ),
        QuestionSpec(
            id="severity",
            kind="score",
            instructions="How much of the customer's use of the product is impaired right now?",
            criteria=[
                "Cosmetic. Something looks wrong but everything works.",
                "Degraded. A feature is slower or clumsier but still usable.",
                "Feature blocked. One important workflow cannot be completed.",
                "Unusable. The customer cannot do their core work in the product at all.",
            ],
        ),
        QuestionSpec(
            id="data_loss_risk",
            kind="noul",
            instructions="Does this report describe customer data being lost, corrupted, or exposed?",
        ),
    ),
)


# --- Escalation subgraph ----------------------------------------------------

ESCALATION = QuestionSet(
    name="escalation",
    questions=(
        QuestionSpec(
            id="tier",
            kind="choice",
            instructions="Who should this ticket be handed to?",
            criteria={
                "tier_two": "An experienced support agent with broader tooling can resolve it.",
                "tier_three": "It needs an engineer who can inspect the system directly.",
                "account_manager": "The relationship itself is at risk and needs a commercial owner.",
                "legal_review": "It involves legal threats, regulatory obligations, or privacy demands.",
            },
        ),
        QuestionSpec(
            id="churn_risk",
            kind="score",
            instructions="How likely is this customer to stop paying if this ticket goes badly?",
            criteria=[
                "Anchored. They show no sign of leaving.",
                "Watchful. They are unhappy but still invested in making it work.",
                "Wavering. They mention comparing alternatives or reconsidering.",
                "Departing. They state they are cancelling or have already begun to.",
            ],
        ),
        QuestionSpec(
            id="legal_exposure",
            kind="noul",
            instructions=(
                "Does this ticket create legal or regulatory exposure that a lawyer "
                "should see, rather than ordinary dissatisfaction?"
            ),
        ),
    ),
)

QUESTION_SETS: dict[str, QuestionSet] = {
    qs.name: qs for qs in (TRIAGE, BILLING, TECHNICAL, ESCALATION)
}

# Sanity: the criteria above must stay aligned with the literal types in types.py.
assert list(TRIAGE.by_id()["department"].criteria) == list(DEPARTMENTS)
assert len(TRIAGE.by_id()["priority"].criteria) == len(PRIORITY_LEVELS)
assert list(BILLING.by_id()["action"].criteria) == list(BILLING_ACTIONS)
assert list(TECHNICAL.by_id()["action"].criteria) == list(TECHNICAL_ACTIONS)
assert list(ESCALATION.by_id()["tier"].criteria) == list(ESCALATION_TIERS)
