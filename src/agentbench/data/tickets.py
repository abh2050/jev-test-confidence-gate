"""A small labeled ticket set.

Roughly a third of these are deliberately ambiguous — a billing complaint with a
technical cause, an angry message about a trivial problem, a calm message about a
severe one. Clean tickets tell you almost nothing about a decision layer; these
are where two engines diverge, and where a confidence number either earns its
keep or does not.

Labels are one reviewer's judgment on invented tickets. Replace them with your
own traffic before reading anything into an accuracy number.
"""

from __future__ import annotations

from ..types import GoldLabel, Ticket

Case = tuple[Ticket, GoldLabel]

CASES: list[Case] = [
    # --- Unambiguous billing -------------------------------------------------
    (
        Ticket(
            id="T-001",
            subject="Charged twice for March",
            body=(
                "My card was billed $49 twice on March 3rd. I only have one "
                "subscription. Please refund the duplicate."
            ),
            customer_tier="pro",
            account_age_days=420,
            prior_tickets_30d=0,
            order_total_usd=49.0,
        ),
        GoldLabel("billing", 2, True),
    ),
    (
        Ticket(
            id="T-002",
            subject="What is this line item?",
            body=(
                "There's a $12 'overage' charge on my invoice this month. I don't "
                "know what it's for. Can you explain?"
            ),
            customer_tier="starter",
            account_age_days=95,
            prior_tickets_30d=0,
            order_total_usd=12.0,
        ),
        GoldLabel("billing", 0, False),
    ),
    (
        Ticket(
            id="T-003",
            subject="Cancel and refund annual plan",
            body=(
                "I upgraded to annual by mistake four days ago and want to go back "
                "to monthly. The annual charge was $588."
            ),
            customer_tier="pro",
            account_age_days=730,
            prior_tickets_30d=0,
            order_total_usd=588.0,
        ),
        GoldLabel("billing", 1, True),
    ),
    (
        Ticket(
            id="T-004",
            subject="Card declined but account suspended anyway",
            body=(
                "My card expired, I updated it the same day, but the account is "
                "still locked and my team can't log in. Invoice was $199."
            ),
            customer_tier="business",
            account_age_days=310,
            prior_tickets_30d=1,
            order_total_usd=199.0,
        ),
        GoldLabel("billing", 3, True),
    ),
    # --- Unambiguous technical ----------------------------------------------
    (
        Ticket(
            id="T-005",
            subject="PDF export spins forever",
            body=(
                "Open any report, click Export, choose PDF — the spinner never "
                "finishes. Chrome 128 on macOS. CSV export works fine."
            ),
            customer_tier="pro",
            account_age_days=200,
            prior_tickets_30d=0,
            order_total_usd=0.0,
        ),
        GoldLabel("technical", 1, False),
    ),
    (
        Ticket(
            id="T-006",
            subject="API returning 500 on every call",
            body=(
                "Since about 09:00 UTC every request to /v1/records returns a 500. "
                "Our production sync is down. Nothing changed on our side."
            ),
            customer_tier="enterprise",
            account_age_days=890,
            prior_tickets_30d=0,
            order_total_usd=0.0,
        ),
        GoldLabel("technical", 3, True),
    ),
    (
        Ticket(
            id="T-007",
            subject="Dashboard numbers look off",
            body=(
                "The weekly total on my dashboard doesn't match what I get when I "
                "export the same range. Off by about 3%."
            ),
            customer_tier="business",
            account_age_days=150,
            prior_tickets_30d=0,
            order_total_usd=0.0,
        ),
        GoldLabel("technical", 1, True),
    ),
    (
        Ticket(
            id="T-008",
            subject="Can't invite users",
            body=(
                "The invite button is greyed out. I'm the account owner. We have "
                "seats left — 4 of 10 used."
            ),
            customer_tier="business",
            account_age_days=60,
            prior_tickets_30d=0,
            order_total_usd=0.0,
        ),
        GoldLabel("technical", 2, False),
    ),
    (
        Ticket(
            id="T-009",
            subject="Sidebar icon is misaligned",
            body="Tiny thing, but the settings icon in the sidebar sits 2px too low on Firefox.",
            customer_tier="starter",
            account_age_days=30,
            prior_tickets_30d=0,
            order_total_usd=0.0,
        ),
        GoldLabel("technical", 0, False),
    ),
    # --- Unambiguous escalation ---------------------------------------------
    (
        Ticket(
            id="T-010",
            subject="Notice of intent to pursue legal action",
            body=(
                "Our counsel has advised us that your retention of our data after "
                "the deletion request of 14 May breaches our DPA. Respond within "
                "five business days."
            ),
            customer_tier="enterprise",
            account_age_days=1200,
            prior_tickets_30d=2,
            order_total_usd=0.0,
        ),
        GoldLabel("escalation", 3, True),
    ),
    (
        Ticket(
            id="T-011",
            subject="We are cancelling",
            body=(
                "This is the fourth time I've written about the same sync failure "
                "and nobody has fixed it. We've signed with a competitor and will "
                "be gone at renewal."
            ),
            customer_tier="enterprise",
            account_age_days=950,
            prior_tickets_30d=4,
            order_total_usd=0.0,
        ),
        GoldLabel("escalation", 3, True),
    ),
    (
        Ticket(
            id="T-012",
            subject="GDPR data export request",
            body=(
                "Under Article 15 I am requesting a complete copy of all personal "
                "data you hold about me, within the statutory period."
            ),
            customer_tier="starter",
            account_age_days=500,
            prior_tickets_30d=0,
            order_total_usd=0.0,
        ),
        GoldLabel("escalation", 2, True),
    ),
    # --- Ambiguous: billing surface, technical cause -------------------------
    (
        Ticket(
            id="T-013",
            subject="Billed for seats we removed",
            body=(
                "We removed three seats last month but the invoice still shows ten. "
                "The seat count in settings says seven, so your billing system and "
                "your app disagree."
            ),
            customer_tier="business",
            account_age_days=400,
            prior_tickets_30d=1,
            order_total_usd=150.0,
        ),
        GoldLabel("technical", 2, True),
    ),
    (
        Ticket(
            id="T-014",
            subject="Refund me, your app lost my work",
            body=(
                "Two hours of edits vanished when the editor crashed. I want my "
                "money back for this month."
            ),
            customer_tier="pro",
            account_age_days=88,
            prior_tickets_30d=0,
            order_total_usd=49.0,
        ),
        GoldLabel("technical", 3, True),
    ),
    # --- Ambiguous: angry tone, small problem --------------------------------
    (
        Ticket(
            id="T-015",
            subject="ABSOLUTELY RIDICULOUS",
            body=(
                "I have wasted TWENTY MINUTES trying to find the dark mode toggle. "
                "Why is this so hard? Completely unacceptable design."
            ),
            customer_tier="starter",
            account_age_days=12,
            prior_tickets_30d=0,
            order_total_usd=0.0,
        ),
        GoldLabel("technical", 0, False),
    ),
    # --- Ambiguous: calm tone, severe problem --------------------------------
    (
        Ticket(
            id="T-016",
            subject="Small question about permissions",
            body=(
                "Quick one — a contractor on the free viewer role seems to be able "
                "to open the payroll folder. Probably my mistake in setup, but "
                "thought I'd check."
            ),
            customer_tier="enterprise",
            account_age_days=600,
            prior_tickets_30d=0,
            order_total_usd=0.0,
        ),
        GoldLabel("escalation", 3, True),
    ),
    # --- Ambiguous: could be any of the three --------------------------------
    (
        Ticket(
            id="T-017",
            subject="Third time asking",
            body=(
                "I've asked twice about the duplicate charge and got a template "
                "reply both times. I'd like an actual person to look at this."
            ),
            customer_tier="pro",
            account_age_days=365,
            prior_tickets_30d=3,
            order_total_usd=49.0,
        ),
        GoldLabel("escalation", 2, True),
    ),
    (
        Ticket(
            id="T-018",
            subject="Upgrade didn't apply",
            body=(
                "I paid for the business plan an hour ago. Card was charged, but "
                "the app still shows me on starter and blocks the features."
            ),
            customer_tier="starter",
            account_age_days=45,
            prior_tickets_30d=0,
            order_total_usd=99.0,
        ),
        GoldLabel("billing", 3, True),
    ),
    (
        Ticket(
            id="T-019",
            subject="Is the service down?",
            body="Can't load anything. Is it just me? Two of my colleagues say the same.",
            customer_tier="business",
            account_age_days=220,
            prior_tickets_30d=0,
            order_total_usd=0.0,
        ),
        GoldLabel("technical", 3, False),
    ),
    (
        Ticket(
            id="T-020",
            subject="Pricing question before renewal",
            body=(
                "Our renewal is in three weeks. We're comparing you against two "
                "alternatives and the per-seat price is the sticking point. Can "
                "someone talk to us about it?"
            ),
            customer_tier="enterprise",
            account_age_days=1100,
            prior_tickets_30d=0,
            order_total_usd=0.0,
        ),
        GoldLabel("escalation", 2, True),
    ),
    (
        Ticket(
            id="T-021",
            subject="Feature request: bulk edit",
            body=(
                "Not a bug. It would save us hours if we could edit tags on many "
                "records at once. Is that on the roadmap?"
            ),
            customer_tier="pro",
            account_age_days=270,
            prior_tickets_30d=0,
            order_total_usd=0.0,
        ),
        GoldLabel("technical", 0, False),
    ),
    (
        Ticket(
            id="T-022",
            subject="Invoice needs our VAT number",
            body=(
                "Our finance team can't process the invoice without our VAT ID on "
                "it. Can you reissue? Quarter closes Friday."
            ),
            customer_tier="business",
            account_age_days=480,
            prior_tickets_30d=0,
            order_total_usd=240.0,
        ),
        GoldLabel("billing", 2, True),
    ),
    (
        Ticket(
            id="T-023",
            subject="Slow since Tuesday",
            body=(
                "Everything takes 5-10 seconds to load since Tuesday. Still works, "
                "just painful. Same for everyone on my team."
            ),
            customer_tier="business",
            account_age_days=330,
            prior_tickets_30d=0,
            order_total_usd=0.0,
        ),
        GoldLabel("technical", 2, True),
    ),
    (
        Ticket(
            id="T-024",
            subject="Account compromised?",
            body=(
                "I got a login alert from a country I've never been to, and there "
                "are records in my account I didn't create."
            ),
            customer_tier="pro",
            account_age_days=190,
            prior_tickets_30d=0,
            order_total_usd=0.0,
        ),
        GoldLabel("escalation", 3, True),
    ),
]


def load_cases(limit: int | None = None) -> list[Case]:
    return CASES[:limit] if limit else list(CASES)


def by_id(ticket_id: str) -> Case:
    for case in CASES:
        if case[0].id == ticket_id:
            return case
    raise KeyError(f"no ticket {ticket_id!r}")
