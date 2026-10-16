"""DockerSandbox without Docker: a fake runner turns `docker exec` into a local shell in a temp dir.

This checks our wiring against BaseSandbox (its file tools are shell/python scripts run via execute).
"""
from __future__ import annotations

import subprocess

import pytest

pytest.importorskip("deepagents")

from mastery.deep.sandbox import DockerSandbox, docker_available  # noqa: E402


def fake_runner(tmp_path):
    seen: list[list[str]] = []

    def run(args, **kw):
        seen.append(list(args))
        if args[:2] in (["docker", "run"], ["docker", "rm"]):
            return subprocess.CompletedProcess(args, 0, "id\n" if kw.get("text") else b"id\n", "")
        assert args[:2] == ["docker", "exec"]
        rest = args[2:]
        if rest[0] == "-w":
            rest = rest[2:]
        if rest[0] == "-i":
            rest = rest[1:]
        cmd = rest[1:]                                  # drop the container name
        kw.pop("timeout", None)
        return subprocess.run(cmd, cwd=tmp_path, timeout=30, **kw)

    return run, seen


def test_run_args_are_locked_down():
    args = DockerSandbox().run_args()
    for flag in ("--network", "--cap-drop", "--memory", "--pids-limit", "--rm"):
        assert flag in args
    assert "-v" not in args and "-e" not in args
    assert "--network" not in DockerSandbox(network=True).run_args()


def test_sandbox_round_trip_through_base_sandbox(tmp_path):
    run, seen = fake_runner(tmp_path)
    work = str(tmp_path)
    with DockerSandbox(workdir=work, runner=run) as box:
        assert box.execute("echo hi").output.strip() == "hi"
        assert box.upload_files([(f"{work}/a/b.txt", b"one\ntwo\n")])[0].error is None
        assert box.download_files([f"{work}/a/b.txt"])[0].content == b"one\ntwo\n"
        assert box.download_files([f"{work}/missing"])[0].error == "file_not_found"
        res = box.execute("exit 3")
        assert res.exit_code == 3
        assert "two" in str(box.read(f"{work}/a/b.txt"))
    assert seen[-1][:3] == ["docker", "rm", "-f"]


def test_output_is_truncated(tmp_path):
    run, _ = fake_runner(tmp_path)
    box = DockerSandbox(workdir=str(tmp_path), runner=run, max_output_chars=10)
    res = box.execute("printf '%s' 0123456789abcdef")
    assert res.truncated and res.output == "0123456789"


def test_docker_available_is_false_without_cli(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    assert docker_available() is False
