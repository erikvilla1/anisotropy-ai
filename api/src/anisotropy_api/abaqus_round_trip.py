"""A coupon through the user's own Abaqus and back, from one sentence (ADR-0094, step 4; ADR-0048). Nothing here computes a result.

    uv run --project api python -m anisotropy_api.abaqus_round_trip "build this coupon in Abaqus and compare" \\
        --coupon <coupon>.toml --folder <work>

Runs on the machine that has Abaqus. The work is done by `fea/tools/abaqus_tools.py`, three fixed commands (build, run, send) whose
arguments our code derives from the coupon's spec. This module only decides which of the three run:

- With the assistant on (ANISOTROPY_ASSISTANT_PROVIDER, ADR-0052), the model is given the sentence, the three tools' names and
  descriptions, and the names of those already done in the folder. It answers with names in a fixed schema. `tool_guard` keeps the
  names on offer, once each, in the tools' own order. The model sees no file, no path, no coupon and no result (ADR-0094, part 6),
  and nothing it writes reaches a command: a name is looked up, never passed on.
- With the assistant off, or when the model gives no answer, the sentence is not read and every step that is not done runs, in order.
  The reason is said.

The tools then refuse a chain with a gap, run, and write each call to the folder's record with who chose it and the sentence. The
verdict and every number are printed by the tools from tested code; none passes through the model (ADR-0001).

Exit code: the tools' own (0 the bundle agrees with ours, 1 it differs, 2 refused), and 2 when nothing was chosen.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .assistant import Assistant, assistant_for
from .coupon_jobs import FEA
from .settings import assistant_settings, environment

TOOL = FEA / "tools" / "abaqus_tools.py"
MAX_MESSAGE = 2000  # characters of the engineer's sentence the model is given
STATE_TIMEOUT_S = 300.0


class RoundTripRefused(Exception):
    pass


@dataclass
class Chosen:
    """What of the model's answer stands: the tools kept, in the tools' own order, and what was dropped with the reason."""

    tools: list[str] = field(default_factory=list)
    dropped: list[dict[str, str]] = field(default_factory=list)


def tool_command() -> list[str]:
    """`uv run --project fea python fea/tools/abaqus_tools.py`, as the API starts every tool of the fea package."""
    uv = shutil.which("uv")
    if uv is None:
        raise RoundTripRefused("uv is not on PATH; the tools run fea/tools/abaqus_tools.py through `uv run --project fea`")
    return [uv, "run", "--project", str(FEA), "python", str(TOOL)]


def view_of(message: str, told: dict[str, Any]) -> dict[str, Any]:
    """What the model may see: the sentence, each tool's name and description, and the names of the tools already done. No file, path,
    coupon name or result (ADR-0094, part 6)."""
    done = {"build": told["state"]["built"], "run": told["state"]["ran"], "send": told["state"]["sent"]}
    return {"message": message[:MAX_MESSAGE], "tools": [{"name": tool["name"], "description": tool["description"]} for tool in told["tools"]],
            "done": [tool["name"] for tool in told["tools"] if done.get(tool["name"])]}


def tool_guard(raw: dict[str, Any], offered: list[str]) -> Chosen:
    """The names of the model's answer that are tools on offer, once each, in the order the tools are offered in: a model is built
    before its job runs, whatever order the answer gives. Anything else in the answer is dropped with the reason and never used."""
    chosen = Chosen()
    seen: set[str] = set()
    answer = raw.get("tools")
    for item in (answer if isinstance(answer, list) else [])[:len(offered) + 5]:
        name = item if isinstance(item, str) else ""
        if name not in offered:
            chosen.dropped.append({"name": str(item)[:40], "reason": "not a tool on offer"})
        elif name in seen:
            chosen.dropped.append({"name": name, "reason": "chosen twice; once stands"})
        else:
            seen.add(name)
    chosen.tools = [name for name in offered if name in seen]
    for key in raw:
        if key != "tools":
            chosen.dropped.append({"name": str(key)[:40], "reason": "not part of the answer asked for"})
    return chosen


def remaining(told: dict[str, Any]) -> list[str]:
    done = {"build": told["state"]["built"], "run": told["state"]["ran"], "send": told["state"]["sent"]}
    return [tool["name"] for tool in told["tools"] if not done.get(tool["name"])]


def start(argv: list[str], capture: bool) -> subprocess.CompletedProcess:
    """One tool of the fea package, waited for. `capture` for the state's JSON; otherwise its lines go straight to the terminal."""
    if capture:
        return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=STATE_TIMEOUT_S, check=False)
    return subprocess.run(argv, check=False)


def round_trip(message: str, coupon: Path, folder: Path, assistant: Assistant, abaqus: str | None = None,
               runner: Callable[[list[str], bool], Any] = start, say: Callable[[str], None] = print) -> int:
    """Choose among the three tools for `message` and run the chosen ones. Returns the exit code; raises `RoundTripRefused` with the
    reason when nothing could be started."""
    command = tool_command()
    asked = runner([*command, "state", str(coupon), "--folder", str(folder), "--json"], True)
    if asked.returncode != 0:
        raise RoundTripRefused((asked.stderr or asked.stdout or "the tools gave no state").strip())
    try:
        told = json.loads(asked.stdout)
        offered = [str(tool["name"]) for tool in told["tools"]]
        left = remaining(told)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RoundTripRefused(f"the tools' state could not be read: {exc}") from exc
    if not left:
        say("Every step is already done in this folder; use an empty folder for another round trip.")
        return 2
    reading = assistant.choose_tools(view_of(message, told))
    if reading.raw is None:
        tools, chosen_by = left, "template"
        why = reading.reason or "the assistant is off"
        say(f"Your words were not read ({why}), so every step that is not done runs: {', '.join(tools)}.")
    else:
        kept = tool_guard(reading.raw, offered)
        for dropped in kept.dropped:
            say(f"Left out of the assistant's answer: {dropped['name']} ({dropped['reason']}).")
        tools, chosen_by = kept.tools, f"{reading.writer} ({reading.model})" if reading.model else reading.writer
        if not tools:
            say(f"The assistant found none of the steps in your words. They are: {', '.join(offered)}.")
            return 2
        say(f"The assistant chose: {', '.join(tools)}.")
    argv = [*command, "plan", str(coupon), "--folder", str(folder), "--tools", *tools, "--chosen-by", chosen_by, "--asked", message[:MAX_MESSAGE]]
    if abaqus:
        argv += ["--abaqus", abaqus]
    return int(runner(argv, False).returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m anisotropy_api.abaqus_round_trip", description=__doc__.splitlines()[0])
    parser.add_argument("message", help='what you want, in your own words, such as "build this coupon in Abaqus and compare"')
    parser.add_argument("--coupon", type=Path, required=True, help="the coupon's spec (.toml)")
    parser.add_argument("--folder", type=Path, required=True, help="the work folder of this round trip; one coupon, one folder")
    parser.add_argument("--abaqus", default=None, help="the Abaqus command; default ANISOTROPY_ABAQUS, then abaqus on PATH")
    args = parser.parse_args(argv)
    try:
        settings = assistant_settings(environment())
        return round_trip(args.message, args.coupon, args.folder, assistant_for(settings.provider, settings.model), args.abaqus)
    except (RoundTripRefused, RuntimeError) as exc:
        print(f"refused:\n  {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
