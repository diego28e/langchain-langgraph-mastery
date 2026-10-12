"""Start and stop ``langgraph dev`` from a notebook (Lesson 07.06, Project 07).

``langgraph dev`` normally runs in its own Git Bash window. From a notebook we start it as a
child process with ``--no-browser --no-reload`` (no reloader child, so ``stop()`` really stops it,
also on Windows), wait for ``/ok``, and stop it when done.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Self

__all__ = ["DevServer", "dev_server_command"]


def dev_server_command(port: int, host: str = "127.0.0.1") -> list[str]:
    """The command line: the CLI module of **this** Python (no PATH surprises on Windows)."""
    return [sys.executable, "-m", "langgraph_cli", "dev", "--no-browser", "--no-reload", "--host", host, "--port", str(port)]


class DevServer:
    """A ``langgraph dev`` child process serving ``app_dir`` (the folder with ``langgraph.json``)."""

    def __init__(self, app_dir: Path, port: int | None = None, *, env: dict[str, str] | None = None,
                 log_path: Path | None = None) -> None:
        if not (Path(app_dir) / "langgraph.json").is_file():
            raise FileNotFoundError(f"No langgraph.json in {app_dir}")
        if port is None:
            from mastery.mcp import free_port

            port = free_port()
        self.app_dir, self.port = Path(app_dir), port
        self.url = f"http://127.0.0.1:{port}"
        self.studio_url = f"https://smith.langchain.com/studio/?baseUrl={self.url}"
        self.log_path = log_path
        self._env = {**os.environ, "PYTHONUTF8": "1", **(env or {})}
        self._proc: subprocess.Popen | None = None
        self._log = None

    def start(self, timeout: float = 90.0) -> Self:
        out = subprocess.DEVNULL
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log = open(self.log_path, "w", encoding="utf-8")   # noqa: SIM115 - closed in stop()
            out = self._log
        self._proc = subprocess.Popen(dev_server_command(self.port), cwd=self.app_dir, env=self._env,
                                      stdout=out, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                self.stop()
                raise RuntimeError(f"langgraph dev exited with code {self._proc.returncode}; see {self.log_path or 'its output'}")
            try:
                with urllib.request.urlopen(f"{self.url}/ok", timeout=2) as resp:
                    if resp.status == 200:
                        return self
            except OSError:
                time.sleep(0.5)
        self.stop()
        raise TimeoutError(f"langgraph dev did not answer on {self.url}/ok within {timeout:.0f}s")

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        if self._log:
            self._log.close()
            self._log = None

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()
