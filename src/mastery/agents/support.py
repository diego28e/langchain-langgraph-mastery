"""Orbita Cloud support desk: the shared domain for Lessons 09.02-09.05 and Project 09.

Orbita Cloud is a fictional SaaS. Three specialists (billing, technical, account) each own a
few tools; a product FAQ in ``data/samples/support-desk/faq`` is searchable through
``mastery.rag`` (BM25 offline; Chroma in the project's LIVE mode). Refunds above
``REFUND_THRESHOLD`` call ``interrupt()`` so a billing manager approves them.

The same specialists are assembled two ways so you can measure the difference:

- :func:`build_handoffs_desk` (Pattern A): triage → billing / technical / account as graph
  nodes with ``transfer_to_*`` tools (multiple-agent-subgraph handoffs).
- :func:`build_subagents_desk` (Pattern B): one coordinator calls the specialists as tools.

Everything runs keyless with :func:`offline_model`: a rule-based scripted model that reads
its role from the system prompt and its options from the tools it was bound to, so it
behaves like a (very literal) tool-calling LLM. Swap in ``mastery.models.get_model`` for LIVE.
"""
from __future__ import annotations

import json
import math
import re
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any

from langchain.tools import ToolRuntime, tool
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import MessagesState
from langgraph.types import Send, interrupt

from mastery.agents.specialists import (
    ESCALATION_MESSAGE,
    Specialist,
    StepState,
    handoff_graph,
    handoff_tool,
    step_middleware,
    step_tool,
    subagent_tool,
    task_tool,
)
from mastery.config import find_repo_root
from mastery.testing import ScriptedChatModel

__all__ = [
    "DOMAINS",
    "DOMAIN_TOOLS",
    "MAX_HANDOFFS",
    "REFUND_THRESHOLD",
    "SIDE_EFFECT_TOOLS",
    "OfflineSupportModel",
    "SupportContext",
    "SupportDesk",
    "build_custom_desk",
    "build_handoffs_desk",
    "build_refund_workflow",
    "build_router_desk",
    "build_single_agent_baseline",
    "build_single_agent_desk",
    "build_skills_desk",
    "build_subagents_desk",
    "conversation_reviewer",
    "detect_intents",
    "evaluate",
    "faq_search",
    "is_refund_request",
    "load_conversations",
    "load_skill_tool",
    "make_skills",
    "make_specialists",
    "make_support_tools",
    "offline_model",
    "parse_refund",
    "run_conversation",
    "score",
    "signed_in_customer",
    "split_by_intent",
    "support_dir",
]

REFUND_THRESHOLD = 50.0
# Handoffs: more transfers than this in ONE user turn is a ping-pong, so the desk escalates to a human.
MAX_HANDOFFS = 4
DOMAINS = ("billing", "technical", "account")
DOMAIN_TOOLS = {
    "billing": ("lookup_invoices", "issue_refund"),
    "technical": ("search_faq", "check_service_status"),
    "account": ("send_password_reset", "unlock_account", "update_email"),
}
_TOOL_DOMAIN = {name: domain for domain, names in DOMAIN_TOOLS.items() for name in names}

# Keyword rules for the offline model (and the router in Lesson 09.04). A real model reads
# the request; these regexes are the "literal LLM" stand-in, kept deliberately simple.
_INTENT_PATTERNS = {
    "billing": r"\brefund|\binvoice|\bcharg|\bbill|\bpayment|\bprice",
    "technical": r"\b429\b|\berror|\bapi\b|\bsync|\bwebhook|\bexport|\boutage|\bdown\b|\bstatus\b",
    "account": r"\bpassword|\bemail\b|\blocked\b|\b2fa\b|\blog ?in\b|\bsign ?in\b|\bseat",
}
_CUSTOMER = re.compile(r"\bC-\d{4}\b")
_INVOICE = re.compile(r"\bINV-\d{4}\b")
_AMOUNT = re.compile(r"\$\s?(\d+(?:\.\d{1,2})?)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def support_dir() -> Path:
    return find_repo_root() / "data" / "samples" / "support-desk"


# --------------------------------------------------------------------------- identity
@dataclass(frozen=True)
class SupportContext:
    """Who is signed in, passed at invoke time: ``app.invoke(..., context=SupportContext("C-1001"))``.

    The customer ID comes from your login system, never from the chat: anyone can TYPE
    "I'm C-1002". When ``customer_id`` is set, every customer-scoped tool acts on that customer
    only and refuses any other ID the model passes. ``None`` (the default, used by the offline
    test set) means "no login": tools trust the ID in the conversation, as in a demo.
    """

    customer_id: str | None = None


def signed_in_customer(runtime: Any) -> str | None:
    """The signed-in customer ID from a ``ToolRuntime`` / ``Runtime`` (None if there is no login)."""
    context = getattr(runtime, "context", None)
    cid = getattr(context, "customer_id", None)
    return cid.strip().upper() if isinstance(cid, str) and cid.strip() else None


# --------------------------------------------------------------------------- backend
@dataclass
class SupportDesk:
    """A fake backend: customers, invoices, refunds, service status and an event log."""

    customers: dict[str, dict] = field(default_factory=dict)
    services: dict[str, str] = field(default_factory=dict)
    refunds: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    denials: list[dict] = field(default_factory=list)
    _seed: dict = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, path: str | Path | None = None) -> SupportDesk:
        data = json.loads(Path(path or support_dir() / "customers.json").read_text(encoding="utf-8"))
        desk = cls(_seed=data)
        desk.reset()
        return desk

    def reset(self) -> None:
        """Back to the seed data (run this between conversations)."""
        data = json.loads(json.dumps(self._seed))
        self.customers = data.get("customers", {})
        self.services = data.get("services", {})
        self.refunds = []
        self.events = []
        self.denials = []

    def log(self, tool_name: str, **args: Any) -> None:
        self.events.append({"tool": tool_name, "domain": _TOOL_DOMAIN.get(tool_name, "?"), "args": args})

    def tools_called(self) -> list[str]:
        return [e["tool"] for e in self.events]

    def route(self) -> list[str]:
        """Specialist domains that did work, in order, without repeats."""
        out: list[str] = []
        for e in self.events:
            if e["domain"] not in out:
                out.append(e["domain"])
        return out


# --------------------------------------------------------------------------- FAQ search
def faq_search(kind: str = "bm25", *, embeddings: Any = None, k: int = 2) -> Callable[[str], list[Document]]:
    """``query -> top-k FAQ chunks``. ``kind="bm25"`` is keyless; ``"chroma"`` builds a vector index."""
    from mastery.rag import BM25, build_index, load_corpus, retrieve, split_documents

    root = find_repo_root()
    docs = load_corpus(support_dir() / "faq", root=root)
    chunks = split_documents(docs, preset="markdown", chunk_size=600)
    if kind == "bm25":
        bm25 = BM25(chunks)
        return lambda query: bm25.search(query, k=k)
    if embeddings is None:
        from mastery.rag import default_embeddings
        embeddings = default_embeddings()
    store = build_index(chunks, embeddings, kind=kind, collection="support_faq")  # type: ignore[arg-type]
    return lambda query: retrieve(store, query, k=k)


def _passages(docs: list[Document]) -> str:
    if not docs:
        return "No matching FAQ passages."
    parts = []
    for d in docs:
        text = re.sub(r"\s+", " ", d.page_content).strip()
        parts.append(f"[{d.metadata.get('source', '?')}] {text}")
    return "\n".join(parts)


# --------------------------------------------------------------------------- tools
# --------------------------------------------------------------------------- manager review (HITL)
_EDIT_AMOUNT = re.compile(r"\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:usd)?\s*", re.IGNORECASE)


def parse_amount(text: Any) -> float | None:
    """``"150"``, ``"$150"``, ``"$1,990.00"``, ``"150 USD"`` → 150.0; anything else (or non-finite) → None."""
    if isinstance(text, int | float):
        return float(text) if math.isfinite(text) else None
    match = _EDIT_AMOUNT.fullmatch(str(text or ""))
    return float(match.group(1).replace(",", "")) if match else None


def manager_review(payload: dict[str, Any], *, max_amount: float, max_invalid: int = 3) -> tuple[str, float | None, str]:
    """Ask a billing manager (``interrupt``) and validate the ANSWER before anything can raise.

    An edit is a new amount, so it gets the same rule as the agent's request: ``0 < amount <= max_amount``.
    An invalid answer ("yes", "$abc", "1990" on a $199 invoice) re-asks with a NEW interrupt that
    carries an ``error``, instead of crashing the run (a crash would store the bad answer and replay
    it on every resume: a poisoned thread, Lesson 08.03). ``interrupt()`` is never inside a ``try``.

    Returns:
        ``(action, amount, feedback)``: ``("approve", None, "")``, ``("edit", 150.0, "")`` or
        ``("reject", None, feedback)``. After ``max_invalid`` invalid answers it rejects.
    """
    from mastery.graphs.hitl import parse_decision

    error = ""
    for attempt in range(1, max_invalid + 1):
        answer = interrupt({**payload, "max_amount": max_amount} | ({"error": error, "attempt": attempt} if error else {}))
        try:
            decision = parse_decision(answer)
        except ValueError as exc:
            error = f"Not a valid decision ({exc}). Answer approve, reject, or edit with a new amount."
            continue
        if decision.action != "edit":
            return decision.action, None, decision.feedback or ""
        amount = parse_amount(decision.text)
        if amount is None or not 0 < amount <= max_amount:
            error = f"An edit needs an amount between $0 and ${max_amount:.2f}; got {decision.text!r}."
            continue
        return "edit", amount, decision.feedback or ""
    return "reject", None, f"no valid decision after {max_invalid} tries"


def make_support_tools(desk: SupportDesk, search: Callable[[str], list[Document]] | None = None, *,
                       threshold: float = REFUND_THRESHOLD) -> dict[str, list[Any]]:
    """The specialists' tools, grouped by domain. Every call is logged in ``desk.events``."""
    search = search or faq_search()

    def customer(customer_id: str) -> dict | None:
        return desk.customers.get(customer_id.strip().upper())

    def refused(tool_name: str, customer_id: str, runtime: Any) -> str | None:
        """A refusal message if a signed-in customer asks the tool to act on ANOTHER customer."""
        signed_in = signed_in_customer(runtime)
        if signed_in is None or customer_id.strip().upper() == signed_in:
            return None
        desk.denials.append({"tool": tool_name, "asked_for": customer_id, "signed_in": signed_in})
        return (f"Not allowed: you are signed in as {signed_in}, so I can only act on {signed_in}'s account, "
                f"not {customer_id}.")

    @tool
    def lookup_invoices(customer_id: str, runtime: ToolRuntime[SupportContext]) -> str:
        """List a customer's invoices (id, date, amount). customer_id looks like C-1001."""
        if (refusal := refused("lookup_invoices", customer_id, runtime)) is not None:
            return refusal
        desk.log("lookup_invoices", customer_id=customer_id)
        c = customer(customer_id)
        if c is None:
            return f"No customer {customer_id}."
        rows = [f"{i['id']} {i['date']} ${i['amount']:.2f}" + (f" ({i['note']})" if i.get("note") else "")
                for i in c["invoices"]]
        return f"Invoices for {customer_id} ({c['plan']} plan): " + "; ".join(rows)

    @tool
    def issue_refund(customer_id: str, invoice_id: str, amount: float, runtime: ToolRuntime[SupportContext], reason: str = "") -> str:
        """Refund part or all of an invoice. Refunds above the approval threshold pause for a billing manager."""
        # Identity first, before any interrupt: a manager is never asked about someone else's invoice.
        if (refusal := refused("issue_refund", customer_id, runtime)) is not None:
            return refusal
        # Log AFTER any interrupt: on resume this whole function runs again from the top,
        # so a side effect placed before interrupt() would happen twice (Lesson 08.03).
        result, refunded = _refund(customer_id, invoice_id, float(amount), reason)
        # The audit log records what was actually refunded (after a manager's edit), and what was asked.
        desk.log("issue_refund", customer_id=customer_id, invoice_id=invoice_id,
                 amount=refunded if refunded is not None else amount, requested=amount)
        return result

    def _refund(customer_id: str, invoice_id: str, amount: float, reason: str) -> tuple[str, float | None]:
        """Returns (message for the model, amount actually refunded or None)."""
        c = customer(customer_id)
        if c is None:
            return f"No customer {customer_id}.", None
        invoice = next((i for i in c["invoices"] if i["id"] == invoice_id.strip().upper()), None)
        if invoice is None:
            return f"Invoice {invoice_id} does not belong to {customer_id}.", None
        if any(r["invoice_id"] == invoice["id"] for r in desk.refunds):
            return f"Invoice {invoice['id']} was already refunded.", None
        amount = float(amount)
        if not math.isfinite(amount) or amount <= 0 or amount > invoice["amount"]:
            return f"Refund amount must be between $0 and ${invoice['amount']:.2f}.", None
        approved_by = "policy"
        if amount > threshold:
            action, edited, feedback = manager_review({
                "type": "refund_approval", "customer_id": customer_id, "invoice_id": invoice["id"],
                "amount": amount, "threshold": threshold, "reason": reason,
                "question": f"Approve a ${amount:.2f} refund (over ${threshold:.0f})? approve / edit (new amount) / reject",
            }, max_amount=invoice["amount"])
            if action == "reject":
                return (f"Refund of ${amount:.2f} for {invoice['id']} was not approved by a billing manager"
                        f" ({feedback}).", None)
            if action == "edit":
                amount = edited
            approved_by = "billing manager"
        desk.refunds.append({"customer_id": customer_id, "invoice_id": invoice["id"], "amount": amount,
                             "approved_by": approved_by, "over_threshold": amount > threshold})
        return (f"Refunded ${amount:.2f} for {invoice['id']} (approved by {approved_by}); "
                "it arrives in 5-10 business days.", amount)

    @tool
    def search_faq(query: str) -> str:
        """Search the Orbita Cloud product FAQ (billing, technical and account topics)."""
        desk.log("search_faq", query=query)
        return _passages(search(query))

    @tool
    def check_service_status(service: str = "") -> str:
        """Current status of Orbita Cloud services (api, station sync, webhooks, dashboard)."""
        desk.log("check_service_status", service=service)
        return "Service status: " + "; ".join(f"{k}: {v}" for k, v in desk.services.items())

    @tool
    def send_password_reset(customer_id: str, runtime: ToolRuntime[SupportContext]) -> str:
        """Email the customer a password reset link."""
        if (refusal := refused("send_password_reset", customer_id, runtime)) is not None:
            return refusal
        desk.log("send_password_reset", customer_id=customer_id)
        c = customer(customer_id)
        if c is None:
            return f"No customer {customer_id}."
        return f"Sent a password reset link to {c['email']}; it is valid for 60 minutes."

    @tool
    def unlock_account(customer_id: str, runtime: ToolRuntime[SupportContext]) -> str:
        """Unlock a customer account that was locked after failed sign-ins."""
        if (refusal := refused("unlock_account", customer_id, runtime)) is not None:
            return refusal
        desk.log("unlock_account", customer_id=customer_id)
        c = customer(customer_id)
        if c is None:
            return f"No customer {customer_id}."
        was = c["locked"]
        c["locked"] = False
        return f"Account {customer_id} is unlocked." if was else f"Account {customer_id} was not locked."

    @tool
    def update_email(customer_id: str, new_email: str, runtime: ToolRuntime[SupportContext]) -> str:
        """Start a login email change; the customer must click the confirmation link."""
        if (refusal := refused("update_email", customer_id, runtime)) is not None:
            return refusal
        desk.log("update_email", customer_id=customer_id, new_email=new_email)
        if customer(customer_id) is None:
            return f"No customer {customer_id}."
        return f"Sent a confirmation link to {new_email}; the change applies after it is clicked."

    return {
        "billing": [lookup_invoices, issue_refund],
        "technical": [search_faq, check_service_status],
        "account": [send_password_reset, unlock_account, update_email],
    }


# --------------------------------------------------------------------------- prompts and specialists
_SPECIALIST_PROMPT = (
    "You are Orbita Cloud's {domain} specialist. {scope}\n"
    "Use your tools; never invent invoice numbers, amounts or policies. If you need the customer ID "
    "(looks like C-1001) and it is not in the conversation, ask for it. Answer in at most 3 sentences "
    "and include the concrete result of each tool you used."
)
_SCOPES = {
    "billing": "You handle invoices, charges and refunds. Refunds above $50 need a billing manager's "
               "approval; the issue_refund tool asks for it automatically, so just call it.",
    "technical": "You handle API errors, rate limits, station sync, webhooks, exports and outages. "
                 "Check the service status for outages; search the FAQ for how-to questions.",
    "account": "You handle passwords, locked accounts, login email changes, 2FA and seats.",
}
DESCRIPTIONS = {
    "billing": "Invoices, charges and refunds (refunds above $50 need manager approval).",
    "technical": "API errors and rate limits, station sync, webhooks, exports, service status.",
    "account": "Password resets, locked accounts, login email changes, 2FA, seats.",
}
TRIAGE_PROMPT = (
    "You are Orbita Cloud's triage agent. Do not solve problems yourself: transfer the customer to "
    "the right specialist with a transfer tool (billing, technical or account). If the request is "
    "unclear, ask one short question."
)
HANDOFF_SUFFIX = (
    "\nIf the customer's latest message needs another specialist (billing, technical or account), "
    "finish your part, then transfer with the matching transfer tool."
)
GENERALIST_PROMPT = (
    "You are Orbita Cloud's support agent. You handle billing (invoices, charges, refunds; refunds above "
    "$50 need a billing manager's approval, which issue_refund asks for automatically), technical "
    "questions (API errors, sync, webhooks, status) and accounts (passwords, locks, email changes). "
    "Use your tools; never invent facts. If you need the customer ID (looks like C-1001), ask for it. "
    "Answer in at most 4 sentences with the concrete result of each tool you used."
)
COORDINATOR_PROMPT = (
    "You are Orbita Cloud's support coordinator. Delegate each part of the customer's request to "
    "the right specialist tool (billing, technical, account), in parallel when there are several. "
    "Always pass a complete, standalone task that includes the customer ID if the conversation has "
    "one. Then answer the customer with the specialists' results in at most 4 sentences."
)


def make_specialists(tools: dict[str, list[Any]], *, handoffs: bool = False) -> dict[str, Specialist]:
    """One :class:`Specialist` per domain. ``handoffs=True`` adds the "transfer when needed" rule."""
    out = {}
    for domain in DOMAINS:
        prompt = _SPECIALIST_PROMPT.format(domain=domain, scope=_SCOPES[domain])
        if handoffs:
            prompt += HANDOFF_SUFFIX
        out[domain] = Specialist(name=domain, description=DESCRIPTIONS[domain], system_prompt=prompt,
                                 tools=tuple(tools[domain]))
    return out


def build_single_agent_baseline(model: Any, tools: dict[str, list[Any]], *, checkpointer: Any) -> Any:
    """The baseline: ONE agent with every tool and one big prompt. Measure this before going multi-agent."""
    from langchain.agents import create_agent

    return create_agent(model, tools=[t for d in DOMAINS for t in tools[d]], system_prompt=GENERALIST_PROMPT,
                        name="support_agent", checkpointer=checkpointer, context_schema=SupportContext)


def make_skills() -> dict[str, dict[str, str]]:
    """One skill per domain: a one-line description (always in the prompt) and the full
    instructions + FAQ text (loaded only when needed). Progressive disclosure."""
    faq = support_dir() / "faq"
    return {d: {"description": DESCRIPTIONS[d],
                "content": f"# Skill: {d}\n{_SCOPES[d]}\n\n" + (faq / f"{d}.md").read_text(encoding="utf-8")}
            for d in DOMAINS}


def load_skill_tool(skills: dict[str, dict[str, str]]) -> Any:
    """The docs' ``load_skill(skill_name)`` tool over ``skills``."""

    @tool
    def load_skill(skill_name: str) -> str:
        """Load a skill's full instructions and reference text. Call it before handling a request in that area."""
        skill = skills.get(skill_name.strip().lower())
        if skill is None:
            return f"Unknown skill {skill_name!r}. Available: {', '.join(skills)}."
        return skill["content"]

    return load_skill


SKILLS_PROMPT = (
    "You are Orbita Cloud's support agent. Before you handle a request, load the matching skill with "
    "load_skill (once per conversation is enough). Available skills:\n{listing}\n"
    "Use your tools; never invent facts. If you need the customer ID (looks like C-1001), ask for it. "
    "Answer in at most 4 sentences with the concrete result of each tool you used."
)


def build_skills_desk(model: Any, tools: dict[str, list[Any]], *, checkpointer: Any, inline: bool = False) -> Any:
    """Skills pattern: ONE agent with every tool plus ``load_skill``; skill texts load on demand.

    ``inline=True`` is the comparison point: every skill's content pasted into the system
    prompt up front (no ``load_skill``), i.e. what skills avoid.
    """
    from langchain.agents import create_agent

    skills = make_skills()
    all_tools = [t for d in DOMAINS for t in tools[d]]
    if inline:
        prompt = GENERALIST_PROMPT + "\n\n" + "\n\n".join(s["content"] for s in skills.values())
        return create_agent(model, tools=all_tools, system_prompt=prompt, name="support_agent",
                            checkpointer=checkpointer, context_schema=SupportContext)
    listing = "\n".join(f"- {name}: {s['description']}" for name, s in skills.items())
    return create_agent(model, tools=[load_skill_tool(skills), *all_tools],
                        system_prompt=SKILLS_PROMPT.format(listing=listing), name="support_agent",
                        checkpointer=checkpointer, context_schema=SupportContext)


def build_handoffs_desk(model_for: Callable[[str], Any], tools: dict[str, list[Any]], *,
                        checkpointer: Any, carry: str = "turn", max_handoffs: int | None = MAX_HANDOFFS,
                        triage_prompt: str = TRIAGE_PROMPT) -> Any:
    """Pattern A: triage + 3 specialists as nodes of one graph, routed by ``active_agent``.

    ``triage_prompt`` swaps the triage agent's system prompt (Lesson 10.07 evaluates prompt versions).

    ``carry="turn"`` (default here) hands over the specialist's tool results with the
    conversation; see :func:`mastery.agents.handoff_tool` for why ``"last"`` can loop.
    ``max_handoffs`` (default :data:`MAX_HANDOFFS`) escalates a ping-pong to a human instead
    of looping until ``recursion_limit``; ``None`` turns the guard off (Lesson 09.03 does, to show the bug).
    """
    from langchain.agents import create_agent

    transfers = {d: handoff_tool(d, description=f"Transfer to the {d} specialist: {DESCRIPTIONS[d]}",
                                 carry=carry) for d in DOMAINS}
    specialists = make_specialists(tools, handoffs=True)
    agents: dict[str, Any] = {
        "triage": create_agent(model_for("triage"), tools=list(transfers.values()),
                               system_prompt=triage_prompt, name="triage", context_schema=SupportContext),
    }
    for domain, spec in specialists.items():
        others = [t for d, t in transfers.items() if d != domain]
        agents[domain] = spec.build(model_for(domain), extra_tools=others, context_schema=SupportContext)
    return handoff_graph(agents, entry="triage", checkpointer=checkpointer, context_schema=SupportContext,
                         max_handoffs=max_handoffs)


def build_single_agent_desk(model: Any, tools: dict[str, list[Any]], *, checkpointer: Any) -> Any:
    """Pattern A, one-agent form (what the handoffs docs recommend): ONE ``create_agent`` whose
    middleware swaps prompt and tools based on ``current_step`` (triage → billing / technical / account)."""
    from langchain.agents import create_agent

    transfers = {d: step_tool(d, description=f"Transfer to the {d} specialist: {DESCRIPTIONS[d]}") for d in DOMAINS}
    specialists = make_specialists(tools, handoffs=True)
    steps: dict[str, dict[str, Any]] = {"triage": {"prompt": TRIAGE_PROMPT, "tools": list(transfers.values())}}
    for domain, spec in specialists.items():
        steps[domain] = {"prompt": spec.system_prompt,
                         "tools": [*spec.tools, *(t for d, t in transfers.items() if d != domain)]}
    all_tools = [*transfers.values(), *(t for d in DOMAINS for t in tools[d])]
    return create_agent(model, tools=all_tools, middleware=[step_middleware(steps, default="triage")],
                        state_schema=StepState, checkpointer=checkpointer, name="support_desk",
                        context_schema=SupportContext)


def build_subagents_desk(model_for: Callable[[str], Any], tools: dict[str, list[Any]], *,
                         checkpointer: Any, context: str = "query", dispatch: str = "per_agent") -> Any:
    """Pattern B: a coordinator agent with each specialist wrapped as a tool.

    ``dispatch="per_agent"`` gives one tool per specialist (``billing_agent``, ...);
    ``"task"`` gives a single ``task(agent_name, description)`` tool.
    """
    from langchain.agents import create_agent

    specialists = make_specialists(tools)
    built = {d: spec.build(model_for(d), context_schema=SupportContext)            # no checkpointer
             for d, spec in specialists.items()}
    if dispatch == "task":
        subtools = [task_tool({d: (built[d], DESCRIPTIONS[d]) for d in DOMAINS})]
    else:
        subtools = [subagent_tool(built[d], name=f"{d}_agent", description=f"The {d} specialist. {DESCRIPTIONS[d]}",
                                  context=context)  # type: ignore[arg-type]
                    for d in DOMAINS]
    return create_agent(model_for("coordinator"), tools=subtools, system_prompt=COORDINATOR_PROMPT,
                        name="coordinator", checkpointer=checkpointer, context_schema=SupportContext)


def _collect(left: list | None, right: list | None) -> list:
    """Reducer for router results: ``None`` clears (a new turn), a list appends (parallel branches)."""
    if right is None:
        return []
    return [*(left or []), *right]


class RouterState(MessagesState):
    """Router state: the conversation, this turn's routes, and the specialists' answers."""

    routes: list[str]
    results: Annotated[list, _collect]
    escalate: bool


def build_router_desk(model_for: Callable[[str], Any], tools: dict[str, list[Any]], *, checkpointer: Any = None,
                      classify: Callable[[str], Any] | None = None, min_confidence: float | None = None) -> Any:
    """Router pattern: classify the latest message, fan out with ``Send`` to the matching
    specialists in parallel, then join their answers. ``classify`` defaults to
    :func:`detect_intents` (keyword rules, zero model calls); pass an LLM classifier for LIVE.

    ``classify`` returns the domains, or ``(domains, confidence)``. With ``min_confidence``, a
    routed message whose confidence is below it goes to nobody: the desk answers with
    :data:`~mastery.agents.ESCALATION_MESSAGE` (a human takes over) instead of guessing. A plain
    list counts as confidence 1.0. A model's self-reported confidence is NOT calibrated: check
    it on labelled examples before you pick the threshold (Module 10).

    Stateless per turn: specialists see only the routed query (plus the customer ID), and the
    join is deterministic code, so model calls = one per routed specialist (+ its tool loop).
    """
    from langgraph.graph import END, START, StateGraph

    classify = classify or detect_intents
    built = {d: spec.build(model_for(d), context_schema=SupportContext) for d, spec in make_specialists(tools).items()}

    def route(state: RouterState) -> dict:
        text, _ = _turn(state["messages"])
        decision = classify(text)
        domains, confidence = decision if isinstance(decision, tuple) else (decision, 1.0)
        routes = [d for d in domains if d in built]
        escalate = bool(routes) and min_confidence is not None and confidence < min_confidence
        return {"routes": [] if escalate else routes, "results": None, "escalate": escalate}

    def fan_out(state: RouterState) -> list[Send] | str:
        text, _ = _turn(state["messages"])
        context = _all_user_text(state["messages"])
        clauses = split_by_intent(text)
        return [Send(d, {"query": _with_customer(clauses.get(d, text), context)}) for d in state["routes"]] or "join"

    def make_node(domain: str) -> Callable[[dict], dict]:
        def node(payload: dict) -> dict:
            out = built[domain].invoke({"messages": [{"role": "user", "content": payload["query"]}]})
            return {"results": [{"domain": domain, "answer": out["messages"][-1].text}]}
        return node

    def join(state: RouterState) -> dict:
        if state.get("escalate"):
            return {"messages": [AIMessage(content=ESCALATION_MESSAGE, name="router")]}
        if not state.get("results"):
            text = "Happy to help! Is this about billing, a technical problem, or your account?"
        else:
            order = {d: i for i, d in enumerate(state["routes"])}
            text = " ".join(r["answer"] for r in sorted(state["results"], key=lambda r: order.get(r["domain"], 9)))
        return {"messages": [AIMessage(content=text, name="router")]}

    builder = StateGraph(RouterState, context_schema=SupportContext)
    builder.add_node("route", route)
    for domain in built:
        builder.add_node(domain, make_node(domain))
        builder.add_edge(domain, "join")
    builder.add_node("join", join)
    builder.add_edge(START, "route")
    builder.add_conditional_edges("route", fan_out, [*built, "join"])
    builder.add_edge("join", END)
    return builder.compile(checkpointer=checkpointer)


class RefundState(MessagesState):
    """Pattern C state: the conversation plus the structured refund request and its outcome."""

    request: dict
    problem: str
    approved_by: str
    result: str


def parse_refund(messages: list) -> dict:
    """Customer ID, invoice and amount from the conversation (deterministic, no model)."""
    text, _ = _turn(messages)
    context = _all_user_text(messages)
    cid = (_CUSTOMER.findall(text) or _CUSTOMER.findall(context) or [None])[-1]
    invoice = (_INVOICE.findall(text) or [None])[0]
    amount = (_AMOUNT.findall(text) or [None])[0]
    return {"customer_id": cid, "invoice_id": invoice, "amount": float(amount) if amount else None, "reason": text[:120]}


def build_refund_workflow(desk: SupportDesk, writer: Any, *, threshold: float = REFUND_THRESHOLD,
                          checkpointer: Any = None) -> Any:
    """Pattern C: the refund path as a custom graph (Lesson 09.05, Project 09 stretch).

    ``parse`` → ``validate`` → ``approve`` (``interrupt()`` only above ``threshold``) → ``issue``
    → ``reply``. Every step but ``reply`` is plain code: the policy cannot be talked around,
    and the model is used once, to write the customer reply (``writer`` = any chat model).
    """
    from langgraph.graph import END, START, StateGraph
    from langgraph.runtime import Runtime

    def parse(state: RefundState, runtime: Runtime[SupportContext]) -> dict:
        request = parse_refund(state["messages"])
        signed_in = signed_in_customer(runtime)
        problem = ""
        if signed_in is not None:
            # The login decides whose invoice this is; a different ID typed in the chat is refused.
            if request["customer_id"] not in (None, signed_in):
                problem = f"you are signed in as {signed_in}, not {request['customer_id']}"
                desk.denials.append({"tool": "refund_workflow", "asked_for": request["customer_id"],
                                     "signed_in": signed_in})
            request = {**request, "customer_id": signed_in}
        return {"request": request, "problem": problem, "approved_by": "", "result": ""}

    def validate(state: RefundState) -> dict:
        r = state["request"]
        if state.get("problem"):
            return {"problem": state["problem"]}
        if not (r["customer_id"] and r["invoice_id"] and r["amount"]):
            missing = [k for k in ("customer_id", "invoice_id", "amount") if not r[k]]
            return {"problem": "missing " + ", ".join(missing)}
        c = desk.customers.get(r["customer_id"])
        invoice = next((i for i in (c or {}).get("invoices", []) if i["id"] == r["invoice_id"]), None)
        if invoice is None:
            return {"problem": f"invoice {r['invoice_id']} does not belong to {r['customer_id']}"}
        if any(x["invoice_id"] == invoice["id"] for x in desk.refunds):
            return {"problem": f"invoice {invoice['id']} was already refunded"}
        if r["amount"] <= 0 or r["amount"] > invoice["amount"]:
            return {"problem": f"amount must be between $0 and ${invoice['amount']:.2f}"}
        return {"problem": ""}

    def approve(state: RefundState) -> dict:
        r = state["request"]
        # Logged here (after any interrupt, so once) whatever the decision: the attempt is what's audited.
        if r["amount"] <= threshold:
            desk.log("issue_refund", customer_id=r["customer_id"], invoice_id=r["invoice_id"], amount=r["amount"])
            return {"approved_by": "policy"}
        invoice = next(i for i in desk.customers[r["customer_id"]]["invoices"] if i["id"] == r["invoice_id"])
        action, edited, feedback = manager_review({
            "type": "refund_approval", **{k: r[k] for k in ("customer_id", "invoice_id", "amount", "reason")},
            "threshold": threshold,
            "question": f"Approve a ${r['amount']:.2f} refund (over ${threshold:.0f})? approve / edit (new amount) / reject",
        }, max_amount=invoice["amount"])
        final = edited if action == "edit" else r["amount"]
        desk.log("issue_refund", customer_id=r["customer_id"], invoice_id=r["invoice_id"],
                 amount=final, requested=r["amount"])
        if action == "reject":
            return {"approved_by": "", "problem": f"not approved by a billing manager ({feedback})"}
        if action == "edit":
            return {"approved_by": "billing manager", "request": {**r, "amount": edited}}
        return {"approved_by": "billing manager"}

    def issue(state: RefundState) -> dict:
        r = state["request"]
        desk.refunds.append({"customer_id": r["customer_id"], "invoice_id": r["invoice_id"], "amount": r["amount"],
                             "approved_by": state["approved_by"], "over_threshold": r["amount"] > threshold})
        return {"result": f"Refunded ${r['amount']:.2f} for {r['invoice_id']} (approved by {state['approved_by']}); "
                          "it arrives in 5-10 business days."}

    def reply(state: RefundState) -> dict:
        r = state["request"]
        if state["result"]:
            facts = state["result"]
        elif state["problem"].startswith("not approved"):
            facts = f"Refund of ${r['amount']:.2f} for {r['invoice_id']} was {state['problem']}."
        else:
            facts = f"I could not refund this request: {state['problem']}."
        message = writer.invoke([
            SystemMessage("You are Orbita Cloud's refund desk. Rewrite the FACTS as a short, friendly reply to the "
                          "customer. Keep every number, invoice ID and the outcome exactly as given."),
            HumanMessage(f"FACTS: {facts}"),
        ])
        return {"messages": [AIMessage(content=message.text or facts, name="refund_desk")]}

    def after_validate(state: RefundState) -> str:
        return "reply" if state["problem"] else "approve"

    def after_approve(state: RefundState) -> str:
        return "reply" if state["problem"] else "issue"

    builder = StateGraph(RefundState, context_schema=SupportContext)
    for name, fn in (("parse", parse), ("validate", validate), ("approve", approve), ("issue", issue),
                     ("reply", reply)):
        builder.add_node(name, fn)
    builder.add_edge(START, "parse")
    builder.add_edge("parse", "validate")
    builder.add_conditional_edges("validate", after_validate, ["approve", "reply"])
    builder.add_conditional_edges("approve", after_approve, ["issue", "reply"])
    builder.add_edge("issue", "reply")
    builder.add_edge("reply", END)
    return builder.compile(checkpointer=checkpointer, name="refund_workflow")


def is_refund_request(text: str) -> bool:
    """Only-billing message that asks for a refund: the path Pattern C takes over."""
    return detect_intents(text) == ["billing"] and "refund" in text.lower()


def build_custom_desk(model_for: Callable[[str], Any], tools: dict[str, list[Any]], desk: SupportDesk, *,
                      checkpointer: Any, writer: Any = None) -> Any:
    """Pattern C embedded: refunds go to the custom workflow, everything else to the handoffs desk."""
    from langgraph.graph import END, START, StateGraph

    refunds = build_refund_workflow(desk, writer if writer is not None else _echo_writer())
    agents = build_handoffs_desk(model_for, tools, checkpointer=None)

    def agents_node(state: MessagesState) -> dict:
        out = agents.invoke({"messages": state["messages"]})
        return {"messages": [out["messages"][-1]]}

    def pick(state: MessagesState) -> str:
        text, _ = _turn(state["messages"])
        return "refunds" if is_refund_request(text) else "agents"

    builder = StateGraph(MessagesState, context_schema=SupportContext)
    builder.add_node("refunds", refunds)
    builder.add_node("agents", agents_node)
    builder.add_conditional_edges(START, pick, ["refunds", "agents"])
    builder.add_edge("refunds", END)
    builder.add_edge("agents", END)
    return builder.compile(checkpointer=checkpointer)


def _echo_writer() -> ScriptedChatModel:
    """Offline reply writer: returns the FACTS unchanged (a real model would rephrase them)."""
    return ScriptedChatModel(responses=[lambda messages: messages[-1].text.removeprefix("FACTS: ")], repeat_last=True)


# --------------------------------------------------------------------------- offline model
def detect_intents(text: str) -> list[str]:
    """Domains mentioned in ``text``, in order of first mention (keyword rules)."""
    hits = []
    for domain, pattern in _INTENT_PATTERNS.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            hits.append((m.start(), domain))
    return [d for _, d in sorted(hits)]


def split_by_intent(text: str) -> dict[str, str]:
    """Split a multi-domain request into one clause per domain (keyword rules).

    ``"refund INV-1 ($49) and tell me how to fix 429 errors"`` →
    ``{"billing": "refund INV-1 ($49)", "technical": "tell me how to fix 429 errors"}``.
    A domain whose words appear nowhere on their own gets the whole text.
    """
    clauses = [c.strip() for c in re.split(r"(?<=[.?!])\s+|\s+and\s+(?=also\b|tell\b|how\b|what\b|please\b|can\b|my\b|our\b)",
                                          text) if c.strip()]
    parts: dict[str, list[str]] = {}
    current = None
    for clause in clauses:
        found = detect_intents(clause)
        current = found[0] if found else current     # a clause without keywords belongs to the previous one
        if current:
            parts.setdefault(current, []).append(clause)
    return {d: (" ".join(parts[d]) if d in parts else text) for d in detect_intents(text)}


def _with_customer(task: str, context: str) -> str:
    cid = (_CUSTOMER.findall(context) or [None])[-1]
    return task if (cid is None or cid in task) else f"{task} (customer {cid})"


def _call(name: str, args: dict, messages: list) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{name}_{len(messages)}",
                                              "type": "tool_call"}])


def _calls(items: list[tuple[str, dict]], messages: list) -> AIMessage:
    return AIMessage(content="", tool_calls=[
        {"name": n, "args": a, "id": f"call_{n}_{len(messages)}_{i}", "type": "tool_call"}
        for i, (n, a) in enumerate(items)])


def _role(messages: list) -> str:
    system = next((m for m in messages if isinstance(m, SystemMessage)), None)
    match = re.search(r"Orbita Cloud's (\w+) (specialist|agent|coordinator)", system.text if system else "")
    if not match:
        return "unknown"
    if match.group(2) == "coordinator":
        return "coordinator"
    return "generalist" if match.group(1) == "support" else match.group(1)


def _turn(messages: list) -> tuple[str, list]:
    """(latest user text, messages after it)."""
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            return messages[i].text, messages[i + 1:]
    return "", []


def _all_user_text(messages: list) -> str:
    return "\n".join(m.text for m in messages if isinstance(m, HumanMessage))


def _results(turn: list) -> list[ToolMessage]:
    return [m for m in turn if isinstance(m, ToolMessage) and not (m.name or "").startswith("transfer_to_")]


def _compose(results: list[ToolMessage]) -> str:
    return " ".join(r.text.strip() for r in results) or "Done."


def _specialist_action(domain: str, text: str, context: str, messages: list) -> AIMessage:
    cid = (_CUSTOMER.findall(text) or _CUSTOMER.findall(context) or [None])[-1]
    if "Your task:" in text:              # forked context (subagent_tool(context="history")): act on the task
        text = text.rsplit("Your task:", 1)[1].strip()
    text = split_by_intent(text).get(domain, text)
    low = text.lower()
    if domain == "technical":
        if re.search(r"sync|\bdown\b|outage|status", low):
            return _call("check_service_status", {"service": ""}, messages)
        return _call("search_faq", {"query": text}, messages)
    if cid is None:
        return AIMessage(content="Could you give me your customer ID? It looks like C-1001.")
    if domain == "billing":
        invoice = (_INVOICE.findall(text) or [None])[0]
        amount = (_AMOUNT.findall(text) or [None])[0]
        if "refund" in low and invoice and amount:
            return _call("issue_refund", {"customer_id": cid, "invoice_id": invoice, "amount": float(amount),
                                          "reason": text[:120]}, messages)
        return _call("lookup_invoices", {"customer_id": cid}, messages)
    if domain == "account":
        if "locked" in low:
            return _call("unlock_account", {"customer_id": cid}, messages)
        email = _EMAIL.findall(text)
        if "email" in low and email:
            return _call("update_email", {"customer_id": cid, "new_email": email[-1]}, messages)
        return _call("send_password_reset", {"customer_id": cid}, messages)
    return AIMessage(content="I can't help with that.")


def _policy(messages: list, bound: list[str]) -> AIMessage:
    role = _role(messages)
    text, turn = _turn(messages)
    context = _all_user_text(messages)
    intents = detect_intents(text)
    transfers = {n.removeprefix("transfer_to_") for n in bound if n.startswith("transfer_to_")}
    results = _results(turn)

    if role == "triage":
        target = next((d for d in intents if d in transfers), None)
        if target:
            return _call(f"transfer_to_{target}", {}, messages)
        return AIMessage(content="Happy to help! Is this about billing, a technical problem, or your account? "
                                 "Please include your customer ID (like C-1001).")

    if role == "coordinator":
        if results:
            return AIMessage(content=_compose(results))
        tasks = {d: _with_customer(clause, context) for d, clause in split_by_intent(text).items()}
        if "task" in bound:
            picks = [("task", {"agent_name": d, "description": tasks[d]}) for d in intents]
        else:
            picks = [(f"{d}_agent", {"query": tasks[d]}) for d in intents if f"{d}_agent" in bound]
        if picks:
            return _calls(picks, messages)
        return AIMessage(content="Happy to help! Is this about billing, a technical problem, or your account?")

    if role == "generalist":
        results = [r for r in results if r.name != "load_skill"]
        served = {_TOOL_DOMAIN.get(r.name or "") for r in results}
        pending = [d for d in intents if d not in served]
        if pending:
            loaded = {r.text.split("\n", 1)[0].removeprefix("# Skill: ").strip()
                      for r in messages if isinstance(r, ToolMessage) and r.name == "load_skill"}
            if "load_skill" in bound and pending[0] not in loaded:
                return _call("load_skill", {"skill_name": pending[0]}, messages)
            return _specialist_action(pending[0], text, context, messages)
        if results:
            return AIMessage(content=_compose(results))
        return AIMessage(content="Happy to help! Is this about billing, a technical problem, or your account?")

    if role in DOMAINS:
        served = {_TOOL_DOMAIN.get(r.name or "") for r in results}
        if role in served or (results and role not in intents):
            pending = [d for d in intents if d not in served and d in transfers]
            if pending:
                return _call(f"transfer_to_{pending[0]}", {}, messages)
            return AIMessage(content=_compose(results))
        if intents and role not in intents:
            target = next((d for d in intents if d in transfers), None)
            if target:
                return _call(f"transfer_to_{target}", {}, messages)
        return _specialist_action(role, text, context, messages)

    return AIMessage(content="(offline model: unknown role)")


class OfflineSupportModel(ScriptedChatModel):
    """:class:`ScriptedChatModel` that also counts the bound tool schemas as input tokens.

    A real provider receives every tool's JSON schema on every call, so an agent with many
    tools pays for them each time. Counting them (4 characters ≈ 1 token) keeps the offline
    token comparison between patterns honest.
    """

    tool_tokens: int = 0

    def bind_tools(self, tools: Any, *, tool_choice: Any = None, **kwargs: Any) -> OfflineSupportModel:
        from langchain_core.utils.function_calling import convert_to_openai_tool

        super().bind_tools(tools, tool_choice=tool_choice, **kwargs)
        self.tool_tokens = sum(len(json.dumps(convert_to_openai_tool(t))) // 4 for t in tools)
        return self

    def _next(self, messages: list) -> AIMessage:
        message = super()._next(messages)
        usage = dict(message.usage_metadata or {})
        usage["input_tokens"] = usage.get("input_tokens", 0) + self.tool_tokens
        usage["total_tokens"] = usage.get("total_tokens", 0) + self.tool_tokens
        return message.model_copy(update={"usage_metadata": usage})


def offline_model(role: str | None = None) -> OfflineSupportModel:
    """A keyless stand-in for a tool-calling LLM on the support desk (see module docstring).

    One instance per agent: it reads the role from the system prompt and its options from
    the tool names it was last bound to. ``role`` is only a label for readability.
    """
    holder: dict[str, OfflineSupportModel] = {}

    def respond(messages: list) -> AIMessage:
        return _policy(messages, list(holder["model"].bound_tools or []))

    model = OfflineSupportModel(responses=[respond], repeat_last=True)
    holder["model"] = model
    return model


# --------------------------------------------------------------------------- running and scoring
def load_conversations(path: str | Path | None = None) -> list[dict]:
    text = Path(path or support_dir() / "conversations.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def conversation_reviewer(conversation: dict) -> Callable[[Any], Any]:
    """The billing manager for one test conversation: approves unless ``decision`` says otherwise."""
    decision = conversation.get("decision", "approve")

    def review(payload: Any) -> Any:
        if decision == "reject":
            return {"action": "reject", "feedback": "partial-month refunds are not offered"}
        return "approve"

    return review


def run_conversation(app: Any, conversation: dict, desk: SupportDesk, *, reviewer: Callable[[Any], Any] | None = None,
                     callbacks: Iterable[Any] = (), thread_id: str | None = None,
                     recursion_limit: int = 40, context: SupportContext | None = None) -> dict[str, Any]:
    """Play every user turn of ``conversation`` on one thread; answer pauses with ``reviewer``.

    ``recursion_limit`` caps graph steps per turn, so two agents that keep handing off to
    each other fail fast with ``GraphRecursionError`` instead of burning tokens.
    ``context`` is the signed-in customer (default: the conversation's ``signed_in`` field, if any).

    ``interrupts`` counts approvals asked (one per ``reviewer`` call), so two refunds approved
    in ONE pause count 2, as in a sequential pattern; ``pauses`` counts resume rounds.
    """
    from mastery.graphs.hitl import drive

    desk.reset()
    base = reviewer or conversation_reviewer(conversation)
    asked: list[Any] = []

    def counting_reviewer(payload: Any) -> Any:
        asked.append(payload)
        return base(payload)

    if context is None and conversation.get("signed_in"):
        context = SupportContext(conversation["signed_in"])
    config = {"configurable": {"thread_id": thread_id or f"{conversation['id']}-{uuid.uuid4().hex[:6]}"},
              "callbacks": list(callbacks), "recursion_limit": recursion_limit}
    answers, pauses, escalated = [], 0, False
    for turn in conversation["turns"]:
        result = drive(app, {"messages": [{"role": "user", "content": turn}]}, config, counting_reviewer,
                       printer=None, context=context)
        pauses += result["pauses"]
        last = result["values"]["messages"][-1]
        answers.append(last.text if hasattr(last, "text") else str(last))
        escalated = escalated or answers[-1] == ESCALATION_MESSAGE
    return {"id": conversation["id"], "answers": answers, "answer": answers[-1], "tools": desk.tools_called(),
            "route": desk.route(), "interrupts": len(asked), "pauses": pauses, "refunds": list(desk.refunds),
            "events": list(desk.events), "denials": list(desk.denials), "escalated": escalated}


SIDE_EFFECT_TOOLS = ("issue_refund", "unlock_account", "update_email", "send_password_reset")


def _refund_key(r: dict) -> tuple[str, str, float]:
    """Normalized (customer, invoice, amount): a LIVE model may send ``"49"`` or ``49.0`` or ``"inv-1003"``."""
    return (str(r.get("customer_id", "")).strip().upper(), str(r.get("invoice_id", "")).strip().upper(),
            round(float(r.get("amount", 0)), 2))


def score(conversation: dict, outcome: dict, *, threshold: float = REFUND_THRESHOLD) -> dict[str, Any]:
    """Resolution checks for one conversation. ``passed`` is True only if every check holds.

    It checks OUTCOMES, not just that something happened:

    - ``tools``: every expected tool ran; ``no_extra_side_effects``: no side-effect tool
      (refund, unlock, email change, password reset) ran unless expected (or listed in
      ``expect["allow"]``); ``once``: each side-effect tool ran at most once.
    - ``refunds``: when ``expect["refunds"]`` is given, the refunds actually made match it exactly
      (customer, invoice, amount): refunding $1 instead of $19, or another customer's invoice, fails.
    - ``route``: the specialists that did work (compared as a set: parallel work logs in any order).
    - ``interrupts``: approvals asked; ``answer``: required phrases; ``refund_policy``: every refund
      over ``threshold`` was approved by a billing manager.
    """
    expect = conversation["expect"]
    answer = outcome["answer"].lower()
    tools = outcome["tools"]
    allowed = set(expect.get("tools", [])) | set(expect.get("allow", []))
    checks = {
        "tools": all(t in tools for t in expect.get("tools", [])),
        "no_extra_side_effects": all(t in allowed for t in tools if t in SIDE_EFFECT_TOOLS),
        "once": all(tools.count(t) <= 1 for t in SIDE_EFFECT_TOOLS),
        "refunds": ("refunds" not in expect
                    or sorted(map(_refund_key, outcome["refunds"])) == sorted(map(_refund_key, expect["refunds"]))),
        "route": "route" not in expect or "route" not in outcome or set(outcome["route"]) == set(expect["route"]),
        "interrupts": outcome["interrupts"] == expect.get("interrupts", 0),
        "answer": all(s.lower() in answer for s in expect.get("contains", [])),
        "refund_policy": all(r["approved_by"] == "billing manager"
                             for r in outcome["refunds"] if float(r["amount"]) > threshold),
    }
    return {"id": conversation["id"], "passed": all(checks.values()), **checks}


def evaluate(app: Any, conversations: list[dict], desk: SupportDesk, *, meter: Any = None,
             limit: int | None = None, catch_errors: bool = True,
             reviewer: Callable[[Any], Any] | None = None) -> dict[str, Any]:
    """Run and score ``conversations`` on ``app``. With a :class:`UsageMeter`, adds calls/tokens/time.

    With ``catch_errors`` (default) a conversation that raises (provider error, recursion
    limit) is recorded as failed with its error, so one bad run doesn't hide the other 14.
    ``reviewer`` answers every approval pause (default: each conversation's own ``decision``).
    """
    rows = []
    for conv in conversations[:limit]:
        callbacks = [meter] if meter is not None else []
        try:
            if meter is not None:
                with meter:
                    outcome = run_conversation(app, conv, desk, callbacks=callbacks, reviewer=reviewer)
            else:
                outcome = run_conversation(app, conv, desk, reviewer=reviewer)
        except Exception as exc:
            if not catch_errors:
                raise
            outcome = {"id": conv["id"], "answers": [], "answer": f"⚠️ {type(exc).__name__}: {str(exc)[:160]}",
                       "tools": desk.tools_called(), "route": desk.route(), "interrupts": -1,
                       "refunds": list(desk.refunds), "events": list(desk.events), "denials": list(desk.denials),
                       "escalated": False, "error": type(exc).__name__}
        rows.append({**score(conv, outcome), "outcome": outcome})
    report = {"passed": sum(r["passed"] for r in rows), "total": len(rows), "rows": rows}
    if meter is not None:
        report["usage"] = meter.summary()
    return report
