"""The question banks of the assistant (ADR-0121), as the API meets them: the theory sections a question of why finds, what a model's
reading of a question may name, and that every route the chat's readers reach is asked about. The banks are the JSON files in
`tests/assistant-questions/`; the page's side is `tests/assistant-questions.test.ts`, the MCP server's `mcp-server/tests/test_questions.py`.
Nothing here calls a model."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anisotropy_api.main import app
from anisotropy_api.result_answers import SECTIONS_SHOWN
from anisotropy_api.result_questions import KINDS, QUANTITIES, SENSES
from anisotropy_api.theory import find, repair_sections, sections, wing_sections

BANKS = Path(__file__).resolve().parents[2] / "tests" / "assistant-questions"
ALL = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(BANKS.glob("*.json"))]
LIVE = [bank for bank in ALL if not bank.get("waiting")]
QUESTIONS = [(bank["feature"], q) for bank in LIVE for q in bank["questions"]]

# Every route under /v1/workspace/ and the questions that reach it. A new route fails the last test below until a bank asks something
# that reaches it and a line here says which.
REACHED_BY = {
    "/v1/workspace/assistant": lambda q: True,  # the page asks once whether a model reads; every question meets it
    "/v1/workspace/proposals": lambda q: bool(q.get("live", {}).get("proposals") or q.get("live", {}).get("plate")),
    "/v1/workspace/result-questions": lambda q: bool(q.get("live", {}).get("request")),
    "/v1/workspace/result-answers": lambda q: q["route"] == "why",
    "/v1/workspace/theory-sections": lambda q: bool(q.get("sections")),
    "/v1/workspace/questions": lambda q: q["route"] == "general",  # the FEA assistant of a blank project (ADR-0124)
}


def search_gap(question: dict) -> bool:
    return str(question.get("gap", "")).startswith("search:")


def test_the_banks_are_there_and_the_theory_pages_hold_every_section_a_bank_names():
    assert len(LIVE) >= 10 and len(QUESTIONS) >= 150
    ids = {section.id for section in sections()}
    named = {s for _, q in QUESTIONS for s in q.get("sections", [])}
    assert named and named <= ids, f"sections no theory page holds: {sorted(named - ids)}"


@pytest.mark.parametrize(("feature", "question"), [(f, q) for f, q in QUESTIONS if q.get("sections")], ids=lambda v: v["ask"] if isinstance(v, dict) else v)
def test_a_question_of_why_finds_the_section_that_holds_its_reason_among_those_a_model_is_shown(feature, question):
    # the wing's chat searches its theory and the reference pages (ADR-0127, ADR-0128); the repair's its own theory and its page (ADR-0136)
    among = wing_sections() if feature == "wing" else repair_sections() if feature == "repair" else None
    found = [section.id for section, _ in find(question["ask"], among=among, limit=SECTIONS_SHOWN)]
    missing = [s for s in question["sections"] if s not in found]
    if search_gap(question):
        assert missing, f"{feature}: “{question['ask']}”: the gap “{question['gap']}” is closed; take the mark off"
    else:
        assert not missing, f"{feature}: “{question['ask']}” finds {found}, not {missing}"


def test_what_a_bank_expects_a_model_to_read_is_inside_what_the_page_offers_it():
    for feature, question in QUESTIONS:
        request = question.get("live", {}).get("request")
        if not request:
            continue
        where = f"{feature}: “{question['ask']}”"
        assert request["kind"] in KINDS, where
        assert set(request.get("quantities", [])) <= set(QUANTITIES), where
        assert request.get("sense") in (None, *SENSES), where
        assert all(isinstance(p, int) and p >= 1 for p in request.get("plies", [])), where


def test_every_route_the_chats_readers_reach_is_asked_about():
    routes = sorted({route.path for route in app.routes if getattr(route, "path", "").startswith("/v1/workspace/")})
    unmapped = [path for path in routes if path not in REACHED_BY]
    assert not unmapped, f"workspace routes with no questions: {unmapped}; add questions that reach them and a line in REACHED_BY"
    unasked = [path for path, reaches in REACHED_BY.items() if path in routes and not any(reaches(q) for _, q in QUESTIONS)]
    assert not unasked, f"routes no question reaches: {unasked}"
