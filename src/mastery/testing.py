"""mastery.testing: offline stand-ins for chat models (no network, no key, no cost).

Module 02 uses agents everywhere, and ``create_agent`` needs a model that
supports ``bind_tools`` *and* streams tool calls. LangChain's own fakes
(``GenericFakeChatModel``, ``FakeMessagesListChatModel``) raise
``NotImplementedError`` on ``bind_tools`` (checked with langchain-core 1.6.9),
so the course ships its own small one.

``ScriptedChatModel`` replies with a script you write in advance:

>>> from langchain.messages import AIMessage
>>> model = ScriptedChatModel(responses=[
...     AIMessage("", tool_calls=[{"name": "add", "args": {"a": 2, "b": 3}, "id": "call_1"}]),
...     "2 + 3 = 5.",
... ])

Each call to the model takes the next item. An item can be:

- an ``AIMessage`` (with or without ``tool_calls``),
- a ``str`` (becomes ``AIMessage(content=...)``),
- a callable ``f(messages) -> AIMessage | str``, to react to what the agent sent
  (for example, answer with the content of the last ``ToolMessage``).

Used by the 🧪 cells of Module 02 and by ``tests/unit``. It is a *teaching and
testing* tool: it shows the mechanics of the loop, never model quality.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator, Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field, PrivateAttr

__all__ = ["ScriptExhaustedError", "ScriptedChatModel"]

Response = AIMessage | str | Callable[[list[BaseMessage]], "AIMessage | str"]


class ScriptExhaustedError(RuntimeError):
    """The model was called more times than the script has responses."""


class ScriptedChatModel(BaseChatModel):
    """A chat model that returns pre-written responses, in order.

    Attributes:
        responses: The script (see the module docstring).
        calls: Every list of messages the model received, for inspection.
        bound_tools: Tool names from the last ``bind_tools`` call.
        tool_choice: ``tool_choice`` from the last ``bind_tools`` call.
        repeat_last: If True, keep returning the last response instead of
            raising ``ScriptExhaustedError`` (simulates a model stuck in a loop).
    """

    responses: list[Any] = Field(default_factory=list)
    model_name: str = "scripted"
    calls: list[list[BaseMessage]] = Field(default_factory=list)
    bound_tools: list[str] = Field(default_factory=list)
    tool_choice: Any = None
    repeat_last: bool = False
    _position: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted-chat-model"

    # --- tool binding -------------------------------------------------------
    def bind_tools(self, tools: Sequence[Any], *, tool_choice: Any = None, **kwargs: Any) -> ScriptedChatModel:
        """Record which tools the agent offered, then return the same model.

        Real models send the tool schemas to the provider; here we only keep
        the names so a notebook or test can check what the agent bound.
        """
        self.bound_tools = [_tool_name(t) for t in tools]
        self.tool_choice = tool_choice
        return self

    # --- generation ---------------------------------------------------------
    def _next(self, messages: list[BaseMessage]) -> AIMessage:
        if self.repeat_last and self.responses and self._position >= len(self.responses):
            self._position = len(self.responses) - 1
        if self._position >= len(self.responses):
            msg = (
                f"ScriptedChatModel was called {self._position + 1} times but the script has "
                f"{len(self.responses)} responses. Add a response, or check why the agent looped."
            )
            raise ScriptExhaustedError(msg)
        item = self.responses[self._position]
        self._position += 1
        self.calls.append(list(messages))
        if callable(item) and not isinstance(item, BaseMessage):
            item = item(list(messages))
        if isinstance(item, str):
            item = AIMessage(content=item)
        if not isinstance(item, AIMessage):
            msg = f"Script items must be AIMessage, str or callable, got {type(item).__name__}"
            raise TypeError(msg)
        return item.model_copy(update={"usage_metadata": _usage(messages, item)})

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next(messages))])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """Stream like a real provider: tool-call chunks first, then text word by word."""
        message = self._next(messages)
        chunks: list[AIMessageChunk] = []
        for index, call in enumerate(message.tool_calls):
            chunks.append(AIMessageChunk(content="", tool_call_chunks=[{
                "name": call["name"], "args": json.dumps(call["args"]), "id": call["id"], "index": index,
            }]))
        text = message.content if isinstance(message.content, str) else message.text
        chunks.extend(AIMessageChunk(content=piece) for piece in re.findall(r"\S+\s*", text))
        if not chunks:
            chunks.append(AIMessageChunk(content=""))
        chunks[-1] = chunks[-1].model_copy(update={"usage_metadata": message.usage_metadata,
                                                   "chunk_position": "last"})
        for chunk in chunks:
            if run_manager and isinstance(chunk.content, str) and chunk.content:
                run_manager.on_llm_new_token(chunk.content, chunk=ChatGenerationChunk(message=chunk))
            yield ChatGenerationChunk(message=chunk)

    def reset(self) -> None:
        """Start the script again from the first response."""
        self._position = 0
        self.calls.clear()


def _tool_name(tool: Any) -> str:
    if isinstance(tool, dict):
        return str(tool.get("name") or tool.get("function", {}).get("name") or tool.get("type") or tool.get("title"))
    return str(getattr(tool, "name", None) or getattr(tool, "__name__", type(tool).__name__))


def _usage(messages: list[BaseMessage], reply: AIMessage) -> dict[str, int]:
    """Rough token counts (4 characters ≈ 1 token) so cost code has numbers to work with."""
    prompt = sum(len(str(m.content)) for m in messages) // 4 + 10
    completion = len(str(reply.content)) // 4 + 10 * len(reply.tool_calls) + 1
    return {"input_tokens": prompt, "output_tokens": completion, "total_tokens": prompt + completion}
