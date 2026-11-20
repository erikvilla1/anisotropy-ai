"""The question banks of the assistant (ADR-0121), as an MCP client's model meets them: a question a bank answers with one of our tools
is put to that tool, on the result the stand-in API returns, and its answer must hold what the bank says. Every tool is asked about by
at least one question, so a new tool fails here until a bank asks something it answers. The banks are `tests/assistant-questions/`;
the page's side is `tests/assistant-questions.test.ts`, the API's `api/tests/test_assistant_questions.py`. Nothing here calls a model."""

import json
from pathlib import Path

import pytest

from conftest import Refused
from test_server import TOOLS, VALUES

BANKS = Path(__file__).resolve().parents[2] / "tests" / "assistant-questions"
LIVE = [bank for bank in (json.loads(path.read_text(encoding="utf-8")) for path in sorted(BANKS.glob("*.json"))) if not bank.get("waiting")]
ASKED = [(bank["feature"], q) for bank in LIVE for q in bank["questions"] if q.get("mcp")]
ON_A_RESULT = {"result_values", "result_extreme", "explain_result", "show_working"}  # tools that read a result the server holds


def compact(answer) -> str:
    return str(answer) if isinstance(answer, Refused) else json.dumps(answer, separators=(",", ":"), ensure_ascii=False)


def test_every_tool_is_asked_about():
    named = {q["mcp"]["tool"] for _, q in ASKED}
    assert len(ASKED) >= 10 and named <= set(TOOLS), f"tools the server does not offer: {sorted(named - set(TOOLS))}"
    assert set(TOOLS) <= named, f"tools no question asks about: {sorted(set(TOOLS) - named)}; add questions that a client's model answers with them"


@pytest.mark.parametrize(("feature", "question"), ASKED, ids=lambda v: v["ask"] if isinstance(v, dict) else v)
def test_a_question_answered_by_a_tool_gets_what_its_bank_says(call, feature, question):
    asked = question["mcp"]
    args = {key: VALUES if key == "values" and value == "example" else value for key, value in asked["args"].items()}
    steps = [("solve_coupon", {"values": VALUES})] if asked["tool"] in ON_A_RESULT else []
    if asked["tool"] in ON_A_RESULT:
        args = {"result_id": "r1", **args}
    answer = call(*steps, (asked["tool"], args))[-1]
    text = compact(answer)
    found = [f"refused: {text[:200]}" if isinstance(answer, Refused) != bool(asked.get("refused")) else None]
    found += [f"does not say {says}" for says in asked.get("says", []) if says not in text]
    found = [f for f in found if f]
    where = f"{feature}: “{question['ask']}” ({asked['tool']})"
    if str(question.get("gap", "")).startswith("mcp:"):
        assert found, f"{where}: the gap “{question['gap']}” is closed; take the mark off"
    else:
        assert not found, f"{where}: {'; '.join(found)}"
