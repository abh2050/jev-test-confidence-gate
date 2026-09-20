"""Domain and judgment types shared by every engine and every subgraph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Department = Literal["billing", "technical", "escalation"]
DEPARTMENTS: tuple[Department, ...] = ("billing", "technical", "escalation")

BillingAction = Literal["full_refund", "partial_credit", "explain_charge", "request_info"]
BILLING_ACTIONS: tuple[BillingAction, ...] = (
    "full_refund",
    "partial_credit",
    "explain_charge",
    "request_info",
)

TechnicalAction = Literal["known_issue", "config_fix", "needs_repro", "platform_outage"]
TECHNICAL_ACTIONS: tuple[TechnicalAction, ...] = (
    "known_issue",
    "config_fix",
    "needs_repro",
    "platform_outage",
)

EscalationTier = Literal["tier_two", "tier_three", "account_manager", "legal_review"]
ESCALATION_TIERS: tuple[EscalationTier, ...] = (
    "tier_two",
    "tier_three",
    "account_manager",
    "legal_review",
)

PRIORITY_LEVELS: tuple[str, ...] = ("routine", "normal", "elevated", "critical")


@dataclass(frozen=True)
class Ticket:
    """One inbound support ticket plus the account facts code already knows."""

    id: str
    subject: str
    body: str
    customer_tier: str
    account_age_days: int
    prior_tickets_30d: int
    order_total_usd: float

    def as_state(self) -> dict[str, Any]:
        """The JSON state handed to the judgment layer.

        Named fields rather than one blob: the questions reference them by path.
        """
        return {
            "ticket": {"subject": self.subject, "message": self.body},
            "account": {
                "plan_tier": self.customer_tier,
                "age_days": self.account_age_days,
                "tickets_last_30_days": self.prior_tickets_30d,
                "disputed_amount_usd": self.order_total_usd,
            },
        }


@dataclass(frozen=True)
class GoldLabel:
    """Human-assigned ground truth for one ticket."""

    department: Department
    priority: int  # 0..3, indexing PRIORITY_LEVELS
    needs_human: bool


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.requests + other.requests,
        )


@dataclass
class Judgment:
    """Result of one engine call: the answers plus what they cost to get."""

    values: dict[str, Any]
    latency_ms: float = 0.0
    usage: Usage = field(default_factory=Usage)

    def __getitem__(self, key: str) -> Any:
        return self.values[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)


@dataclass(frozen=True)
class TriageJudgment:
    """Supervisor-level judgments, all asked over the same state at once."""

    department: Department
    department_confidence: float
    department_probabilities: dict[str, float]
    priority: float  # expected score across PRIORITY_LEVELS, may be fractional
    priority_confidence: float
    needs_human: float  # probability, not a bool: code owns the threshold
    refund_eligible: float
    angry_customer: float
