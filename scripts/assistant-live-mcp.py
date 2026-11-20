"""The MCP half of the real-model check (ADR-0121, check 2): each question a bank answers with one of our tools is put to a model acting as
an engineer's own assistant, with the MCP server's tools and instructions, and the server answers it in process from the stored results
the tests use (the stand-in API of `mcp-server/tests/conftest.py`), so no solver runs. Whether the model calls the tool the bank names,
with its arguments, is checked here; its last words go to the judge in `assistant-live.py`, which starts this script:

    uv run --project mcp-server --with "anthropic>=1,<2" python scripts/assistant-live-mcp.py --questions q.json --store DIR --out a.json

A conversation's turns depend on each other, so they are sent one after another, each stored under its exact request like every other
answer; the conversations themselves go on at the same time, `AT_ONCE` of them. Exits 3 when the budget stopped one, with what was done
written out."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

import httpx
from mcp import Client

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "mcp-server" / "tests")]

from assistant_live_common import AT_ONCE, OverBudget, Spend, Store, key_of, reply, resolve  # noqa: E402
from conftest import FakeApi  # noqa: E402
from test_server import VALUES  # noqa: E402

from anisotropy_mcp.api import Api  # noqa: E402
from anisotropy_mcp.server import INSTRUCTIONS, build  # noqa: E402

ON_A_RESULT = {"result_values", "result_extreme", "explain_result", "show_working"}
TURNS = 6
# The coupon of VALUES, as an engineer would state it to their assistant.
SETUP = ("I am setting up an unnotched tension coupon, sized from an example: 250 by 25 mm with 56 mm tabs, IM7/8552 from the library, "
         "layup [45/0/-45/90]s, symmetric, loaded by a 1 mm displacement, G13 4688.43 MPa and G23 3000 MPa. Filled by A. Engineer on 2026-11-17.")


def block(content: dict[str, Any]) -> dict[str, Any] | None:
    """A stored content block as the next request sends it back."""
    kind = content.get("type")
    if kind == "text":
        return {"type": "text", "text": content["text"]}
    if kind == "tool_use":
        return {"type": "tool_use", "id": content["id"], "name": content["name"], "input": content["input"]}
    if kind == "thinking":
        return {"type": "thinking", "thinking": content.get("thinking", ""), "signature": content["signature"]}
    if kind == "redacted_thinking":
        return {"type": "redacted_thinking", "data": content["data"]}
    return None


def called_as_asked(calls: list[dict[str, Any]], asked: dict[str, Any]) -> bool:
    for call in calls:
        if call["name"] != asked["tool"]:
            continue
        given = call["input"]
        if all((key in given) if value == "example" else given.get(key) == value for key, value in asked["args"].items()):
            return True
    return False


async def talk(question: dict[str, Any], model: str, store: Store, spend: Spend, client: Any) -> dict[str, Any]:
    asked = question["mcp"]
    context = asked.get("context") or ("solved" if asked["tool"] in ON_A_RESULT else None)
    server = build(Api("http://127.0.0.1:8000", transport=httpx.MockTransport(FakeApi())))
    async with Client(server) as session:
        tools = [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in (await session.list_tools()).tools]
        messages: list[dict[str, Any]] = []
        if context == "solved":
            solved = await session.call_tool("solve_coupon", {"values": VALUES})
            messages += [{"role": "user", "content": SETUP + " Solve it."},
                         {"role": "assistant", "content": [{"type": "tool_use", "id": "toolu_context_1", "name": "solve_coupon", "input": {"values": VALUES}}]},
                         {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_context_1", "content": solved.content[0].text}]},
                         {"role": "assistant", "content": "It is solved; its result is r1."}]
        messages.append({"role": "user", "content": f"{SETUP}\n\n{question['ask']}" if context == "setup" else question["ask"]})
        calls: list[dict[str, Any]] = []
        final = ""
        for _ in range(TURNS):
            params = {"model": model, "max_tokens": 4000, "system": INSTRUCTIONS, "tools": tools, "messages": messages, "output_config": {"effort": "low"}}
            key = key_of(params)
            await asyncio.to_thread(resolve, client, {key: params}, store, spend, batch=False, log=print)
            answer = store.get(key)
            if answer is None:
                return {"id": question["id"], "tools": calls, "final": final, "faults": ["the model gave no answer in this run"]}
            message = reply(answer)
            final = "".join(b.text for b in message.content if b.type == "text").strip()
            messages.append({"role": "assistant", "content": [b for b in map(block, answer["content"]) if b]})
            uses = [b for b in answer["content"] if b["type"] == "tool_use"]
            if message.stop_reason != "tool_use" or not uses:
                break
            results = []
            for use in uses:
                result = await session.call_tool(use["name"], use["input"])
                text = result.content[0].text if result.content else ""
                calls.append({"name": use["name"], "input": use["input"], "refused": bool(result.is_error)})
                results.append({"type": "tool_result", "tool_use_id": use["id"], "content": text, **({"is_error": True} if result.is_error else {})})
            messages.append({"role": "user", "content": results})
    faults = [] if called_as_asked(calls, asked) else [f"did not call {asked['tool']} with {json.dumps(asked['args'])}; called {[c['name'] for c in calls] or 'nothing'}"]
    return {"id": question["id"], "tools": calls, "final": final, "faults": faults}


async def talk_all(questions: list[dict[str, Any]], model: str, store: Store, spend: Spend, client: Any) -> tuple[list[dict[str, Any]], str | None]:
    """Every conversation, `AT_ONCE` at a time; the answers in the questions' order. One the budget stops is left out and named."""
    gate = asyncio.Semaphore(AT_ONCE)

    async def one(question: dict[str, Any]) -> dict[str, Any]:
        async with gate:
            return await talk(question, model, store, spend, client)

    done = await asyncio.gather(*(one(q) for q in questions), return_exceptions=True)
    stopped = next((str(r) for r in done if isinstance(r, OverBudget)), None)
    failed = next((r for r in done if isinstance(r, BaseException) and not isinstance(r, OverBudget)), None)
    if failed is not None:
        raise failed
    return [r for r in done if isinstance(r, dict)], stopped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--budget", type=float, required=True)
    parser.add_argument("--spent", type=float, default=0.0)
    args = parser.parse_args()
    import anthropic

    logging.getLogger("httpx").setLevel(logging.WARNING)  # the stand-in API's every call is not news
    store, spend = Store(args.store), Spend(args.budget, args.spent)
    client = anthropic.Anthropic(max_retries=4)
    results, stopped = asyncio.run(talk_all(json.loads(args.questions.read_text(encoding="utf-8")), args.model, store, spend, client))
    args.out.write_text(json.dumps({"spent": spend.dollars, "sent": len(store.sent), "stored": len(store.used - store.sent), "stopped": stopped,
                                    "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 3 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
