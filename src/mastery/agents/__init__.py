"""mastery.agents: agent helpers (Module 02) and multi-agent building blocks (Module 09).

- :mod:`mastery.agents.loop` (Module 02): run, inspect and display a single agent loop.
  Everything that used to live in ``mastery/agents.py`` is re-exported here unchanged.
- :mod:`mastery.agents.specialists` (Module 09): specialist factories, subagent tools,
  handoff tools/graphs and the single-agent "step" middleware.
- :mod:`mastery.agents.metrics` (Module 09): count model calls, tokens and latency per agent.
- :mod:`mastery.agents.support` (Module 09): the Orbita Cloud support desk used by
  Lessons 09.02-09.05 and Project 09 (tools, specialists, offline models, test set, scoring).
"""
from mastery.agents.loop import (
    LoopLimitError,
    agent_stats,
    execute_tool_calls,
    format_stream_part,
    format_transcript,
    run_tool_loop,
)
from mastery.agents.metrics import UsageMeter
from mastery.agents.specialists import (
    HandoffState,
    Specialist,
    StepState,
    handoff_graph,
    handoff_tool,
    step_middleware,
    step_tool,
    subagent_tool,
    task_tool,
)

__all__ = [
    "HandoffState",
    "LoopLimitError",
    "Specialist",
    "StepState",
    "UsageMeter",
    "agent_stats",
    "execute_tool_calls",
    "format_stream_part",
    "format_transcript",
    "handoff_graph",
    "handoff_tool",
    "run_tool_loop",
    "step_middleware",
    "step_tool",
    "subagent_tool",
    "task_tool",
]
