"""The guard on the model's words (ADR-0139): an answer that calls the design safe or certified, or says the laminate holds where the
engine says it fails (or the reverse), is set aside for the template. Checked on the public example coupon's fact sheet, whose every
criterion holds, and on copies of it with a criterion flipped to fail. Nothing here calls a model."""

import json
from pathlib import Path

import pytest

from anisotropy_api.assistant import ClaudeAssistant, TemplateAssistant
from anisotropy_api.general_answers import general_guard
from anisotropy_api.result_answers import answer_guard
from anisotropy_api.verdict_guard import Verdicts, verdict_guard, verdicts_of

from test_result_answers import StubClient

EXAMPLE = json.loads((Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "studio" / "explanation.json").read_text(encoding="utf-8"))
HOLDS = EXAMPLE["facts"]  # max_stress and tsai_hill both hold at the applied loading
FAILS = {**HOLDS, "max_stress_fails": True, "tsai_hill_fails": True}
MIXED = {**HOLDS, "tsai_hill_fails": True}  # holds by maximum stress, fails by Tsai-Hill


def test_the_verdicts_are_the_fact_sheets_own_and_none_without_them():
    assert verdicts_of(HOLDS) == Verdicts({"max_stress": False, "tsai_hill": False})
    assert verdicts_of(MIXED) == Verdicts({"max_stress": False, "tsai_hill": True})
    assert verdicts_of(None) is None and verdicts_of({}) is None
    assert verdicts_of({"criteria": []}) is None
    assert verdicts_of({"criteria": ["tsai_hill"]}) is None  # no verdict written for it: nothing to hold the words to
    assert verdicts_of({"criteria": ["tsai_hill"], "tsai_hill_fails": "no"}) is None


def test_the_templates_own_sentences_pass():
    assert verdict_guard(" ".join(EXAMPLE["sentences"]), HOLDS).ok
    assert verdict_guard(" ".join(EXAMPLE["setup_sentences"]), None).ok


@pytest.mark.parametrize("prose, facts", [
    ("The laminate holds at the applied loading; ply 4 would fail first at 1.032 times it.", HOLDS),
    ("By Tsai-Hill the laminate holds at the applied loading.", HOLDS),
    ("The coupon fails first in ply 4, at 1.032 times the applied loading.", HOLDS),  # when it would fail, not whether it does now
    ("It fails at 1.032 times the applied loading.", HOLDS),
    ("The factor of safety is applied to the loads.", HOLDS),  # a term, not a verdict
    ("The laminate holds by maximum stress but fails by Tsai-Hill.", MIXED),  # each clause held to the criterion it names
    ("By maximum stress the laminate holds at the applied loading.", MIXED),
    ("By Tsai-Hill the laminate fails at the applied loading.", MIXED),
    ("The 90 degree plies carry little load, so they fail first.", HOLDS),
    ("The top grip holds the coupon.", FAILS),  # a grip holding is not the laminate holding
    ("If the width were 20 mm the laminate would fail.", HOLDS),  # a supposition states no verdict
    ("Ply 4 is the first to fail by transverse tension.", HOLDS),
    ("The laminate fails at the applied loading.", FAILS),
    ("Every ply fails at the applied loading.", FAILS),
])
def test_an_answer_that_keeps_to_the_engines_verdict_stands(prose, facts):
    guarded = verdict_guard(prose, facts)
    assert guarded.ok, guarded.reason


@pytest.mark.parametrize("prose, facts, said", [
    ("The laminate fails at the applied loading.", HOLDS, "laminate fails"),
    ("The laminate holds at the applied loading.", FAILS, "laminate holds"),
    ("The laminate holds at the applied loading.", MIXED, "laminate holds"),  # no criterion named: held to all of them
    ("By Tsai-Hill the coupon survives the applied loading.", MIXED, "coupon survives"),
    ("No ply fails at the applied loading.", FAILS, "No ply fails"),
    ("The specimen does not fail.", FAILS, "specimen does not fail"),
])
def test_an_answer_against_the_engines_verdict_is_set_aside(prose, facts, said):
    guarded = verdict_guard(prose, facts)
    assert not guarded.ok and said in guarded.offending
    assert "against the engine's verdict at the applied loading" in guarded.reason


@pytest.mark.parametrize("prose, word", [
    ("The laminate is safe.", "safe"),
    ("This coupon is unsafe at the applied loading.", "unsafe"),
    ("The design is strong enough for flight.", "strong enough"),
    ("The repair is airworthy.", "airworthy"),
    ("The part can be certified as it is.", "certified"),
    ("You are good to go.", "good to go"),
    ("An engineer can sign off on this layup.", "sign off"),
])
def test_an_answer_that_decides_for_the_engineer_is_set_aside_with_or_without_a_result(prose, word):
    for facts in (HOLDS, FAILS, None):
        guarded = verdict_guard(prose, facts)
        assert not guarded.ok and word in [w.lower() for w in guarded.offending]
        assert "which no analysis here decides: the engineer does" in guarded.reason


def test_with_no_verdicts_only_the_deciding_words_are_read():
    assert verdict_guard("The laminate fails at the applied loading.", None).ok  # nothing to hold it to
    assert verdict_guard("The laminate holds.", {"criteria": ["tsai_hill"]}).ok
    assert verdict_guard("", HOLDS).ok and verdict_guard(None, HOLDS).ok


# --------------------------------------------------------------------------------------------- where the guard stands

def test_a_why_answer_against_the_verdict_is_set_aside_with_its_reason():
    kept = answer_guard({"answer": "The laminate fails at the applied loading because ply 4 cracks.", "sections": [], "covered": False},
                        "does it fail?", HOLDS, [])
    assert kept.prose == () and kept.withheld and "against the engine's verdict" in kept.reason
    safe = answer_guard({"answer": "The coupon is safe.", "sections": [], "covered": False}, "is it safe?", HOLDS, [])
    assert safe.withheld and "the engineer does" in safe.reason


def test_a_general_answer_that_calls_a_design_safe_is_set_aside_and_its_start_kept():
    kept = general_guard({"answer": "A quasi-isotropic layup is safe for a wing.", "sections": [], "covered": False, "start": "coupon"},
                         "is quasi-isotropic safe?", [], ["coupon"])
    assert kept.prose == () and kept.withheld and kept.start == "coupon" and "the engineer does" in kept.reason


def test_the_claude_writer_falls_back_to_the_template_when_the_words_are_against_the_verdict():
    template = EXAMPLE["sentences"]
    writer = ClaudeAssistant("claude-opus-5-5", client=StubClient("The laminate fails at the applied loading."))
    draft = writer.explain_result(HOLDS, template)
    assert draft.writer == "template" and draft.model is None and draft.withheld and list(draft.prose) == template
    assert "laminate fails" in draft.offending and "against the engine's verdict" in draft.reason
    kept = ClaudeAssistant("claude-opus-5-5", client=StubClient("The laminate holds at the applied loading."))
    assert kept.explain_result(HOLDS, template).writer == "anthropic"
    assert TemplateAssistant().explain_result(FAILS, template).prose == tuple(template)  # the template is never judged: it is the engine's
