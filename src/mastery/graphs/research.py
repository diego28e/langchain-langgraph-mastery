"""Project 08 reference graph: a durable, interruptible research-and-write agent.

    clarify_question (⏸️ if ambiguous) → plan → research [subgraph: search_docs → search_web]
    → draft → approval (⏸️ approve / edit / reject+feedback) → finalize   (reject → draft, max 3)

- ``search_web`` is **async** with a per-node ``timeout`` and a ``RetryPolicy`` (Lesson 08.02);
  after the retries an ``error_handler`` records the failure and the run continues with docs only.
- Long-term writing preferences come from the store (``("preferences", user_id)``), read by ``draft``.
- ``offline_models()`` / ``offline_web_search()`` / ``corpus_docs_search()`` run it with no key.
- ``python -m mastery.graphs.research --db FILE --thread ID --question "..." [--slow S]`` runs it
  offline with a SQLite checkpointer and prints one line per node: Project 08 kills that process
  mid-run and resumes the thread in the notebook.

Served by ``apps/m08_research_agent`` (``langgraph dev``). Verified 2026-10-12 with langgraph 1.2.14.
"""

from __future__ import annotations

import argparse
import asyncio
import operator
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.errors import NodeError, NodeTimeoutError
from langgraph.func import task
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import RetryPolicy, TimeoutPolicy, interrupt
from pydantic import BaseModel, Field

from mastery.graphs.hitl import approval_node
from mastery.graphs.nodes import timed

__all__ = [
    "Clarity",
    "Plan",
    "ResearchContext",
    "ResearchState",
    "build_research_graph",
    "corpus_docs_search",
    "draft_prompt",
    "offline_models",
    "offline_web_search",
    "planner_prompt",
    "retriever_docs_search",
    "run_and_kill",
    "web_tool_search",
]

Finding = dict[str, Any]                       # {"kind": "web"|"docs", "query", "text", "source"}
WebSearch = Callable[[str], list[Finding]]     # sync; run in a thread by the async node
DocsSearch = Callable[[str], list[Finding]]


class Clarity(BaseModel):
    """Is the request clear enough to research?"""

    ambiguous: bool = Field(description="True if you would have to guess the product, audience or scope")
    question: str = Field(default="", description="One short clarifying question when ambiguous")


class Plan(BaseModel):
    """A research plan."""

    queries: list[str] = Field(min_length=1, max_length=4, description="1-4 focused search queries")
    outline: list[str] = Field(min_length=1, max_length=5, description="Section headings for the answer")


class ResearchState(TypedDict, total=False):
    question: str
    clarification: str
    plan: dict            # Plan.model_dump(): plain data checkpoints anywhere (no allow-list needed, D-030)
    findings: Annotated[list[Finding], operator.add]
    draft: str
    feedback: str
    rejections: int
    approval: str
    final: str
    run_log: Annotated[list[dict], operator.add]


class ResearchSubState(TypedDict, total=False):   # the research subgraph's own schema
    plan: dict
    findings: Annotated[list[Finding], operator.add]
    run_log: Annotated[list[dict], operator.add]


@dataclass
class ResearchContext:
    user_id: str = "me"


CLARIFY_PROMPT = ("Decide if this research request is clear. It is ambiguous only if you would have to guess "
                  "what product, audience or scope is meant. If ambiguous, ask ONE short question.")
PLAN_PROMPT = ("Plan research for an answer about Orbita Labs weather stations. Return 2-3 focused search "
               "queries and 2-4 section headings.")
DRAFT_PROMPT = ("Write a short, accurate answer (150-300 words, Markdown) using ONLY the findings. Cite each "
                "fact as [source: <source>]. Follow the writing preferences. If feedback is given, apply it.")


def planner_prompt(question: str) -> list:
    return [SystemMessage(PLAN_PROMPT), HumanMessage(f"Request: {question}")]


def draft_prompt(question: str, plan: Plan | dict, findings: list[Finding], feedback: str = "", preferences: str = "") -> list:
    plan = Plan.model_validate(plan)
    notes = "\n".join(f"- ({f['kind']}) {f['text']} [source: {f.get('source') or 'none'}]" for f in findings)
    text = f"Request: {question}\nOutline: {' | '.join(plan.outline)}\n\nFindings:\n{notes or '- (none)'}"
    if preferences:
        text += f"\n\nWriting preferences: {preferences}"
    if feedback:
        text += f"\n\nReviewer feedback to apply: {feedback}"
    return [SystemMessage(DRAFT_PROMPT), HumanMessage(text)]


def build_research_graph(models: dict[str, Any], *, web_search: WebSearch, docs_search: DocsSearch,
                         checkpointer: Any = None, store: Any = None, search_timeout: float = 30.0,
                         search_attempts: int = 3, max_rejections: int = 3, name: str = "research_agent"):
    """Compile the Project 08 graph. ``models``: ``clarifier``, ``planner``, ``writer`` chat models."""
    clarify_model = models["clarifier"].with_structured_output(Clarity)
    plan_model = models["planner"].with_structured_output(Plan)
    writer = models["writer"]

    @task
    def assess_clarity(question: str) -> dict:
        """The LLM verdict, as a task: its result is checkpointed, so a resume reuses it."""
        return clarify_model.invoke([SystemMessage(CLARIFY_PROMPT), HumanMessage(question)]).model_dump()

    @timed("clarify_question")
    def clarify_question(state: ResearchState) -> dict:
        # The node re-runs from the top on resume. Calling the model directly here would ask it again,
        # and a different verdict ("clear" this time) would skip the interrupt and silently drop the
        # human's answer. The task replays the first verdict instead (Lesson 08.03, rules of interrupts).
        verdict = assess_clarity(state["question"]).result()
        if not verdict["ambiguous"]:
            return {}
        answer = interrupt({"kind": "clarify", "question": verdict["question"], "request": state["question"]})
        return {"clarification": str(answer), "question": f"{state['question']} ({answer})"}

    @timed("plan")
    def plan(state: ResearchState) -> dict:
        return {"plan": plan_model.invoke(planner_prompt(state["question"])).model_dump()}

    @timed("search_web")
    async def search_web(state: ResearchSubState) -> dict:
        found: list[Finding] = []
        for query in state["plan"]["queries"]:
            found += await asyncio.to_thread(web_search, query)   # blocking client → thread; timeout applies
        return {"findings": found}

    def web_failed(state: ResearchSubState, error: NodeError) -> dict:
        reason = f"{type(error.error).__name__}: {error.error}"[:200]
        return {"findings": [{"kind": "web", "query": "*", "text": f"Web search unavailable ({reason}).",
                              "source": None}],
                "run_log": [{"node": "search_web", "seconds": 0.0, "error": reason}]}

    @timed("search_docs")
    def search_docs(state: ResearchSubState) -> dict:
        found: list[Finding] = []
        for query in state["plan"]["queries"]:
            found += docs_search(query)
        return {"findings": found}

    sub = StateGraph(ResearchSubState)
    sub.add_node("search_web", search_web, timeout=TimeoutPolicy(run_timeout=search_timeout),
                 retry_policy=RetryPolicy(max_attempts=search_attempts, initial_interval=0.2, jitter=False,
                                          retry_on=(ConnectionError, TimeoutError, NodeTimeoutError)),
                 error_handler=web_failed)
    sub.add_node("search_docs", search_docs)
    # Sequential on purpose: measured with langgraph 1.2.14, a node's error_handler does not fire when the
    # node fails in the same superstep as a parallel sibling (the exception bubbles up instead). D-031.
    sub.add_edge(START, "search_docs")
    sub.add_edge("search_docs", "search_web")
    sub.add_edge("search_web", END)
    research_graph = sub.compile(name="research")

    async def research(state: ResearchState) -> dict:
        """Different schemas: call the subgraph with its own input and return only what the parent needs.

        (Adding it directly as a node would hand it the parent's ``run_log``/``findings`` and the
        returned lists would be added twice by the parent's reducers.)
        """
        out = await research_graph.ainvoke({"plan": state["plan"]})
        return {"findings": out.get("findings", []), "run_log": out.get("run_log", [])}

    @timed("draft")
    def draft(state: ResearchState, runtime: Runtime[ResearchContext]) -> dict:
        prefs = ""
        if runtime.store is not None:
            user = getattr(runtime.context, "user_id", None) or "me"
            prefs = "; ".join(str(i.value.get("text", "")) for i in runtime.store.search(("preferences", user)))
        reply = writer.invoke(draft_prompt(state["question"], state["plan"], state.get("findings", []),
                                           state.get("feedback", ""), prefs))
        return {"draft": reply.text}

    @timed("finalize")
    def finalize(state: ResearchState) -> dict:
        sources = sorted({f["source"] for f in state.get("findings", []) if f.get("source")})
        return {"final": state["draft"].rstrip() + "\n\n---\nSources: " + (", ".join(sources) or "none")}

    builder = StateGraph(ResearchState, context_schema=ResearchContext)
    builder.add_node("clarify_question", clarify_question)
    builder.add_node("plan", plan)
    builder.add_node("research", research)
    builder.add_node("draft", draft)
    builder.add_node("approval", approval_node(approved="finalize", rejected="draft", max_rejections=max_rejections,
                                               give_up="finalize"), destinations=("finalize", "draft"))
    builder.add_node("finalize", finalize)
    builder.add_edge(START, "clarify_question")
    builder.add_edge("clarify_question", "plan")
    builder.add_edge("plan", "research")
    builder.add_edge("research", "draft")
    builder.add_edge("draft", "approval")
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=checkpointer, store=store, name=name)


# --- Search backends -----------------------------------------------------------------------------------

def corpus_docs_search(k: int = 4, sentences: int = 2) -> DocsSearch:
    """Docs search over the Module 06 corpus (offline, free): BM25 chunks, then the best statements.

    Headings and questions are dropped (they read badly in a draft); every finding is a copied
    sentence with its source file, never invented text. Swap in Project 06's Chroma index with
    ``retriever_docs_search``.
    """
    from mastery.config import find_repo_root
    from mastery.rag import BM25, load_corpus, split_documents
    from mastery.rag.retrieve import terms

    chunks = split_documents(load_corpus(find_repo_root() / "data" / "samples" / "rag" / "corpus"), "markdown", 800, 100)
    bm25 = BM25(chunks)
    generic = {"nimbu", "station", "orbita", "lab", "how", "what", "troubleshoot"}

    def search(query: str) -> list[Finding]:
        wanted = set(terms(query)) - generic
        scored = []
        for rank, doc in enumerate(bm25.search(" ".join(sorted(wanted)) or query, k=k)):
            lines = [ln.replace("**", "").strip(" -*") for ln in doc.page_content.splitlines()
                     if ln.strip() and not ln.lstrip().startswith("#")]
            if doc.metadata.get("type") == "pdf":          # PDF line breaks are layout, not sentence ends
                lines = [" ".join(lines)]
            for sentence in (x for ln in lines for x in re.split(r"(?<=[.!?])\s+(?=[A-Z])", " ".join(ln.split()))):
                sentence = sentence.strip(" -*")
                overlap = len(wanted & set(terms(sentence)))
                if overlap and not sentence.endswith("?") and 30 < len(sentence) < 300:
                    scored.append((-overlap, rank, sentence, doc.metadata["source"]))
        best = list(dict.fromkeys((sent, src) for *_, sent, src in sorted(scored)))[:sentences]
        return [{"kind": "docs", "query": query, "text": sent, "source": src} for sent, src in best]

    return search


def retriever_docs_search(retrieve: Callable[[str], list[Any]], sentences: int = 2) -> DocsSearch:
    """Wrap any ``query -> [Document]`` search (e.g. Project 06's Chroma index) as a docs search."""
    def search(query: str) -> list[Finding]:
        out = []
        for doc in retrieve(query)[:sentences]:
            text = " ".join(line for line in doc.page_content.splitlines() if not line.lstrip().startswith("#"))
            first = re.split(r"(?<=[.!])\s+(?=[A-Z])", " ".join(text.replace("**", "").split()))[0]
            out.append({"kind": "docs", "query": query, "text": first[:300], "source": doc.metadata.get("source")})
        return out

    return search


def offline_web_search(*, failures: int = 0, delay: float = 0.0) -> WebSearch:
    """Offline stand-in for web search: no results, but it can fail or be slow on purpose.

    ``failures``: the first N calls raise ``ConnectionError`` (to watch the retry policy).
    ``delay``: seconds to sleep per call (to trip the node timeout).
    """
    state = {"calls": 0}

    def search(query: str) -> list[Finding]:
        state["calls"] += 1
        if delay:
            time.sleep(delay)
        if state["calls"] <= failures:
            raise ConnectionError(f"offline web search: simulated outage (call {state['calls']})")
        return []

    search.calls = state  # type: ignore[attr-defined]
    return search


def web_tool_search(tool: Any) -> WebSearch:
    """Wrap Module 05's ``web_search`` tool (💸 one Groq browser-search call per query)."""
    def search(query: str) -> list[Finding]:
        msg = tool.invoke({"type": "tool_call", "name": tool.name, "args": {"query": query}, "id": "web"})
        urls = [s["url"] for s in (getattr(msg, "artifact", None) or {}).get("sources", [])]
        return [{"kind": "web", "query": query, "text": str(msg.content)[:1500], "source": urls[0] if urls else None}]

    return search


# --- Offline models ------------------------------------------------------------------------------------

def offline_models() -> dict[str, Any]:
    """Scripted ``clarifier``, ``planner`` and ``writer`` (no key, deterministic).

    clarifier: ambiguous when the request has fewer than 4 words. planner: the request itself plus a
    "troubleshooting" query. writer: one bullet per finding with its source; applies "shorter"
    (2 bullets), "bullets"/"paragraph" preferences and echoes the feedback it applied.
    """
    from mastery.testing import ScriptedChatModel

    def clarify(messages: list) -> AIMessage:
        request = messages[-1].text.strip()
        ambiguous = len(re.findall(r"\w+", request)) < 4
        args = Clarity(ambiguous=ambiguous, question="Which product or topic do you mean, and for whom?"
                       if ambiguous else "").model_dump()
        return AIMessage("", tool_calls=[{"name": "Clarity", "id": "c", "args": args}])

    def plan(messages: list) -> AIMessage:
        request = messages[-1].text.removeprefix("Request:").strip().rstrip("?")
        args = Plan(queries=[request, f"{request} troubleshooting"],
                    outline=["What to know", "What to do"]).model_dump()
        return AIMessage("", tool_calls=[{"name": "Plan", "id": "p", "args": args}])

    def write(messages: list) -> AIMessage:
        text = messages[-1].text
        request = re.search(r"^Request: (.+)$", text, re.MULTILINE).group(1)
        facts = re.findall(r"^- \((docs|web)\) (.+) \[source: ([^\]]+)\]$", text, re.MULTILINE)
        facts = list(dict.fromkeys(f for f in facts if f[2] != "none"))   # drop duplicates, keep order
        feedback = (re.search(r"^Reviewer feedback to apply: (.+)$", text, re.MULTILINE) or [None, ""])[1]
        prefs = (re.search(r"^Writing preferences: (.+)$", text, re.MULTILINE) or [None, ""])[1].lower()
        if "shorter" in feedback.lower():
            facts = facts[:2]
        lines = [f"# {request.rstrip('?')}", ""]
        if "paragraph" in prefs:
            lines.append(" ".join(f"{fact.rstrip('.')}. [source: {src}]" for _, fact, src in facts))
        else:
            lines += [f"- {fact.rstrip('.')}. [source: {src}]" for _, fact, src in facts]
        if not facts:
            lines.append("I found nothing relevant in the sources.")
        if feedback:
            lines += ["", f"_Revised after review: {feedback}_"]
        return AIMessage("\n".join(lines))

    return {"clarifier": ScriptedChatModel(responses=[clarify], repeat_last=True),
            "planner": ScriptedChatModel(responses=[plan], repeat_last=True),
            "writer": ScriptedChatModel(responses=[write], repeat_last=True)}


# --- CLI: a run that can be killed ---------------------------------------------------------------------

def _slow(search: DocsSearch, seconds: float) -> DocsSearch:
    def slow_search(query: str) -> list[Finding]:
        print(f"   ...searching docs for {query!r} ({seconds:g}s)", flush=True)
        time.sleep(seconds)
        return search(query)

    return slow_search


async def _run_cli(args: argparse.Namespace) -> int:
    from mastery.graphs.persistence import async_sqlite_checkpointer

    saver = await async_sqlite_checkpointer(args.db)     # async nodes → the async saver
    graph = build_research_graph(offline_models(), web_search=offline_web_search(),
                                 docs_search=_slow(corpus_docs_search(), args.slow), checkpointer=saver)
    config = {"configurable": {"thread_id": args.thread}}
    print(f"PID {__import__('os').getpid()} thread={args.thread}", flush=True)
    # durability="sync": each checkpoint is written before the next step starts, so a kill loses at most
    # the step in progress ("async", the default, may still be writing when the process dies).
    async for part in graph.astream({"question": args.question}, config, stream_mode="updates", subgraphs=True,
                                    durability=args.durability):
        namespace, update = part
        for node in update:
            where = "/".join(ns.split(":")[0] for ns in namespace)
            print(f"STEP {where + '/' if where else ''}{node}", flush=True)
    state = await graph.aget_state(config)
    print("NEXT", list(state.next), "INTERRUPTS", len(state.interrupts), flush=True)
    await saver.conn.close()
    return 0


def run_and_kill(db: str | Path, thread: str, question: str, *, durability: str = "sync", slow: float = 5.0,
                 kill_on: str | None = "searching docs", timeout: float = 120) -> list[str]:
    """Run the CLI in a child process and kill it hard when a line contains ``kill_on``.

    Simulates a crash (power cut, OOM, Ctrl+C in a terminal). ``kill_on=None`` lets it finish.
    Returns the lines it printed. Works on Windows too (``Popen.kill`` = TerminateProcess).
    """
    import os
    import subprocess
    import sys

    cmd = [sys.executable, "-u", "-m", "mastery.graphs.research", "--db", str(db), "--thread", thread,
           "--question", question, "--slow", str(slow), "--durability", durability]
    env = {**os.environ, "PYTHONUTF8": "1"}
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", env=env,
                            cwd=Path(__file__).resolve().parents[3])
    lines: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        lines.append(line.rstrip())
        if kill_on and kill_on in line:
            proc.kill()
            lines.append("💥 killed")
            break
    proc.wait(timeout=timeout)
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Project 08 graph offline with a SQLite checkpointer.")
    parser.add_argument("--db", required=True, help="SQLite checkpoint file")
    parser.add_argument("--thread", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--slow", type=float, default=0.0, help="seconds per docs search (time to kill it)")
    parser.add_argument("--durability", choices=["sync", "async", "exit"], default="sync")
    return asyncio.run(_run_cli(parser.parse_args(argv)))


if __name__ == "__main__":
    # Run the *imported* module, not this __main__ copy: checkpoints must store
    # mastery.graphs.research.Plan (an allowed type), never __main__.Plan.
    from mastery.graphs.research import main as _main

    sys.exit(_main())

