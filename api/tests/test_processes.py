"""A tool the API starts is stopped whole (ADR-0051 amendment 1): the process started, the tool under it and the solver under that."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from anisotropy_api.processes import OWN_GROUP, run_tool, stop_tool

pytestmark = pytest.mark.skipif(os.name != "posix", reason="process groups; on Windows the tree is stopped by taskkill")

# A tool as `uv run` starts one: a process that starts another, which does the work, and waits for it.
TOOL = """
import subprocess, sys, time
worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
with open(sys.argv[1], "w") as said:
    said.write(str(worker.pid))
time.sleep(600)
"""


def running(pid: int) -> bool:
    """Whether a process is still running: one that has ended and waits to be collected is not."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    stat = Path(f"/proc/{pid}/stat")
    return not stat.exists() or stat.read_text().rsplit(")", 1)[1].split()[0] != "Z"


def ended(pid: int, within_s: float = 10.0) -> bool:
    until = time.monotonic() + within_s
    while running(pid) and time.monotonic() < until:
        time.sleep(0.05)
    return not running(pid)


def worker_of(said: Path, within_s: float = 10.0) -> int:
    until = time.monotonic() + within_s
    while (not said.exists() or not said.read_text()) and time.monotonic() < until:
        time.sleep(0.05)
    return int(said.read_text())


def test_a_tool_that_outlasts_its_time_leaves_nothing_running(tmp_path):
    said = tmp_path / "worker"
    with pytest.raises(subprocess.TimeoutExpired):
        run_tool([sys.executable, "-c", TOOL, str(said)], timeout_s=3.0)
    assert ended(worker_of(said)), "the tool's own process was left running after the tool was stopped"


def test_a_job_that_is_stopped_leaves_nothing_running(tmp_path):
    said = tmp_path / "worker"
    process = subprocess.Popen([sys.executable, "-c", TOOL, str(said)], **OWN_GROUP)
    worker = worker_of(said)
    assert running(worker) and process.poll() is None
    stop_tool(process)
    process.wait(timeout=10)
    assert ended(worker)
    stop_tool(process)  # a tool that has ended is left alone


def test_a_tool_that_ends_gives_its_output_and_status(tmp_path):
    done = run_tool([sys.executable, "-c", "import sys; print('said'); print('why', file=sys.stderr); sys.exit(3)"], timeout_s=30.0, cwd=tmp_path)
    assert (done.returncode, done.stdout.strip(), done.stderr.strip()) == (3, "said", "why")
