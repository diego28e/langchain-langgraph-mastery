"""A minimal Docker sandbox backend for Deep Agents (Lesson 11.09).

``BaseSandbox`` builds every file tool on top of ``execute()``, so a provider only implements
``execute``, ``upload_files``, ``download_files`` and ``id``. ``DockerSandbox`` does that with the
``docker`` CLI: one locked-down container per instance, no network by default, no host mounts, and
no environment variables from your machine (keys stay outside, in your tools).

For production, prefer a managed provider (LangSmith, Daytona, E2B, Modal, Runloop...): they add
snapshots, TTLs, quotas and audit logs this teaching class does not.
"""
from __future__ import annotations

import shlex
import shutil
import subprocess
import uuid
from collections.abc import Callable, Sequence
from pathlib import PurePosixPath
from typing import Any

from deepagents.backends.protocol import ExecuteResponse, FileDownloadResponse, FileUploadResponse
from deepagents.backends.sandbox import BaseSandbox

Runner = Callable[..., subprocess.CompletedProcess]

DEFAULT_IMAGE = "python:3.12-slim"


def docker_available(runner: Runner = subprocess.run) -> bool:
    """True when the ``docker`` CLI exists and the daemon answers."""
    if shutil.which("docker") is None:
        return False
    try:
        return runner(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


class DockerSandbox(BaseSandbox):
    """Run the agent's ``execute`` and file tools inside a throwaway Docker container.

    Use it as a context manager (``with DockerSandbox() as box:``) so the container is removed.
    """

    def __init__(self, image: str = DEFAULT_IMAGE, *, network: bool = False, memory: str = "512m",
                 cpus: str = "1", pids: int = 128, workdir: str = "/workspace", timeout: int = 60,
                 max_output_chars: int = 20_000, runner: Runner = subprocess.run) -> None:
        self.image, self.network, self.memory, self.cpus, self.pids = image, network, memory, cpus, pids
        self.workdir, self.timeout, self.max_output_chars = workdir, timeout, max_output_chars
        self._run = runner
        self._name = f"m11-sandbox-{uuid.uuid4().hex[:8]}"
        self._started = False

    # ---- lifecycle -------------------------------------------------------------------------
    def run_args(self) -> list[str]:
        """The ``docker run`` command (exposed so you can read exactly what isolation you get)."""
        args = ["docker", "run", "-d", "--rm", "--name", self._name, "--memory", self.memory, "--cpus", self.cpus,
                "--pids-limit", str(self.pids), "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "-w", self.workdir]
        if not self.network:
            args += ["--network", "none"]
        return [*args, self.image, "sleep", "infinity"]

    def start(self) -> DockerSandbox:
        if not self._started:
            done = self._run(self.run_args(), capture_output=True, text=True, timeout=300)
            if done.returncode != 0:
                raise RuntimeError(f"docker run failed: {done.stderr.strip()[:300]}")
            self._started = True
            self.execute(f"mkdir -p {shlex.quote(self.workdir)}")
        return self

    def stop(self) -> None:
        if self._started:
            self._run(["docker", "rm", "-f", self._name], capture_output=True, text=True, timeout=60)
            self._started = False

    def __enter__(self) -> DockerSandbox:
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    @property
    def id(self) -> str:
        return self._name

    # ---- the provider primitives -----------------------------------------------------------
    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        if not self._started:
            self.start()
        limit = timeout or self.timeout
        try:
            done = self._run(["docker", "exec", "-w", self.workdir, self._name, "sh", "-c", command],
                             capture_output=True, text=True, timeout=limit)
        except subprocess.TimeoutExpired:
            return ExecuteResponse(output=f"Error: command timed out after {limit} s", exit_code=124, truncated=False)
        output = (done.stdout or "") + (done.stderr or "")
        truncated = len(output) > self.max_output_chars
        return ExecuteResponse(output=output[: self.max_output_chars], exit_code=done.returncode, truncated=truncated)

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        if not self._started:
            self.start()
        results = []
        for path, content in files:
            parent = shlex.quote(str(PurePosixPath(path).parent))
            done = self._run(["docker", "exec", "-i", self._name, "sh", "-c", f"mkdir -p {parent} && cat > {shlex.quote(path)}"],
                             input=content, capture_output=True, timeout=self.timeout)
            results.append(FileUploadResponse(path=path, error=None if done.returncode == 0 else "permission_denied"))
        return results

    def download_files(self, paths: Sequence[str]) -> list[FileDownloadResponse]:
        if not self._started:
            self.start()
        results = []
        for path in paths:
            done = self._run(["docker", "exec", self._name, "cat", path], capture_output=True, timeout=self.timeout)
            if done.returncode == 0:
                results.append(FileDownloadResponse(path=path, content=done.stdout, error=None))
            else:
                results.append(FileDownloadResponse(path=path, content=None, error="file_not_found"))
        return results
