"""Helpers for MCP in Module 05 (built on the beta ``langchain.mcp`` namespace).

- **Annotations:** :func:`tool_info`, :func:`is_read_only`, :func:`is_destructive`,
  :func:`approval_policy` (human approval for every tool that is not declared read-only).
- **Sources:** :func:`extract_urls`, :func:`urls_from_messages`, :func:`check_sources`
  (an answer may only cite URLs that appeared in tool results).
- **Security:** :func:`tool_fingerprint` (detect a server that changes its tools),
  :func:`poisoned_descriptions` (injection-style text in tool descriptions).
- **Servers:** :func:`serve_http` starts a course MCP server in a child process on
  ``127.0.0.1`` and stops it again (works the same on Windows, macOS and Linux).

Import cost: this module does **not** import ``langchain.mcp``, so it raises no
``LangChainBetaWarning`` by itself.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

from mastery.middleware import injection_signals

__all__ = [
    "DOCS_MCP_URL", "URL_RE", "approval_policy", "check_sources", "extract_urls", "free_port", "is_destructive",
    "is_read_only", "poisoned_descriptions", "serve_http", "tool_fingerprint", "tool_info", "urls_from_messages",
]

#: Public, keyless LangChain docs MCP server (verified 2026-10-12).
DOCS_MCP_URL = "https://docs.langchain.com/mcp"

import re  # noqa: E402  (kept next to the pattern it builds)

#: http(s) URLs, stopping at whitespace, quotes, brackets, backslashes (escaped newlines in JSON) and
#: trailing punctuation.
URL_RE = re.compile(r"https?://[^\s<>\"'`)\]}【】\\]+")
_TRAILING = ".,;:!?*_"


# --- annotations ---------------------------------------------------------------
def _annotations(tool: Any) -> dict[str, Any]:
    return ((getattr(tool, "metadata", None) or {}).get("mcp", {}).get("tool", {}).get("annotations", {})) or {}


def is_read_only(tool: Any) -> bool:
    """True only if the server declared ``readOnlyHint=True``. Missing hint → False (fail closed)."""
    return _annotations(tool).get("read_only_hint") is True


def is_destructive(tool: Any) -> bool:
    """True if the server declared ``destructiveHint=True``, or declared nothing about writes.

    The MCP spec's default for ``destructiveHint`` is ``true`` for tools that are not read-only,
    so a tool with no annotations counts as destructive.
    """
    ann = _annotations(tool)
    if ann.get("read_only_hint") is True:
        return False
    return ann.get("destructive_hint", True) is not False


def tool_info(tools: Iterable[Any]) -> list[dict[str, Any]]:
    """One row per tool: name, server, read_only, destructive, and the first line of its description."""
    rows = []
    for tool in tools:
        server = ((getattr(tool, "metadata", None) or {}).get("mcp", {}).get("server", {}) or {}).get("name")
        rows.append({"name": tool.name, "server": server, "read_only": is_read_only(tool),
                     "destructive": is_destructive(tool),
                     "description": (tool.description or "").strip().splitlines()[0][:80] if tool.description else ""})
    return rows


def approval_policy(tools: Iterable[Any], decisions: Sequence[str] = ("approve", "edit", "reject"),
                    trusted_read_only: Iterable[str] | None = None) -> dict[str, Any]:
    """``interrupt_on`` for ``HumanInTheLoopMiddleware``: pause every tool that is not read-only.

    Args:
        tools: LangChain tools (MCP or not).
        decisions: Allowed decisions for the paused tools.
        trusted_read_only: If given, only these names may skip approval. Use it for
            third-party servers: annotations are *claims* by the server, not guarantees.

    Returns:
        ``{tool_name: False | {"allowed_decisions": [...]}}``.
    """
    allow = set(trusted_read_only) if trusted_read_only is not None else None
    policy: dict[str, Any] = {}
    for tool in tools:
        skip = is_read_only(tool) and (allow is None or tool.name in allow)
        policy[tool.name] = False if skip else {"allowed_decisions": list(decisions)}
    return policy


# --- sources -------------------------------------------------------------------
def extract_urls(text: Any) -> list[str]:
    """Unique http(s) URLs in ``text`` (any object is ``str()``-ed or JSON-dumped), in order."""
    if not isinstance(text, str):
        try:
            text = json.dumps(text, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            text = str(text)
    seen: dict[str, None] = {}
    for match in URL_RE.findall(text):
        url = match.rstrip(_TRAILING)
        if len(url) > len("https://x"):
            seen.setdefault(url, None)
    return list(seen)


def urls_from_messages(messages: Iterable[Any], skip_tools: Iterable[str] = ()) -> list[str]:
    """Every URL that appeared in a tool result: ``ToolMessage`` content and artifact, and
    Groq ``executed_tools`` on AI messages (server-side browser search).

    ``skip_tools``: tool names to ignore. Pass your structured-output schema name (e.g. ``{"Answer"}``)
    with ``ToolStrategy``: its "Returning structured response: ..." ToolMessage echoes the model's own
    sources, which must not count as evidence for themselves.
    """
    skip = set(skip_tools)
    found: dict[str, None] = {}
    for message in messages:
        parts: list[Any] = []
        if getattr(message, "type", None) == "tool" and getattr(message, "name", None) not in skip:
            parts += [message.content, getattr(message, "artifact", None)]
        executed = (getattr(message, "additional_kwargs", None) or {}).get("executed_tools")
        if executed:
            parts.append(executed)
        for part in parts:
            if part is not None:
                for url in extract_urls(part):
                    found.setdefault(url, None)
    return list(found)


def _normalize(url: str) -> str:
    url = url.strip().rstrip("/")
    return url.split("#")[0].rstrip("/").lower()


def check_sources(sources: Iterable[str], seen: Iterable[str]) -> tuple[list[str], list[str]]:
    """Split ``sources`` into (grounded, invented).

    A source is grounded if, ignoring case, a trailing slash and the ``#fragment``, it equals a URL
    seen in a tool result. Anything else counts as invented, even if the page exists.
    """
    known = {_normalize(u) for u in seen}
    grounded, invented = [], []
    for url in sources:
        (grounded if _normalize(url) in known else invented).append(url)
    return grounded, invented


# --- security --------------------------------------------------------------------
def _annotations(tool: Any) -> dict[str, Any]:
    """The MCP annotations (read-only, destructive, ... hints) the adapter stored on a tool.

    Only the annotations: ``_meta`` is library-specific (FastMCP adds its own keys), so hashing it
    would change the fingerprint on a library upgrade without any change on the server.
    """
    mcp = ((getattr(tool, "metadata", None) or {}).get("mcp") or {}).get("tool") or {}
    return {k: v for k, v in sorted((mcp.get("annotations") or {}).items()) if v is not None}


def tool_fingerprint(tools: Iterable[Any], *, instructions: str | None = None) -> str:
    """A SHA-256 over every tool's name, description, argument schema and MCP annotations.

    Save it when you review a server; compare it on every connect. A change means the server
    changed what your agent will see or how your policy treats it (a "rug pull", or a
    ``readOnlyHint`` flip that would move a tool from "ask" to "auto"), so review again before
    trusting it. Pass the server's ``instructions`` to cover them too. A library upgrade can also
    change the hash (for example a different argument-schema rendering): treat that as "review
    again", which fails closed.
    """
    rows = sorted(
        (t.name, t.description or "", json.dumps(getattr(t, "args", {}) or {}, sort_keys=True, default=str),
         json.dumps(_annotations(t), sort_keys=True, default=str))
        for t in tools
    )
    payload = {"tools": rows, "instructions": instructions} if instructions is not None else rows
    return hashlib.sha256(json.dumps(payload).encode("utf-8")).hexdigest()


def _poison_signals(text: str) -> list[str]:
    signals = injection_signals(text)
    if re.search(r"<\s*(important|system|secret)\s*>|do not (tell|mention|show) the user", text, re.I):
        signals.append("hidden_instruction")
    return signals


def poisoned_descriptions(tools: Iterable[Any], *, instructions: str | None = None) -> dict[str, list[str]]:
    """``{tool_name: signals}`` for tool descriptions (and argument descriptions) that contain
    injection-style instructions (Lesson 04.05 patterns). Pass the server's ``instructions`` to
    scan them too (reported under ``"__instructions__"``). Empty dict = nothing found."""
    flagged = {}
    for tool in tools:
        signals = _poison_signals((tool.description or "") + " " + json.dumps(getattr(tool, "args", {}) or {}, default=str))
        if signals:
            flagged[tool.name] = signals
    if instructions and (signals := _poison_signals(instructions)):
        flagged["__instructions__"] = signals
    return flagged


# --- local servers ----------------------------------------------------------------
def free_port() -> int:
    """A free TCP port on 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(port: int, process: subprocess.Popen, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            out = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"MCP server exited with code {process.returncode}:\n{out[-2000:]}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise TimeoutError(f"MCP server did not open port {port} within {timeout:.0f}s.")


@contextlib.contextmanager
def serve_http(module: str = "mastery.mcp_servers.notes_server", *, port: int | None = None,
               env: dict[str, str] | None = None, args: Sequence[str] = (), timeout: float = 30.0) -> Iterator[str]:
    """Run a course MCP server over HTTP in a child process; yield its URL; stop it on exit.

    The child is this interpreter (``sys.executable``), so it uses the same environment as your
    kernel. It listens on ``127.0.0.1`` only (no firewall prompt on Windows, not reachable from
    your network).

    Args:
        module: Module run with ``python -m`` (must accept ``--transport http --host --port``).
        port: Port to use. Default: a free one.
        env: Extra environment variables for the child (for example ``MASTERY_NOTES_TOKENS``).
        args: Extra command-line arguments.
        timeout: Seconds to wait for the port to open.

    Yields:
        The server URL, for example ``http://127.0.0.1:53211/mcp``.
    """
    port = port or free_port()
    src = str(Path(__file__).resolve().parents[1])
    child_env = {**os.environ, **(env or {}), "PYTHONIOENCODING": "utf-8", "FASTMCP_SHOW_CLI_BANNER": "false"}
    child_env["PYTHONPATH"] = src + os.pathsep + child_env.get("PYTHONPATH", "")
    cmd = [sys.executable, "-m", module, "--transport", "http", "--host", "127.0.0.1", "--port", str(port), *args]
    process = subprocess.Popen(cmd, env=child_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               encoding="utf-8", errors="replace")
    try:
        _wait_for_port(port, process, timeout)
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        if process.stdout:
            process.stdout.close()
