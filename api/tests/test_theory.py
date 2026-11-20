"""The theory pages as sections found by a question's words (ADR-0102, proposed): the split, the ranking, and that nothing is found for
words the pages do not hold."""

from __future__ import annotations

import json
import re
from pathlib import Path

from anisotropy_api.theory import MAX_SECTION_CHARS, SOURCES, find, of_subject, sections, split, wing_sections, words_of

REPO = Path(__file__).resolve().parents[2]

PAGE = """# A page

Opening words that belong to no section.

## 1. Stiffness (`lamina.py`)

The reduced stiffness of a ply from its moduli.

### In other axes

Rotation of the stiffness by the fibre angle.

## 2. Failure

The strength ratio by maximum stress and by Tsai-Hill.

## Empty
"""


def test_a_page_is_split_at_its_headings_and_a_sub_section_carries_its_parents_title():
    found = split("page", "A page", PAGE)
    assert [(s.id, s.title) for s in found] == [("page:1-stiffness", "1. Stiffness"), ("page:1-stiffness-in-other-axes", "1. Stiffness: In other axes"),
                                                ("page:2-failure", "2. Failure")]
    assert found[0].text == "The reduced stiffness of a ply from its moduli." and found[1].cited() == "A page, 1. Stiffness: In other axes"
    assert all("Opening words" not in s.text for s in found)  # text before the first section is no section


def test_words_drop_the_grammar_and_a_plurals_s():
    assert words_of("Why are the stresses in the 90 degree plies highest?") == ["stress", "degree", "highest"]
    assert words_of("σ₁ and τ₁₂ across the fibres") == ["σ", "τ", "across", "fibre"]
    assert words_of("max sigma in the fibers, tied") == ["maximum", "σ", "fibre", "tie"]  # one spelling for a word written two ways


def test_a_question_finds_the_section_that_holds_its_words_best_first_and_nothing_for_words_no_section_holds():
    among = tuple(split("page", "A page", PAGE))
    assert [s.id for s, _ in find("how is the stiffness rotated by the fibre angle?", among)][0] == "page:1-stiffness-in-other-axes"
    assert [s.id for s, _ in find("what is the Tsai-Hill strength ratio?", among)] == ["page:2-failure"]
    assert find("banana", among) == [] and find("why is it?", among) == [] and find("stiffness", ()) == []
    first, second = find("stiffness", among)
    assert first[1] >= second[1] and find("stiffness", among) == find("stiffness", among)  # the same question, the same answer


def test_the_real_pages_are_read_and_the_plain_questions_find_their_sections():
    found = sections()
    assert {s.source for s in found} == set(SOURCES) and len({s.id for s in found}) == len(found) >= 40
    assert all(s.text and len(s.text) <= MAX_SECTION_CHARS for s in found)
    # an equation's section is among the three a question brings to the model
    for question, title in [("what is the Tsai-Hill failure index?", "5. Failure"), ("why do the reactions equal the applied force?", "4. Solution and reactions"),
                            ("how is the ply stress rotated into material axes?", "6. Ply stresses in material axes"),
                            ("what does a temperature change do to the plies?", "7. Temperature change")]:
        assert title in [s.title for s, _ in find(question, limit=3)], question


def test_a_question_of_why_finds_its_reason_first():
    for question, title in [
        ("why is ply 4 in compression?", "Why a 90-degree ply is in compression along its fibres when the coupon is pulled"),
        ("why does ply 4 fail first?", "Why a 90-degree ply usually fails first in a tension coupon"),
        ("why is the shear negative in ply 1?", "Why plies at plus and minus 45 degrees carry shear"),
        ("what does the failure index mean?", "What the factor at first-ply failure and the failure index mean"),
        ("why is the stress higher at the grips?", "Why the stress is highest at the grips and is reported apart from the answer"),
        ("why do the 0 plies carry the most load?", "Why plies at different angles carry different stresses"),
        ("why does a finer mesh change the stress?", "Why the element size changes the numbers"),
        ("why are ply 4 and ply 5 tied?", "Why two plies tie"),
        ("what is the reaction force and why", "Why the grip's reaction is what it is"),
    ]:
        section = find(question)[0][0]
        assert (section.document, section.title) == ("Reasons behind a result", title), question
    # a reason is among the three even when an equation's section comes first
    assert "Why the failure criteria give different factors" in [s.title for s, _ in find("why is tsai-hill lower than max stress?", limit=3)]


def test_the_page_of_reasons_names_no_program_and_writes_no_value_of_a_result():
    reasons = [s for s in sections() if s.source == "reasons"]
    assert len(reasons) == 12
    for section in reasons:
        assert not any(name in section.text for name in ("Abaqus", "CalculiX", "PrePoMax", "Claude", "`")), section.title
        assert "From: " in section.text, section.title  # each reason names the theory it rests on
        assert not [n for n in __import__("re").findall(r"\d+\.\d+", section.text)], section.title  # no decimal number: nothing to copy as a result


def test_the_repairs_sections_are_read_but_kept_out_of_a_coupons_search():
    # ADR-0102 amendment 5: no chat answers a question about a repair yet, and its words ("the 0° ply carries", "the load") are a coupon's too
    repair = of_subject("repair")
    assert {s.id for s in repair} == {"engine:16-stepped-lap-bond", "engine:17-stepped-patch-repair"}
    assert set(repair) | set(of_subject("wing")) | set(of_subject("references")) | set(of_subject()) == set(sections())
    for question in ("how come the 0 ply carries most of the load", "why does the adhesive's shear stress peak at the end of a step?"):
        assert all(s.subject == "" for s, _ in find(question, limit=10)), question
    assert find("why does the adhesive's shear stress peak at the end of a step?", among=repair)[0][0].id == "engine:16-stepped-lap-bond"
    assert find("how stiff is a patch ply at an angle on a ledge?", among=repair)[0][0].id == "engine:17-stepped-patch-repair"


def test_the_wings_sections_are_read_but_searched_only_by_their_subject():
    # ADR-0102 amendment 4: no chat answers a question about a wing yet, so its sections are kept out of what a question is matched against
    wing = of_subject("wing")
    assert {s.id for s in wing} >= {"engine:13-wing", "engine:15-spar-caps-and-layups-that-change-along-the-span", "fea:10-the-wing-in-calculix"}
    assert all(s.subject == "wing" for s in wing)
    assert set(wing) | set(of_subject("references")) | set(of_subject("repair")) | set(of_subject()) == set(sections())
    assert "engine:14-design-rules-of-a-stack" in {s.id for s in of_subject()}  # a laminate's rules are not the wing's alone
    question = "why do spar caps carry the bending?"
    assert all(s.subject == "" for s, _ in find(question, limit=10))
    assert find(question, among=wing)[0][0].id == "engine:15-spar-caps-and-layups-that-change-along-the-span"


def test_a_sections_other_words_find_it_as_its_titles_do_and_are_never_shown():
    page = "# A page\n\n## Ply drops\n\n<!-- also: taper, run-out -->\n\nWhere plies end along the span.\n\n## Balance\n\nPlus and minus pairs.\n"
    drops, balance = split("page", "A page", page, "references")
    assert drops.also == "taper, run-out" and "also" not in drops.text and "taper" not in drops.shown and balance.also == ""
    assert drops.subject == balance.subject == "references"
    assert [s.id for s, _ in find("what taper ratio?", (drops, balance))] == ["page:ply-drops"]
    assert find("what run-out does it need?", (drops, balance))[0][0] is drops


# The wing's questions about rules, tests and allowables (tests/assistant-questions/wing.json, waiting for the wing's chat) and the
# reference section each must find first among what the wing's chat searches (ADR-0127). The value in the answer is the wing's or the
# record's; the section only explains it.
WING_ASKS = {
    "what ply drop ratio should I use?": "rules:ply-drops-how-long-the-run-out-is",
    "how many 0° plies can I stack together?": "rules:plies-of-one-angle-in-a-row",
    "does my skin meet the 10% rule?": "rules:the-10-rule",
    "which ASTM test gives the compression allowable?": "tests:compression-along-the-fibres",
    "what allowables are you using for the spar caps?": "allowables:which-strengths-a-wing-used",
}
# Other words for the same subjects, as engineers type them: each finds its section first.
OTHER_WORDS = {
    "what taper should a ply drop-off have": "rules:ply-drops",
    "how many plies can I drop at one place": "rules:ply-drops-how-many-plies-end-at-one-place",
    "max consecutive same angle plies": "rules:plies-of-one-angle-in-a-row",
    "what is the ten percent rule": "rules:the-10-rule",
    "should I use A-basis or B-basis": "allowables:which-basis-to-use-where",
    "what does B-basis mean": "allowables:mean-b-basis-and-a-basis",
    "what is a B-estimate": "allowables:b-basis-values-and-b-estimates",
    "hot wet knockdown": "allowables:environment-hot-wet-and-cold",
    "how is the margin of safety calculated": "allowables:design-values-and-the-margin-of-safety",
    "what is CAI": "tests:impact-and-compression-after-impact-astm-d7136-d7136m-astm-d7137-d7137m",
    "what test gives the shear strength": "tests:in-plane-shear-astm-d3518-d3518m-astm-d5379-d5379m",
}


def test_the_reference_pages_are_searched_only_with_the_wings_sections_and_answer_the_wings_questions_first():
    references = of_subject("references")
    assert {s.source for s in references} == {"rules", "tests", "allowables"} and len(references) >= 20
    assert set(wing_sections()) == set(references) | set(of_subject("wing"))
    asked = {q["ask"] for q in json.loads((REPO / "tests" / "assistant-questions" / "wing.json").read_text(encoding="utf-8"))["questions"]}
    assert set(WING_ASKS) <= asked  # the bank's own words
    for question, section in {**WING_ASKS, **OTHER_WORDS}.items():
        found = [s.id for s, _ in find(question, among=wing_sections(), limit=3)]
        assert found[0] == section, (question, found)
        assert all(s.subject == "" for s, _ in find(question, limit=10)), question  # a coupon's chat never finds them


def test_the_reference_pages_cite_their_sources_name_no_program_and_hold_no_value_of_a_material():
    library = json.loads((REPO / "engine" / "src" / "anisotropy_engine" / "data" / "material-library.json").read_text(encoding="utf-8"))
    values = {f"{p['sourceValue']:g}" for d in library["datasets"] for p in d["properties"] if p.get("sourceValue") and p["sourceValue"] >= 1}
    for section in of_subject("references"):
        assert "Sources: " in section.text, section.title  # each section names where it comes from
        assert section.also, section.title  # every section names the other words it is asked by
        assert not any(name in section.text for name in ("Abaqus", "CalculiX", "PrePoMax", "Ansys", "Claude", "`")), section.title
        cited = re.sub(r"\b(?:sections?|equation|paragraph|Table|definition)\s+\S+", "", section.text)  # where in a source, not a value
        numbers = set(re.findall(r"\d+\.\d+", cited))
        assert not numbers & values, (section.title, numbers & values)  # a value is read from the record, never from a page

