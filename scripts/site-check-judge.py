"""The site check's judge (ADR-0138): each answer the robot read on the live site that passed every fixed check is graded by the small
model against the eleven criteria of the `chat-answer-quality` skill and what the question's bank says a good answer holds, with the
judge and the instructions of the real-model check (ADR-0121). A grade is kept under the exact request, so an answer the site gives
word for word as before is graded again for nothing; only a new or changed answer is paid for, and nothing is sent past the budget.

    uv run --project api python scripts/site-check-judge.py --asked <work>/asked.json --store <store> --out <work>/judged.json [--budget 0.5]

The budget is what the run's cap leaves after the site's model, unless given.

It needs ANTHROPIC_API_KEY (the workflow gives it the question checker's key). `--dry-run` counts what would be sent.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from assistant_live_common import JUDGE_MODEL, OverBudget, Spend, Store, judge_request, key_of, resolve  # noqa: E402

BANKS = ROOT / "tests" / "assistant-questions"
KEEP_DAYS = 45  # a grade no run has used for this long is dropped: a question rotated out is asked again within a month
SHOWN = 4000  # characters of an answer the judge sees, shown and folded each: more than any answer the page gives
PAGES = {
    "start": "the FEA start page, before any work is set up",
    "blank": "a blank coupon",
    "setup": "a coupon given its material and layup on the customer's setup screen, not yet checked; the screen takes the geometry from the "
    "standard and previews first-ply failure before any run",
    "ready": "a coupon checked and ready to run",
    "results": "a solved coupon with its results on the page",
    "past": "a past run opened read-only",
    "wing": "the example wing worked by hand",
    "wing-caps": "the example wing with spar caps added by their button, the same along the span, so no ply drop",
    "repair": "the example flush stepped repair worked by hand",
    "repair-solved": "the example repair with its slice solved",
    "repair-external": "the example repair bonded on top over a hole",
}
SHAPES = {  # criterion 1 of the skill: the kind of question sets the shape of a good answer
    "value": "the value as the heading, with its place",
    "which": "names the ply or the place first",
    "yes-no": "starts with Yes or No, then the one relation that makes it so",
    "what-is": "says what the thing is and where it sits",
    "why": "one to three short sentences from the result's facts",
    "change": "a proposal the engineer ticks or applies, nothing changed until then",
    "command": "does what was asked, or says plainly why not",
    "off-topic": "a short honest decline that says what can be asked",
}


def bank_questions() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(BANKS.glob("*.json")):
        bank = json.loads(path.read_text(encoding="utf-8"))
        for i, question in enumerate(bank["questions"], start=1):
            out[f"{bank['feature']}#{i}"] = question
    return out


def expectation(question: dict[str, Any], model_read: bool) -> str:
    """What a good answer holds, in words: the bank's own words for a model's answer, else its expected page answer, else the shape."""
    live = question.get("live") or {}
    parts = [f"A {question['kind']} question: {SHAPES.get(question['kind'], 'answers what was asked')}."]
    if live.get("judge"):
        parts.append(live["judge"])
    expected = question.get("answer") or {}
    if not model_read or not live.get("judge"):
        if expected.get("heading"):
            parts.append(f"The page's own answer is headed “{expected['heading']}” (numbers in it are of another coupon and may differ).")
        if expected.get("opens"):
            parts.append(f"It opens with “{expected['opens']}”.")
        if expected.get("says"):
            parts.append("It says: " + "; ".join(f"“{w}”" for w in expected["says"]) + " (numbers may differ).")
    if expected.get("never"):
        parts.append("It never says: " + "; ".join(f"“{w}”" for w in expected["never"]) + ".")
    return " ".join(parts)


def item_of(result: dict[str, Any], question: dict[str, Any]) -> dict[str, Any]:
    answer = result["answer"]
    item: dict[str, Any] = {"question": result["ask"]}
    if result.get("after"):
        item["asked before it in the same chat"] = result["after"]
    item["where"] = f"the live site, as a customer sees it: {PAGES.get(result['page'], result['page'])}"
    item["the chat showed"] = {
        "heading": answer["heading"],
        "text": answer["shown"][:SHOWN],
        **({"folded under Details": answer["folded"][:SHOWN]} if answer.get("folded") else {}),
    }
    if answer.get("interim"):
        item["the chat showed first, then replaced once the page had worked"] = answer["interim"]["heading"]
    item["a good answer"] = expectation(question, result["modelRead"])
    if result.get("foreign"):
        item["a good answer"] += (
            f" The question quotes {', '.join(result['foreign'])}, the bank example's numbers; this result's own differ, so judge the yes or no "
            "against the numbers the answer gives."
        )
    item["note"] = (
        "Every number in the answer was checked separately against what the engine sent the page; do not grade whether a number "
        "is right. Do not grade length or polish: grade whether the engineer could act on it without asking again."
    )
    return item


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--asked", type=Path, required=True, help="what the robot read, from scripts/site-check/run.ts")
    parser.add_argument("--store", type=Path, required=True, help="where grades are kept between runs")
    parser.add_argument(
        "--budget", type=float, default=None, help="the most the judge may spend, in dollars (default: the run's cap less the site's spend)"
    )
    parser.add_argument("--out", type=Path, required=True, help="where the grades go")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    asked = json.loads(args.asked.read_text(encoding="utf-8"))
    questions = bank_questions()
    budget = args.budget if args.budget is not None else max(0.0, asked["run"]["cap"] - asked["run"]["siteSpent"])
    store, spend = Store(args.store), Spend(budget)
    requests: dict[str, dict[str, Any]] = {}
    keys: dict[str, str] = {}
    for result in asked["questions"]:
        failed = any(check["level"] == "fails" for check in result["checks"])
        if not result["asked"] or failed or result["id"] not in questions:
            continue
        request = judge_request(JUDGE_MODEL, item_of(result, questions[result["id"]]))
        keys[result["id"]] = key_of(request)
        requests[keys[result["id"]]] = request
    missing = {k: r for k, r in requests.items() if store.get(k) is None}
    print(f"{len(requests)} answers to grade, {len(missing)} not graded before.")
    if args.dry_run:
        return 0
    stopped = None
    if missing:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            stopped = "no key for the judge (ANTHROPIC_API_KEY)"
        else:
            import anthropic

            try:
                resolve(anthropic.Anthropic(max_retries=4), requests, store, spend, batch=False)
            except OverBudget as exc:
                stopped = f"the judge stopped before its budget: {exc}"
    else:
        store.used.update(requests)
    grades: dict[str, Any] = {}
    for qid, key in keys.items():
        answer = store.get(key)
        if answer is None:
            continue
        text = "".join(block.get("text", "") for block in answer["content"] if block.get("type") == "text")
        try:
            graded = json.loads(text)
            grades[qid] = {
                "verdict": graded["verdict"],
                "criteria": [int(c) for c in graded.get("criteria", [])],
                "why": str(graded.get("why", "")),
            }
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            grades[qid] = {"verdict": "weak", "criteria": [], "why": "the judge gave no grade in this run"}
    # a grade this run used is kept another KEEP_DAYS; one no run used for that long goes. When each was last used is kept in a file of
    # its own: the store travels between runs as an artifact, whose files need not keep their times (ADR-0138 amendment 2)
    now = time.time()
    used_file = args.store / "grades-used.json"
    try:
        last_used: dict[str, float] = json.loads(used_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        last_used = {}
    for path in store.folder.glob("*.json"):
        if path.stem in keys.values():
            last_used[path.stem] = now
        elif now - last_used.setdefault(path.stem, now) > KEEP_DAYS * 86400:
            path.unlink()
            del last_used[path.stem]
    used_file.write_text(
        json.dumps({k: round(v) for k, v in sorted(last_used.items()) if (store.folder / f"{k}.json").exists()}), encoding="utf-8"
    )
    args.out.write_text(
        json.dumps({"grades": grades, "spent": round(spend.dollars, 6), "sent": len(store.sent), "stopped": stopped}, indent=1),
        encoding="utf-8",
    )
    print(f"Graded {len(grades)}; sent {len(store.sent)} for ${spend.dollars:.4f}." + (f" {stopped}." if stopped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
