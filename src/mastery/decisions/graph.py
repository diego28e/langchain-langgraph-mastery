"""LangGraph triage with Jev at the branches: cheap by default, frontier on exception (Lesson 15.04, Project 15A).

``build_triage_graph`` routes ONE ticket:

    decide (Jev) ──confident──────────────► queue
          │ └─uncertain──► escalate (LLM) ─► queue
          └─churn risk (enterprise)─► account_review (interrupt: a human confirms) ─► queue

``build_batch_graph`` fans a list of tickets out to that graph with ``Send`` and gathers the results.
Code owns the flow; Jev only answers the questions at each branch.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt

__all__ = ["TicketState", "build_batch_graph", "build_triage_graph"]


def _dump(response: Any) -> dict[str, Any]:
    """Store plain JSON in graph state: checkpointers serialize it safely (no pickled pydantic objects)."""
    return response.model_dump(mode="json")


def _load(data: dict[str, Any] | None) -> Any:
    from langchain_typesafe import ClassifierResponse

    return ClassifierResponse.model_validate(data) if data else None


class TicketState(TypedDict, total=False):
    ticket: dict[str, Any]
    decision: dict[str, Any]    # Jev's ClassifierResponse as JSON (checkpoint-safe), see _load
    escalation: dict[str, Any]  # the LLM's answer as JSON, when escalated
    result: dict[str, Any]


def build_triage_graph(jev: Any, escalate: Any, *, route_at: float = 0.8, churn_at: float = 0.7,
                       questions: Callable[[], dict[str, Any]], state_of: Callable[[dict], Any],
                       provenance: Callable[[Any], str], checkpointer: Any = None) -> Any:
    """``jev`` and ``escalate`` both take ``{"state", "questions"}`` and return a ``ClassifierResponse``."""

    def top(response: Any) -> float:
        return max(response.choices["team"].probabilities.values())

    def decide(state: TicketState) -> TicketState:
        return {"decision": _dump(jev.invoke({"state": state_of(state["ticket"]), "questions": questions()}))}

    def branch(state: TicketState) -> str:
        d, tier = _load(state["decision"]), state["ticket"].get("tier")
        if tier == "enterprise" and d.nouls["churn_risk"].noul >= churn_at:
            return "account_review"
        return "queue" if top(d) >= route_at else "escalate"

    def escalate_node(state: TicketState) -> TicketState:
        return {"escalation": _dump(escalate.invoke({"state": state_of(state["ticket"]), "questions": questions()}))}

    def account_review(state: TicketState) -> TicketState:
        d = _load(state["decision"])
        verdict = interrupt({"ticket": state["ticket"]["id"], "text": state["ticket"]["text"],
                             "suggested_team": d.choices["team"].choice, "p_churn": round(d.nouls["churn_risk"].noul, 2),
                             "ask": "Confirm the team (and whether to alert the account manager)."})
        team = (verdict or {}).get("team") or d.choices["team"].choice
        return {"result": {"queue": team, "by": "human", "alert_account_manager": bool((verdict or {}).get("alert_am")),
                           "p_top": round(top(d), 2)}}

    def queue(state: TicketState) -> TicketState:
        if state.get("result"):
            return {}
        used = _load(state.get("escalation") or state["decision"])
        return {"result": {"queue": used.choices["team"].choice, "by": provenance(used),
                           "p_top": round(top(_load(state["decision"])), 2),
                           "urgency": round(used.scores["urgency"].score, 2)}}

    g = StateGraph(TicketState)
    g.add_node("decide", decide)
    g.add_node("escalate", escalate_node)
    g.add_node("account_review", account_review)
    g.add_node("queue", queue)
    g.add_edge(START, "decide")
    g.add_conditional_edges("decide", branch, ["queue", "escalate", "account_review"])
    g.add_edge("escalate", "queue")
    g.add_edge("account_review", "queue")
    g.add_edge("queue", END)
    return g.compile(checkpointer=checkpointer)


class BatchState(TypedDict, total=False):
    tickets: list[dict[str, Any]]
    results: Annotated[list[dict[str, Any]], operator.add]


def build_batch_graph(route_one: Callable[[dict[str, Any]], dict[str, Any]]) -> Any:
    """Fan ``tickets`` out with ``Send`` (one branch per ticket, run in parallel), gather ``results``."""

    def fan_out(state: BatchState) -> list[Send]:
        return [Send("route_one", {"ticket": t}) for t in state["tickets"]]

    def route_one_node(state: dict[str, Any]) -> BatchState:
        return {"results": [{"id": state["ticket"]["id"], **route_one(state["ticket"])}]}

    g = StateGraph(BatchState)
    g.add_node("route_one", route_one_node)
    g.add_conditional_edges(START, fan_out, ["route_one"])
    g.add_edge("route_one", END)
    return g.compile()
