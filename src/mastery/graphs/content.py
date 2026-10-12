"""The Project 07 content pipeline: topic → outline → parallel research → draft → critique ⟲ revise → final.

``build_content_graph`` is the reference graph served by ``apps/m07_content_pipeline`` (``langgraph dev``)
and used by the Project 07 solution. ``offline_models`` returns scripted stand-ins (no key, no network)
whose critique score improves by fixing one issue per revision, so the loop's behaviour is testable.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from mastery.graphs.nodes import loop_router, timed
from mastery.graphs.state import ContentState, Critique, Outline, SectionNote

__all__ = [
    "CRITIC_PROMPT",
    "PLANNER_PROMPT",
    "TEST_TOPICS",
    "WRITER_PROMPT",
    "build_content_graph",
    "corpus_researcher",
    "critic_prompt",
    "offline_models",
    "planner_prompt",
    "web_researcher",
    "writer_prompt",
]

Researcher = Callable[[str], tuple[str, list[str]]]   # question -> (notes, sources)

# The three acceptance-test topics of Project 07 (they match the Module 06 corpus).
TEST_TOPICS = ["Battery care in winter", "Calibrating the sensors", "Mounting the station outdoors"]

PLANNER_PROMPT = ("You plan short, practical blog posts. Return a title and 3 sections. Each section has a heading "
                  "and ONE concrete question that research must answer.")
WRITER_PROMPT = ("You write clear blog posts (300-500 words) in Markdown. Use ONLY the research notes. "
                 "Every section must cite its sources as [source: <name>]. Start with a 2-sentence introduction and "
                 "end with a '## Conclusion' section. When issues are listed, fix all of them and keep what works.")
CRITIC_PROMPT = ("You are a strict editor. Score the draft from 1 to 10 (8 = publishable) and list concrete issues, "
                 "most important first. Check: introduction, every section cites a source, a conclusion, "
                 "no claims beyond the notes.")


def planner_prompt(topic: str) -> list:
    return [SystemMessage(PLANNER_PROMPT), HumanMessage(f"Topic: {topic}")]


def _notes_block(outline: Outline, sections: list[SectionNote]) -> str:
    by_title = {s["title"]: s for s in sections}
    blocks = []
    for plan in outline.sections:                    # outline order, not completion order
        note = by_title.get(plan.title, {"notes": "(no research)", "sources": []})
        blocks.append(f'<notes title="{plan.title}" sources="{", ".join(note["sources"])}">\n{note["notes"]}\n</notes>')
    return "\n".join(blocks)


def writer_prompt(topic: str, outline: Outline, sections: list[SectionNote], draft: str = "",
                  issues: list[str] | None = None) -> list:
    text = f"Topic: {topic}\nTitle: {outline.title}\n\n{_notes_block(outline, sections)}"
    if draft:
        text += f"\n\n<draft>\n{draft}\n</draft>\n\nIssues to fix:\n" + "\n".join(f"- {i}" for i in issues or [])
    return [SystemMessage(WRITER_PROMPT), HumanMessage(text)]


def critic_prompt(topic: str, draft: str) -> list:
    return [SystemMessage(CRITIC_PROMPT), HumanMessage(f"Topic: {topic}\n\n<draft>\n{draft}\n</draft>")]


def build_content_graph(planner: Any, writer: Any, critic: Any, researcher: Researcher, *,
                        max_iterations: int = 3, threshold: int = 8, checkpointer: Any = None, name: str = "content_pipeline"):
    """Compile the pipeline. ``planner``/``critic`` are chat models (used with structured output), ``writer`` a chat model.

    Termination is guaranteed: the loop ends when the critique score reaches ``threshold`` or after
    ``max_iterations`` revisions, whichever comes first.
    """
    plan_model = planner.with_structured_output(Outline)
    critic_model = critic.with_structured_output(Critique)

    @timed("plan_outline")
    def plan_outline(state: ContentState) -> dict:
        return {"outline": plan_model.invoke(planner_prompt(state["topic"])), "iteration": 0}

    def fan_out(state: ContentState) -> list[Send]:
        return [Send("research_section", {"title": s.title, "question": s.question}) for s in state["outline"].sections]

    @timed("research_section")
    def research_section(task: dict) -> dict:
        notes, sources = researcher(task["question"])
        return {"sections": [SectionNote(title=task["title"], notes=notes, sources=sources)]}

    @timed("write_draft")
    def write_draft(state: ContentState) -> dict:
        reply = writer.invoke(writer_prompt(state["topic"], state["outline"], state["sections"]))
        return {"draft": reply.text}

    @timed("critique")
    def critique(state: ContentState) -> dict:
        review = critic_model.invoke(critic_prompt(state["topic"], state["draft"]))
        return {"critique": review, "scores": [review.score]}

    @timed("revise")
    def revise(state: ContentState) -> dict:
        reply = writer.invoke(writer_prompt(state["topic"], state["outline"], state["sections"],
                                            state["draft"], state["critique"].issues))
        return {"draft": reply.text, "iteration": state.get("iteration", 0) + 1}

    @timed("finalize")
    def finalize(state: ContentState) -> dict:
        sources = sorted({src for s in state["sections"] for src in s["sources"]})
        return {"final": state["draft"].rstrip() + "\n\n---\nSources: " + (", ".join(sources) or "none")}

    builder = StateGraph(ContentState)
    for fn in (plan_outline, research_section, write_draft, critique, revise, finalize):
        builder.add_node(fn.__wrapped__.__name__ if hasattr(fn, "__wrapped__") else fn.__name__, fn)
    builder.add_edge(START, "plan_outline")
    builder.add_conditional_edges("plan_outline", fan_out, ["research_section"])
    builder.add_edge("research_section", "write_draft")
    builder.add_edge("write_draft", "critique")
    builder.add_conditional_edges("critique", loop_router(score_key="critique", threshold=threshold,
                                                          max_iterations=max_iterations, again="revise", done="finalize"),
                                  ["revise", "finalize"])
    builder.add_edge("revise", "critique")
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=checkpointer, name=name)


# --- Researchers --------------------------------------------------------------------------------------

_GENERIC = {"nimbu", "station", "orbita", "lab", "guide", "tip", "overview"}


def corpus_researcher(k: int = 6, sentences: int = 3) -> Researcher:
    """Research from the Module 06 corpus (offline, free): BM25 over the chunks, then the best-matching sentences.

    Notes are copied sentences (never invented); sources are the files they came from, most relevant first.
    """
    from mastery.config import find_repo_root
    from mastery.rag import BM25, load_corpus, split_documents
    from mastery.rag.retrieve import terms

    chunks = split_documents(load_corpus(find_repo_root() / "data" / "samples" / "rag" / "corpus"), "markdown", 800, 100)
    bm25 = BM25(chunks)

    def research(question: str) -> tuple[str, list[str]]:
        wanted = set(terms(question)) - _GENERIC
        scored = []
        for rank, doc in enumerate(bm25.search(" ".join(sorted(wanted)) or question, k=k)):
            text = " ".join(doc.page_content.replace("**", "").split())
            for sentence in re.findall(r"[^.!?]+[.!?]", text):
                sentence = sentence.strip().lstrip("#*- ").strip()
                overlap = len(wanted & set(terms(sentence)))
                if overlap and 30 < len(sentence) < 300:
                    scored.append((-overlap, rank, sentence, doc.metadata["source"]))
        best, seen = [], set()
        for item in sorted(scored):
            if item[2] not in seen:
                seen.add(item[2])
                best.append(item)
            if len(best) == sentences:
                break
        if not best:
            return "No source covers this.", []
        sources = list(dict.fromkeys(src for *_, src in best))
        return " ".join(s for _, _, s, _ in best), sources

    return research


def web_researcher(tool: Any) -> Researcher:
    """Research with Module 05's ``web_search`` tool (💸 one Groq browser-search call per section)."""
    def research(question: str) -> tuple[str, list[str]]:
        msg = tool.invoke({"type": "tool_call", "name": tool.name, "args": {"query": question}, "id": "research"})
        sources = [s["url"] for s in (getattr(msg, "artifact", None) or {}).get("sources", [])]
        return str(msg.content)[:2000], sources

    return research


# --- Offline stand-ins ---------------------------------------------------------------------------------

_CITE = re.compile(r"\[source: [^\]]+\]")


def _draft_checks(draft: str) -> dict[str, bool]:
    head, *rest = draft.split("\n## ")
    sections = [s for s in rest if not s.startswith("Conclusion")]
    return {
        "intro": any(line.strip() and not line.lstrip().startswith("#") for line in head.splitlines()),
        "citations": bool(sections) and all(_CITE.search(s) for s in sections),
        "conclusion": any(s.startswith("Conclusion") for s in rest),
    }


_ISSUES = {
    "intro": "Add a 2-sentence introduction before the first section.",
    "citations": "Cite a source in every section as [source: <name>].",
    "conclusion": "End with a '## Conclusion' section.",
}


def offline_models() -> dict[str, Any]:
    """Scripted ``planner``, ``writer`` and ``critic`` (``ScriptedChatModel``s) for the pipeline.

    The writer's first draft has no introduction, citations or conclusion; each revision fixes the
    **first** listed issue only. The critic scores 4 + 2 per check passed, so scores go 4 → 6 → 8.
    """
    from mastery.testing import ScriptedChatModel

    def plan(messages: list) -> AIMessage:
        topic = messages[-1].text.removeprefix("Topic:").strip()
        outline = Outline(title=f"{topic}: a practical guide", sections=[
            {"title": "The basics", "question": f"{topic}: overview"},
            {"title": "Practical tips", "question": f"{topic}: tips"},
            {"title": "Troubleshooting", "question": f"{topic}: troubleshooting"},
        ])
        return AIMessage("", tool_calls=[{"name": "Outline", "id": "p1", "args": outline.model_dump()}])

    def write(messages: list) -> AIMessage:
        text = messages[-1].text
        title = re.search(r"^Title: (.+)$", text, re.MULTILINE).group(1)
        notes = re.findall(r'<notes title="([^"]*)" sources="([^"]*)">\n(.*?)\n</notes>', text, re.DOTALL)
        old = re.search(r"<draft>\n(.*)\n</draft>", text, re.DOTALL)
        issues = re.findall(r"^- (.+)$", text.split("Issues to fix:")[-1], re.MULTILINE) if old else []
        fixed = set()
        if old:   # keep what the old draft already had, fix only the first issue
            fixed = {k for k, ok in _draft_checks(old.group(1)).items() if ok}
            for key, msg in _ISSUES.items():
                if issues and issues[0] == msg:
                    fixed.add(key)
        parts = [f"# {title}"]
        if "intro" in fixed:
            parts.append(f"This post explains {title.split(':')[0].lower()} in three short sections. "
                         "Everything below comes from the Orbita Labs documentation.")
        for heading, sources, body in notes:
            cite = f" [source: {sources.split(', ')[0]}]" if "citations" in fixed and sources else ""
            parts.append(f"## {heading}\n\n{body.strip()}{cite}")
        if "conclusion" in fixed:
            parts.append("## Conclusion\n\nFollow the steps above and check the cited pages for details.")
        return AIMessage("\n\n".join(parts))

    def review(messages: list) -> AIMessage:
        draft = re.search(r"<draft>\n(.*)\n</draft>", messages[-1].text, re.DOTALL).group(1)
        checks = _draft_checks(draft)
        issues = [_ISSUES[k] for k, ok in checks.items() if not ok]
        critique = Critique(score=4 + 2 * sum(checks.values()), issues=issues)
        return AIMessage("", tool_calls=[{"name": "Critique", "id": "c1", "args": critique.model_dump()}])

    return {"planner": ScriptedChatModel(responses=[plan], repeat_last=True),
            "writer": ScriptedChatModel(responses=[write], repeat_last=True),
            "critic": ScriptedChatModel(responses=[review], repeat_last=True)}
