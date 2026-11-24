"""The real-model check of the assistant (ADR-0121, check 2): every question of the banks that a model reads on the hosted site is put to
the API's own readers with the site's model, the page's answer is drawn from what they return, and a small judge model grades the
answers a bank describes in words. Questions an MCP client answers with our tools go through `assistant-live-mcp.py`. The report says,
feature by feature, what holds, what is weak and what fails, and what changed since the last run.

What keeps it cheap: an answer is stored under the exact request, so a run pays only for requests whose question, instructions, schema
or model changed since the last; the rest go in one batch at half price, with the instructions cached; the judge is the small model;
and the run stops before it would pass its budget. `--now` sends everything at once at full price instead, for a report in minutes
rather than when the batch ends. `--dry-run` counts the requests still to pay for and sends nothing.

    uv run --project api python scripts/assistant-live.py [--features coupon-setup,result-values] [--budget 3] [--now] [--dry-run]

It needs ANTHROPIC_API_KEY. The GitHub workflow "Assistant check" runs it by hand, before a feature is merged.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from assistant_live_common import JUDGE_MODEL, VERDICTS, OverBudget, Spend, Store, judge_request, key_of, reply, resolve  # noqa: E402

READERS_MODEL = "claude-opus-5-5"  # the hosted site's (ANISOTROPY_ASSISTANT_MODEL there)
CLIENT_MODEL = "claude-sonnet-5-5"  # stands in for an engineer's own assistant on the MCP server



class Capture(Exception):
    """Raised inside the API by the stand-in client for a request with no stored answer: the run collects it, asks, and asks the API again."""

    def __init__(self, key: str, params: dict[str, Any]):
        super().__init__(key)
        self.key, self.params = key, params


class StoredModel:
    """Stands in for the Anthropic client inside the API's readers: answers each request from the store, or captures it."""

    def __init__(self, store: Store):
        self.store = store
        self.messages = self

    @property
    def beta(self) -> StoredModel:
        return self

    def create(self, **params: Any) -> Any:
        key = key_of(params)
        self.store.used.add(key)
        answer = self.store.get(key)
        if answer is None:
            raise Capture(key, params)
        return reply(answer)


def node(script: str, *args: str) -> Any:
    out = subprocess.run(["npx", "tsx", f"tests/assistant-questions/{script}", *args], cwd=ROOT, check=True, capture_output=True, text=True)
    return json.loads(out.stdout)


def ask_readers(questions: list[dict[str, Any]], store: Store, spend: Spend, client: Any, batch: bool, dry: bool) -> tuple[dict[str, list], dict[str, Any]]:
    """Each question's requests through the API, in the page's order: a question of the results first, the setup's proposals only when
    that reading kept nothing. Returns the readings by question; on a dry run, none, and the first round's requests still to pay for."""
    from fastapi.testclient import TestClient

    from anisotropy_api.assistant import ClaudeAssistant
    from anisotropy_api.main import app

    model = StoredModel(store)
    app.state.assistant = ClaudeAssistant((os.environ.get("ANISOTROPY_ASSISTANT_MODEL") or READERS_MODEL), client=model)
    api = TestClient(app, headers={"X-Anisotropy-Actor": "studio"})  # no lifespan: nothing recorded, no database

    def post(request: dict[str, Any]) -> dict[str, Any]:
        response = api.post(f"/v1/workspace/{request['reader']}", json=request["body"])
        if response.status_code != 200:
            raise RuntimeError(f"/v1/workspace/{request['reader']} answered {response.status_code}: {response.text[:300]}")
        return response.json()

    readings: dict[str, list] = {q["id"]: [] for q in questions}
    pending = [(q, 0) for q in questions if q["requests"]]
    while pending:
        for _ in range(3):  # a reader that asks twice is captured again on the replay
            wanted: dict[str, dict[str, Any]] = {}
            for q, i in pending:
                try:
                    post(q["requests"][i])
                except Capture as capture:
                    wanted[capture.key] = capture.params
            if dry:
                return readings, {k: p for k, p in wanted.items() if store.get(k) is None}
            if not wanted:
                break
            resolve(client, wanted, store, spend, batch=batch)
        following = []
        for q, i in pending:
            request = q["requests"][i]
            try:
                response = post(request)
                readings[q["id"]].append({"reader": request["reader"], "response": response})
            except Capture:
                readings[q["id"]].append({"reader": request["reader"], "response": None, "error": "the model gave no answer in this run"})
                continue
            nothing = response.get("request") is None and not response.get("question")
            if request["reader"] == "result-questions" and nothing and i + 1 < len(q["requests"]):
                following.append((q, i + 1))
        pending = following
    return readings, {}


def ask_mcp(questions: list[dict[str, Any]], folder: Path, spend: Spend, now: bool) -> dict[str, Any]:
    """The MCP questions, in the MCP server's own environment with the SDK added for the run: an engineer's assistant on our tools."""
    asked = folder / "mcp-questions.json"
    asked.write_text(json.dumps(questions, ensure_ascii=False), encoding="utf-8")
    out = folder / "mcp-answers.json"
    command = ["uv", "run", "--project", "mcp-server", "--with", "anthropic>=1,<2", "python", "scripts/assistant-live-mcp.py", "--questions", str(asked),
               "--store", str(folder), "--out", str(out), "--model", CLIENT_MODEL, "--budget", f"{spend.budget:.4f}", "--spent", f"{spend.dollars:.6f}"]
    done = subprocess.run(command, cwd=ROOT, env={k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"})  # the MCP server's own environment
    if done.returncode not in (0, 3) or not out.exists():
        raise RuntimeError("the MCP half of the run failed; its output is above")
    return json.loads(out.read_text(encoding="utf-8"))


def verdict_of(faults: list[str], graded: dict[str, Any] | None) -> tuple[str, str]:
    if faults:
        return "fails", "; ".join(faults)
    if graded is None:
        return "holds", ""
    return graded["verdict"], graded["why"] + (f" (criteria {', '.join(map(str, graded['criteria']))})" if graded.get("criteria") else "")


def report(rows: list[dict[str, Any]], before: dict[str, str], header: list[str]) -> str:
    lines = [*header, "", "| Feature | Asked | Holds | Weak | Fails |", "| --- | ---: | ---: | ---: | ---: |"]
    features = sorted({r["feature"] for r in rows})
    for feature in features:
        mine = [r for r in rows if r["feature"] == feature]
        counts = [sum(r["verdict"] == v for r in mine) for v in VERDICTS]
        lines.append(f"| {feature} | {len(mine)} | {counts[0]} | {counts[1]} | {counts[2]} |")
    changed = [r for r in rows if r["key"] in before and before[r["key"]] != r["verdict"]]
    if changed:
        lines += ["", "## Changed since the last run", ""]
        lines += [f"- {r['feature']}: “{r['ask']}”: {before[r['key']]} → {r['verdict']}" for r in changed]
    lines += ["", "## What does not hold", ""]
    for feature in features:
        bad = [r for r in rows if r["feature"] == feature and r["verdict"] != "holds"]
        if not bad:
            continue
        lines += [f"### {feature}", ""]
        for r in bad:
            known = f" Known gap: {r['gap']}." if r.get("gap") else ""
            aside = f" Set aside by the API: {r['aside']}." if r.get("aside") else ""
            lines.append(f"- **{r['verdict']}**: “{r['ask']}” ({r['where']}). {r['why']}.{known}{aside} Shown: {r['shown']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--features", default="", help="banks to run, by feature, comma separated; every live bank when empty")
    parser.add_argument("--budget", type=float, default=3.0, help="the most this run may spend, in dollars")
    parser.add_argument("--store", type=Path, default=ROOT / ".local" / "assistant-live", help="where answers are kept between runs")
    parser.add_argument("--report", type=Path, default=None, help="where the report goes (default: in the store's folder)")
    parser.add_argument("--now", action="store_true", help="send everything at once at full price rather than in a half-price batch: done in minutes, about twice the cost")
    parser.add_argument("--no-mcp", action="store_true", help="leave out the questions an MCP client answers")
    parser.add_argument("--dry-run", action="store_true", help="count the requests still to pay for and send nothing")
    args = parser.parse_args()

    store, spend = Store(args.store), Spend(args.budget)
    wanted = {f.strip() for f in args.features.split(",") if f.strip()}
    questions = [q for q in node("requests.ts") if not wanted or q["feature"] in wanted]
    unknown = wanted - {q["feature"] for q in questions}
    if unknown:
        print(f"No live question in a bank named {', '.join(sorted(unknown))}.", file=sys.stderr)
        return 2
    if not os.environ.get("ANTHROPIC_API_KEY") and not args.dry_run:
        print("ANTHROPIC_API_KEY is not set: the run asks the model with the key the workflow's secret holds.", file=sys.stderr)
        return 2
    import anthropic

    client = anthropic.Anthropic(max_retries=4) if not args.dry_run else None
    readers = [q for q in questions if q["requests"]]
    mcp = [q for q in questions if q["mcp"] and not args.no_mcp]
    try:
        readings, still = ask_readers(readers, store, spend, client, batch=not args.now, dry=args.dry_run)
        if args.dry_run:
            dollars = sum(Spend.estimate(p, batch=not args.now) for p in still.values())
            print(f"{len(readers)} questions for the API's readers and {len(mcp)} for an MCP client. {len(still)} of the readers' first requests "
                  f"are not stored yet, about ${dollars:.2f} on the high side; a question of the results the model reads as none adds a "
                  "proposals request, and each MCP question takes two to four turns of its client's model. Nothing was sent.")
            return 0
        shown = node("shown.ts", str(_write(args.store / "readings.json", [{"id": q["id"], "feature": q["feature"], "ask": q["ask"], "readings": readings[q["id"]]} for q in readers])))
        mcp_out = ask_mcp(mcp, args.store, spend, args.now) if mcp else {"spent": spend.dollars, "results": [], "stopped": None}
        spend.dollars = mcp_out["spent"]
        by_id = {q["id"]: q for q in questions}
        to_judge: dict[str, dict[str, Any]] = {}
        items = []
        for s in shown:
            q = by_id[s["id"]]
            said = s["said"]
            item = None
            if (q["live"] or {}).get("judge") or said["kind"] == "why":
                item = {"question": q["ask"], "page": q["page"], "the chat showed": {"heading": said["heading"], "lines": said["lines"]},
                        "a good answer": (q["live"] or {}).get("judge") or "Answers why in one to three short sentences from the result's facts"}
            # an answer the API's guard set aside shows no prose of the model's; its reason says why, which the page never shows
            aside = "; ".join(r["response"]["reason"] for r in readings[s["id"]] if (r.get("response") or {}).get("withheld") and r["response"].get("reason"))
            items.append((q, s, "chat", f"{q['page']} page", " · ".join([said["heading"], *said["lines"]])[:300], s["faults"], item, aside))
        for m in mcp_out["results"]:
            q = by_id[m["id"]]
            final = m["final"] or ""
            # what the tools returned goes with them: a number the answer quotes from there is the engine's, not typed (criterion 4)
            item = {"question": q["ask"], "where": "an engineer's own assistant, on our MCP server's tools",
                    **({"what the engineer told it before the question": m["before"]} if m.get("before") else {}),
                    **({"what its tools returned before the question": m["held"]} if m.get("held") else {}), "tools it called": m["tools"],
                    "its answer": final, "a good answer": (q["live"] or {}).get("judge") or f"Answers from what {q['mcp']['tool']} returned, its numbers as given"}
            items.append((q, m, "mcp", "MCP client", final[:300].replace("\n", " "), m["faults"], item, ""))
        for _, _, _, _, _, faults, item, _ in items:
            if item is not None and not faults:
                request = judge_request(JUDGE_MODEL, item)
                to_judge[key_of(request)] = request
        resolve(client, to_judge, store, spend, batch=not args.now)
    except OverBudget as exc:
        print(f"Stopped before sending: {exc}.", file=sys.stderr)
        return 3

    rows = []
    for q, _, side, where, shown_text, faults, item, aside in items:
        graded = None
        if item is not None and not faults:
            answer = store.get(key_of(judge_request(JUDGE_MODEL, item)))
            text = "".join(block.get("text", "") for block in answer["content"] if block.get("type") == "text") if answer else ""
            try:
                graded = json.loads(text)
            except json.JSONDecodeError:
                graded = {"verdict": "weak", "criteria": [], "why": "the judge gave no grade in this run"}
        verdict, why = verdict_of(faults, graded)
        rows.append({"key": f"{q['id']}:{side}", "feature": q["feature"], "ask": q["ask"], "where": where, "verdict": verdict, "why": why.rstrip("."),
                     "shown": shown_text, "gap": q.get("gap"), "aside": aside})
    summary = args.store / "summary.json"
    before = json.loads(summary.read_text(encoding="utf-8")) if summary.exists() else {}
    header = [f"# Assistant check with a real model, {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC", "",
              f"Readers: {(os.environ.get('ANISOTROPY_ASSISTANT_MODEL') or READERS_MODEL)}; MCP client: {CLIENT_MODEL}; judge: {JUDGE_MODEL}. "
              f"Spent ${spend.dollars:.2f} of ${args.budget:.2f}: {len(store.sent) + mcp_out.get('sent', 0)} requests sent, "
              f"{len(store.used - store.sent) + mcp_out.get('stored', 0)} answered from the store."]
    if mcp_out.get("stopped"):
        header.append(f"The MCP questions stopped early: {mcp_out['stopped']}.")
    text = report(rows, before, header)
    out = args.report or args.store / "report.md"
    out.write_text(text, encoding="utf-8")
    summary.write_text(json.dumps({**before, **{r["key"]: r["verdict"] for r in rows}}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(text)
    # an answer that held and now fails changed for a reason: a stored answer is replayed as it was, so only a changed request differs
    worse = [r for r in rows if before.get(r["key"]) == "holds" and r["verdict"] == "fails"]
    if worse:
        print(f"{len(worse)} answers held at the last run and fail now.", file=sys.stderr)
    return 1 if worse else 0


def _write(path: Path, data: Any) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


if __name__ == "__main__":
    sys.exit(main())
