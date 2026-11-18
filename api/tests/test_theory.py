"""The theory pages as sections found by a question's words (ADR-0102, proposed): the split, the ranking, and that nothing is found for
words the pages do not hold."""

from __future__ import annotations

from anisotropy_api.theory import MAX_SECTION_CHARS, SOURCES, find, sections, split, words_of

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
