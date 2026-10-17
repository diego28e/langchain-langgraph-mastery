"""The Orbita Cloud support-triage questions Module 15 asks Jev (lessons 15.01-15.07 and Project 15A).

Questions live in code, not in each notebook, so a lesson, its recordings and the project all send
byte-identical requests (replay looks answers up by state + questions).
"""

from __future__ import annotations

from typing import Any

__all__ = ["TEAMS", "TICKETS", "URGENCY", "chat_questions", "chat_transcript", "lab_halves", "lab_tickets", "queue_questions",
           "single_questions", "ticket_state", "triage_questions", "urgent_question"]

TEAMS = {
    "billing": "Invoices, charges, refunds, plans and payment methods.",
    "account_access": "Signing in, SSO, passwords, 2FA, permissions and seats.",
    "technical": "Outages, errors, slowness, deploys, APIs and integrations that are broken.",
    "feature_request": "Asking for something the product does not do yet.",
}
URGENCY = [
    "Can wait for the normal queue (days).",
    "Should be handled today.",
    "Blocking the customer's business right now.",
]

# Six realistic tickets (synthetic, no real customers). The last two are deliberately ambiguous.
TICKETS: list[dict[str, Any]] = [
    {"id": "T1", "tier": "enterprise",
     "text": "Our checkout API has returned 502 for 20 minutes and orders are failing. Please look now."},
    {"id": "T2", "tier": "starter",
     "text": "We were charged twice for October. Can you refund one of the payments?"},
    {"id": "T3", "tier": "business",
     "text": "SSO login loops back to the sign-in page for everyone on our team since this morning."},
    {"id": "T4", "tier": "starter",
     "text": "Would love a dark mode for the dashboard someday, my eyes would thank you."},
    {"id": "T5", "tier": "business",
     "text": "After the plan upgrade our new seats can't log in, and the invoice shows 12 seats instead of 10."},
    {"id": "T6", "tier": "enterprise",
     "text": "Exports are slow lately. Not urgent, but if this continues we'll review the contract at renewal."},
]


def urgent_question() -> dict[str, Any]:
    """The single yes/no question of Lesson 15.01, Part 3."""
    from langchain_typesafe import Noul

    return {"urgent": Noul(instructions="Does this ticket need a human to act right now?")}


def triage_questions() -> dict[str, Any]:
    """Four questions about one ticket, answered in one request: team, urgency, is_bug, churn_risk."""
    from langchain_typesafe import Choice, Noul, NoulCriteria, Score

    return {
        "team": Choice(instructions="Which team should own this ticket?", criteria=dict(TEAMS)),
        "urgency": Score(instructions="How urgent is this ticket?", criteria=list(URGENCY)),
        "is_bug": Noul(instructions="Is the customer reporting broken product behaviour?",
                       criteria=NoulCriteria(true="Something that used to work is failing or wrong.",
                                             false="A question, a request, or a billing matter.")),
        "churn_risk": Noul(instructions="Does the customer signal they might cancel or not renew?"),
    }


def ticket_state(ticket: dict[str, Any]) -> dict[str, Any]:
    """Structured state: Jev reads JSON as well as text, so the tier travels with the message."""
    return {"customer_tier": ticket["tier"], "ticket": ticket["text"]}


# --- Lesson 15.02: the labeled lab set (Module 14's held-out tickets, six queues) ---------------------------

def queue_questions() -> dict[str, Any]:
    """Two questions per lab ticket: the queue (Choice over Module 14's six queues) and is_outage (Noul)."""
    from langchain_typesafe import Choice, Noul

    from mastery.finetune.tickets import QUEUE_HELP, QUEUES

    return {
        "queue": Choice(instructions="Which support queue should handle this ticket?",
                        criteria={q: QUEUE_HELP[q] for q in QUEUES}),
        "is_outage": Noul(instructions="Is the service down or badly degraded for this customer right now?"),
    }


def lab_tickets() -> list[dict[str, Any]]:
    """Module 14's 234 held-out (``test``) tickets with gold queues: the calibration lab of Lesson 15.02."""
    from mastery.finetune.tickets import by_split, load_tickets

    return sorted(by_split(load_tickets())["test"], key=lambda t: t["id"])


def lab_halves() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """``(tune, check)``: pick thresholds on one half, measure them on the other (alternate ids)."""
    tickets = lab_tickets()
    return tickets[0::2], tickets[1::2]


# --- Lesson 15.03: a chat transcript as state, and one question per request ------------------------------

def chat_transcript() -> list[Any]:
    """A short support chat as LangChain messages (no ids, so the request is byte-stable for replay)."""
    from langchain_core.messages import AIMessage, HumanMessage

    return [
        HumanMessage("Hi, our station dashboard shows no data since 9am."),
        AIMessage("Sorry about that! Can you try a hard refresh and tell me if the stations show as online?"),
        HumanMessage("Refreshed twice. Still nothing, and this is the third time this month. I want to talk to a person."),
    ]


def chat_questions() -> dict[str, Any]:
    from langchain_typesafe import Choice, Noul

    return {
        "wants_human": Noul(instructions="Has the customer asked to talk to a human agent?"),
        "intent": Choice(instructions="What does the customer need?", criteria=dict(TEAMS)),
    }


def single_questions() -> list[dict[str, Any]]:
    """:func:`triage_questions` split into four one-question sets (Lesson 15.03: one request vs four)."""
    return [{name: q} for name, q in triage_questions().items()]
