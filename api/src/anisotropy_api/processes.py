"""A tool the API starts, and stops whole (ADR-0051 amendment 1).

The fea package's tools run in processes of their own (ADR-0051), started through `uv run`. That makes a small tree: uv, the
tool's Python and, for a solve, CalculiX. Killing the process the API started kills uv alone. The tool and the solver are left
running with nobody waiting for them: they keep a processor and their memory until they end by themselves, after the page has
been told the run took too long. So a tool is started as the leader of a process group of its own, and stopping it stops the
group. On Windows, where a local API runs, the tree is stopped by the system's own `taskkill`.
"""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path

POSIX = os.name == "posix"
# Popen's arguments that make a tool the leader of its own process group, so the group's id is the tool's process id.
OWN_GROUP: dict = {"start_new_session": True} if POSIX else {}


def stop_tool(process: subprocess.Popen) -> None:
    """Kill a tool started with `OWN_GROUP` and everything it started. A tool that has already ended is left alone, and so is its
    group, whose id the system may have given to another by then."""
    if process.poll() is not None:
        return
    try:
        if POSIX:
            os.killpg(process.pid, signal.SIGKILL)
        else:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass
    try:  # the tool itself, whatever became of the group: it is ours to end
        process.kill()
    except OSError:
        pass


def run_tool(args: list[str], *, timeout_s: float, cwd: str | Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    """`subprocess.run` for a tool with its output kept as text: run to its end, or stopped whole when it outlasts `timeout_s`, and
    `subprocess.TimeoutExpired` raised as `subprocess.run` raises it."""
    with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", cwd=cwd, env=env,
                          **OWN_GROUP) as process:
        try:
            out, err = process.communicate(timeout=timeout_s)
        except BaseException:  # the time allowed, or whatever stopped the wait: nothing of the tool is left running
            stop_tool(process)
            raise
    return subprocess.CompletedProcess(args, process.returncode, out, err)
