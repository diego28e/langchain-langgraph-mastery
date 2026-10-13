"""Multi-agent building blocks (Module 09), following docs.langchain.com/oss/python/langchain/multi-agent.

VERIFIED 2026-10-12 against the multi-agent docs (subagents, handoffs, router) with
langchain 1.4.5 / langgraph 1.x. Each helper is the docs pattern with the boilerplate
removed, so lessons can show the raw version once and then use these.

- :class:`Specialist` + :meth:`Specialist.build`: one specialist = name, description,
  system prompt and tools, turned into a ``create_agent`` graph.
- :func:`subagent_tool`: wrap an agent as a tool (subagents pattern). Choose what it sees
  (``context="query"`` isolated, or ``"history"`` forked) and what comes back
  (``output="last"`` final message, or ``"all"`` a short transcript).
- :func:`task_tool`: the single-dispatch variant, ``task(agent_name, description)``, with
  the agent names constrained by an enum.
- :func:`handoff_tool` + :func:`handoff_graph`: handoffs with multiple agent subgraphs
  (``Command(goto=..., graph=Command.PARENT)``) and an ``active_agent`` key.
- :func:`step_tool` + :func:`step_middleware`: handoffs inside ONE agent; middleware swaps
  the system prompt and tools based on ``current_step`` (the form the docs recommend).

Subagents built here get NO checkpointer: they inherit the parent's at runtime, which is
what lets an ``interrupt()`` deep inside a subagent tool pause the outermost graph.
"""
from __future__ import annotations

import enum
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, NotRequired

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import ModelRequest, wrap_model_call
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import Field, create_model

__all__ = [
    "HandoffState",
    "Specialist",
    "StepState",
    "handoff_graph",
    "handoff_tool",
    "step_middleware",
    "step_tool",
    "subagent_tool",
    "task_tool",
]


# --------------------------------------------------------------------------- specialists
@dataclass(frozen=True)
class Specialist:
    """A specialist agent's recipe. ``build(model)`` turns it into a ``create_agent`` graph."""

    name: str
    description: str
    system_prompt: str
    tools: tuple[Any, ...] = field(default_factory=tuple)

    def build(self, model: Any, *, extra_tools: Sequence[Any] = (), middleware: Sequence[Any] = (),
              state_schema: Any = None, checkpointer: Any = None) -> Any:
        """``create_agent`` with this recipe. Leave ``checkpointer`` None for subagents."""
        kwargs: dict[str, Any] = {}
        if state_schema is not None:
            kwargs["state_schema"] = state_schema
        if checkpointer is not None:
            kwargs["checkpointer"] = checkpointer
        return create_agent(model, tools=[*self.tools, *extra_tools], system_prompt=self.system_prompt,
                            middleware=list(middleware), name=self.name, **kwargs)


def _text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    return getattr(message, "text", "") or str(content)


def _transcript(messages: Sequence[Any], limit: int = 12) -> str:
    lines = []
    for m in list(messages)[-limit:]:
        if isinstance(m, HumanMessage):
            lines.append(f"user: {_text(m)}")
        elif isinstance(m, AIMessage):
            calls = ", ".join(c["name"] for c in m.tool_calls)
            lines.append(f"assistant: {_text(m)}" + (f" [called {calls}]" if calls else ""))
        elif isinstance(m, ToolMessage):
            lines.append(f"tool {m.name}: {_text(m)}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- subagents
def subagent_tool(agent: Any, *, name: str, description: str,
                  context: Literal["query", "history"] = "query",
                  output: Literal["last", "all"] = "last") -> BaseTool:
    """Wrap ``agent`` as a tool the coordinator can call (docs: Subagents → tool per agent).

    ``context="query"``: the subagent sees only the query the coordinator wrote (isolated, cheap).
    ``context="history"``: it also sees the coordinator's conversation so far, as a transcript
    in its first message (forked; more tokens, fewer "what is your customer ID?" moments).
    ``output="last"`` returns the final message; ``"all"`` a transcript of the subagent's run.
    """

    def run(query: str, runtime: ToolRuntime) -> str:
        content = query
        if context == "history":
            history = [m for m in runtime.state.get("messages", [])
                       if not (isinstance(m, AIMessage) and m.tool_calls)]
            content = f"Conversation so far:\n{_transcript(history)}\n\nYour task: {query}"
        result = agent.invoke({"messages": [{"role": "user", "content": content}]})
        if output == "all":
            return _transcript(result["messages"][1:])
        return _text(result["messages"][-1])

    run.__doc__ = description
    return tool(name, description=description)(run)


def task_tool(registry: dict[str, tuple[Any, str]], *, name: str = "task") -> BaseTool:
    """One dispatch tool for many subagents: ``task(agent_name, description)``.

    ``registry`` maps agent name -> (agent, one-line description). The names become an enum
    in the tool schema, so the model cannot invent an agent; the descriptions go in the tool
    description (docs: Subagents → single dispatch tool, "system prompt enumeration").
    """
    names = enum.Enum("AgentName", {n: n for n in registry}, type=str)
    listing = "\n".join(f"- {n}: {desc}" for n, (_, desc) in registry.items())

    def run(agent_name: str, description: str) -> str:
        key = getattr(agent_name, "value", agent_name)
        agent = registry[key][0]
        result = agent.invoke({"messages": [{"role": "user", "content": description}]})
        return _text(result["messages"][-1])

    schema = create_model(
        "TaskInput",
        agent_name=(names, Field(description="Which specialist to call.")),
        description=(str, Field(description="A complete, standalone task for the specialist.")),
    )
    return StructuredTool.from_function(
        func=run, name=name, args_schema=schema,
        description=f"Delegate a task to a specialist. Available specialists:\n{listing}")


# --------------------------------------------------------------------------- handoffs (graph)
class HandoffState(AgentState):
    """Shared state for multi-agent handoffs: messages plus who is talking right now."""

    active_agent: NotRequired[str]


def handoff_tool(target: str, *, description: str | None = None, name: str | None = None,
                 carry: Literal["last", "turn"] = "last") -> BaseTool:
    """A ``transfer_to_<target>`` tool that jumps to another agent node in the PARENT graph.

    Returns ``Command(goto=target, graph=Command.PARENT)`` plus the messages the next agent
    should see, always ending in the AIMessage that called this tool and a matching
    ToolMessage, so the tool-call/tool-result pair stays valid (docs: Handoffs → multiple
    agent subgraphs).

    ``carry="last"`` (the docs example) passes only that AIMessage: cheap, but whatever the
    agent did earlier in this turn (tool results!) never reaches the parent state.
    ``carry="turn"`` passes every message since the latest user message, so the next agent
    sees the work already done (and doesn't redo it).
    """
    tool_name = name or f"transfer_to_{target}"

    def run(runtime: ToolRuntime) -> Command:
        messages = list(runtime.state["messages"])
        last_ai = next(m for m in reversed(messages) if isinstance(m, AIMessage))
        carried = [last_ai]
        if carry == "turn":
            start = max((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=-1)
            carried = messages[start + 1:]
            if not carried or carried[-1] is not last_ai:
                carried.append(last_ai)
        transfer = ToolMessage(content=f"Transferred to {target}.", tool_call_id=runtime.tool_call_id,
                               name=tool_name)
        return Command(goto=target, graph=Command.PARENT,
                       update={"active_agent": target, "messages": [*carried, transfer]})

    desc = description or f"Transfer the conversation to the {target} agent."
    run.__doc__ = desc
    return tool(tool_name, description=desc)(run)


def _route_after(state: dict) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and not last.tool_calls:
        return END
    return state.get("active_agent") or END


def handoff_graph(agents: dict[str, Any], *, entry: str, checkpointer: Any = None,
                  state_schema: Any = HandoffState) -> Any:
    """Compile a graph with one node per agent, routed by ``active_agent``.

    A new user turn starts at the agent that was active last (``entry`` the first time),
    an agent's turn ends the graph when it answers without tool calls, and a handoff tool
    jumps between nodes. Give the checkpointer HERE (outermost graph), not to the agents.
    """
    names = list(agents)

    def make_node(agent: Any) -> Callable[[dict], dict]:
        def node(state: dict) -> dict:
            return agent.invoke(state)
        return node

    builder = StateGraph(state_schema)
    for agent_name, agent in agents.items():
        builder.add_node(agent_name, make_node(agent))
    builder.add_conditional_edges(START, lambda s: s.get("active_agent") or entry, names)
    for agent_name in names:
        builder.add_conditional_edges(agent_name, _route_after, [*names, END])
    return builder.compile(checkpointer=checkpointer)


# --------------------------------------------------------------------------- handoffs (one agent)
class StepState(AgentState):
    """State for single-agent handoffs: which configuration (step) is active."""

    current_step: NotRequired[str]


def step_tool(step: str, *, description: str | None = None, name: str | None = None) -> BaseTool:
    """A tool that switches ``current_step``; the next model call gets that step's prompt/tools."""
    tool_name = name or f"transfer_to_{step}"

    def run(runtime: ToolRuntime) -> Command:
        return Command(update={
            "current_step": step,
            "messages": [ToolMessage(content=f"Transferred to {step}.", tool_call_id=runtime.tool_call_id,
                                     name=tool_name)],
        })

    desc = description or f"Hand the conversation to the {step} step."
    run.__doc__ = desc
    return tool(tool_name, description=desc)(run)


def step_middleware(steps: dict[str, dict[str, Any]], *, default: str) -> Any:
    """``@wrap_model_call`` that applies ``steps[current_step]`` = {"prompt": str, "tools": [...]}.

    Register EVERY tool on the agent (``create_agent(tools=all_tools)``); this middleware only
    narrows what each call sees, which is why the agent stays one graph with one checkpoint.
    """

    @wrap_model_call
    def apply_step(request: ModelRequest, handler: Callable) -> Any:
        step = (request.state or {}).get("current_step") or default
        config = steps[step]
        wanted = {t if isinstance(t, str) else t.name for t in config.get("tools", [])}
        tools = [t for t in request.tools if getattr(t, "name", None) in wanted]
        return handler(request.override(system_message=SystemMessage(config["prompt"]), tools=tools))

    return apply_step
