"""List prices, so a token count can be read as money.

These are published list prices entered by hand, not fetched — they go stale.
Check them against each vendor's pricing page before quoting a cost figure, and
edit here rather than in the report code.

Prices are US dollars per million tokens.

Sources as entered:
  jev        — TypeSafe launch post: $0.042/MTok input, output "free (too cheap
               to meter)". Entered as 0.0 output, which makes the output column
               structurally zero rather than merely small.
  gpt-4o-mini — OpenAI list pricing.
"""

from __future__ import annotations

from dataclasses import dataclass

PRICES_LAST_CHECKED = "2026-09-20"


@dataclass(frozen=True)
class Price:
    input_per_mtok: float
    output_per_mtok: float

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * self.input_per_mtok
            + output_tokens * self.output_per_mtok
        ) / 1_000_000


# Keyed by the model name each engine reports.
LIST_PRICES: dict[str, Price] = {
    "jev-latest": Price(input_per_mtok=0.042, output_per_mtok=0.0),
    "jev": Price(input_per_mtok=0.042, output_per_mtok=0.0),
    "gpt-4o-mini": Price(input_per_mtok=0.15, output_per_mtok=0.60),
    "gpt-4o": Price(input_per_mtok=2.50, output_per_mtok=10.00),
}


def price_for(model: str) -> Price | None:
    """The list price for a model, or None if we have not entered one."""
    if model in LIST_PRICES:
        return LIST_PRICES[model]
    # Tolerate dated snapshot suffixes like gpt-4o-mini-2024-07-18.
    for name, price in LIST_PRICES.items():
        if model.startswith(name):
            return price
    return None
