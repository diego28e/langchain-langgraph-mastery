"""Readable, safe rendering of chat messages in Jupyter (rich display).

Introduced in Module 01, Lesson 01.02 ("Messages and standard content blocks").

Why this module exists:
    ``print(ai_message)`` dumps a long repr that hides what matters. Jupyter
    can render HTML, so :func:`show_message` displays the answer, the reasoning
    (collapsed), tool calls and token usage as a small card. The HTML is built
    by :func:`render_message_html`, a pure function that unit tests can check
    without Jupyter. All text is HTML-escaped, so model output can never inject
    markup or scripts into your notebook.
"""

from __future__ import annotations

import html
import json
from typing import Any

__all__ = ["message_summary", "render_message_html", "show_message"]


def message_summary(message: Any) -> dict[str, Any]:
    """Extract the parts of a LangChain message you usually want to see.

    Uses ``content_blocks`` (the provider-agnostic view, Lesson 01.02), so the
    same code works for Groq, OpenAI, Gemini or a fake test model.

    Args:
        message: Any LangChain message (``AIMessage``, ``HumanMessage``...).

    Returns:
        A dict with ``type``, ``text``, ``reasoning``, ``tool_calls``,
        ``usage``, ``model_name`` and ``finish_reason``.
    """
    blocks = getattr(message, "content_blocks", None) or []
    reasoning = "\n".join(b.get("reasoning", "") for b in blocks if b.get("type") == "reasoning").strip()
    metadata = getattr(message, "response_metadata", None) or {}
    return {
        "type": getattr(message, "type", type(message).__name__),
        "text": getattr(message, "text", "") or "",
        "reasoning": reasoning,
        "tool_calls": list(getattr(message, "tool_calls", None) or []),
        "usage": getattr(message, "usage_metadata", None),
        "model_name": metadata.get("model_name"),
        "finish_reason": metadata.get("finish_reason"),
    }


def _shorten(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[:max_chars] + f" … [{len(text) - max_chars} more characters]"


def render_message_html(message: Any, *, max_chars: int = 1_500) -> str:
    """Return an HTML card for a message. Every value is escaped.

    Args:
        message: Any LangChain message.
        max_chars: Longer texts are cut (the full text stays in the object).

    Returns:
        An HTML string.
    """
    info = message_summary(message)
    esc = html.escape
    rows = [f"<div><b>{esc(str(info['type']))}</b>"]
    if info["model_name"]:
        rows.append(f" · <code>{esc(str(info['model_name']))}</code>")
    if info["finish_reason"]:
        rows.append(f" · finish_reason=<code>{esc(str(info['finish_reason']))}</code>")
    rows.append("</div>")
    if info["text"]:
        rows.append(f"<pre style='white-space:pre-wrap'>{esc(_shorten(info['text'], max_chars))}</pre>")
    if info["reasoning"]:
        rows.append(
            "<details><summary>reasoning</summary>"
            f"<pre style='white-space:pre-wrap'>{esc(_shorten(info['reasoning'], max_chars))}</pre></details>"
        )
    for call in info["tool_calls"]:
        args = json.dumps(call.get("args", {}), ensure_ascii=False)
        rows.append(f"<div>🔧 <code>{esc(str(call.get('name')))}({esc(args)})</code> id={esc(str(call.get('id')))}</div>")
    if info["usage"]:
        usage = info["usage"]
        reasoning_tokens = (usage.get("output_token_details") or {}).get("reasoning")
        extra = f" ({reasoning_tokens} reasoning)" if reasoning_tokens else ""
        rows.append(
            f"<div style='color:gray'>tokens: {usage.get('input_tokens')} in · "
            f"{usage.get('output_tokens')} out{esc(extra)} · {usage.get('total_tokens')} total</div>"
        )
    return "<div style='border:1px solid #ccc;border-radius:6px;padding:8px;margin:4px 0'>" + "".join(rows) + "</div>"


def show_message(message: Any, *, max_chars: int = 1_500) -> None:
    """Display a message as an HTML card in Jupyter (falls back to print elsewhere).

    Args:
        message: Any LangChain message.
        max_chars: Longer texts are cut in the display.
    """
    try:
        from IPython.display import HTML, display
    except ImportError:  # Plain Python: print a readable summary instead.
        print(message_summary(message))
        return
    display(HTML(render_message_html(message, max_chars=max_chars)))
