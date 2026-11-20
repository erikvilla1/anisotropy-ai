"""Design rules of a stack (ADR-0123): the 10 % rule, plies of one angle in a row, balance and symmetry, on stacks whose answer is
counted by hand, and the wing file's [design_rules] with the rules of every layup in the wing's report."""

import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from anisotropy_engine.lamina import Lamina
from anisotropy_engine.laminate import Ply
from anisotropy_engine.layup_rules import RuleLimits, angle_words, layup_rules
from anisotropy_engine.wing import analyze_wing, wing_from_dict, wing_report

PLY = Lamina(E1=140e9, E2=10e9, G12=5e9, nu12=0.3)
OTHER = Lamina(E1=40e9, E2=10e9, G12=4e9, nu12=0.28)
EXAMPLE = Path(__file__).parents[1] / "examples" / "example-wing.toml"


def stack(*angles, thickness=1.25e-4):
    return [Ply(material=PLY, angle_deg=a, thickness_m=thickness) for a in angles]


def rules(plies, core_after=None, **limits):
    return {r.rule: r for r in layup_rules(plies, RuleLimits(**limits), core_after)}


def test_a_quasi_isotropic_stack_meets_every_rule():
    found = rules(stack(0, 45, -45, 90, 90, -45, 45, 0))
    assert all(r.met for r in found.values())
    assert found["ten_percent"].detail["shares"] == {"0": 0.25, "45": 0.25, "-45": 0.25, "90": 0.25}
    assert found["in_a_row"].detail["longest"] == 2  # the two 90 plies at the middle
    assert found["symmetry"].words == "Symmetric about the middle."


def test_the_ten_percent_rule_counts_plies_by_direction():
    no_90 = rules(stack(0, 45, -45, 0, 0, -45, 45, 0))["ten_percent"]
    assert not no_90.met
    assert no_90.words.startswith("No plies at 90°:")
    one_in_twelve = rules(stack(0, 45, -45, 0, 0, 90, 0, 0, 0, -45, 45, 0))  # one 90 ply in twelve
    assert not one_in_twelve["ten_percent"].met
    assert one_in_twelve["ten_percent"].words.startswith("Only 8.3 % at 90°:")
    one_in_ten = rules(stack(0, 45, -45, 0, 90, 0, 0, -45, 45, 0))["ten_percent"]  # exactly 10 %: met
    assert one_in_ten.met
    assert rules(stack(0, 45, -45, 0, 90, 0, 0, -45, 45, 0), min_share=0.15)["ten_percent"].met is False


def test_a_fiber_at_theta_is_the_fiber_at_theta_plus_180():
    found = rules(stack(180, 135, -135, -90, 90, 45, -45, 0))
    assert found["ten_percent"].detail["shares"] == {"0": 0.25, "45": 0.25, "-45": 0.25, "90": 0.25}
    assert [angle_words(a) for a in (0, 45, -45, 90, -90, 135, 30, 22.5)] == ["0°", "+45°", "−45°", "90°", "90°", "−45°", "+30°", "+22.5°"]


def test_plies_in_a_row_count_across_the_middle_but_not_across_a_core():
    solid = rules(stack(45, -45, 0, 0, 0, 0, -45, 45))["in_a_row"]  # [45/-45/0/0]s: four 0 plies meet at the middle
    assert solid.met and solid.detail == {"longest": 4, "angle": 0.0, "first": 3, "last": 6, "plies": 8, "max_in_a_row": 4}
    five = rules(stack(45, -45, 0, 0, 0, 0, 0, 0, -45, 45))["in_a_row"]
    assert not five.met
    assert five.words == "6 plies at 0° in a row (plies 3 to 8 of 10); at most 4."
    sandwich = rules(stack(45, -45, 0, 0, 0, 0, 0, 0, -45, 45), core_after=5)["in_a_row"]
    assert sandwich.met and sandwich.detail["longest"] == 3
    assert not rules(stack(45, -45, 0, 0, 0, 0, -45, 45), max_in_a_row=3)["in_a_row"].met


def test_balance_names_the_plies_without_a_partner():
    found = rules(stack(45, 45, 0, 0, 45, 45))["balance"]
    assert not found.met
    assert found.words == "Not balanced: 4 plies at +45° and 0 at −45°."
    assert rules(stack(0, 90, 90, 0))["balance"].words == "Balanced: no plies off 0° and 90°."
    thick = stack(45) + [Ply(material=PLY, angle_deg=-45, thickness_m=2.5e-4)] + stack(0)
    assert rules(thick)["balance"].words == "Not balanced: plies at opposite angles differ in material or thickness."


def test_symmetry_names_the_first_ply_that_does_not_mirror():
    found = rules(stack(0, 45, -45, 90, 90, 45, -45, 0))["symmetry"]
    assert not found.met
    assert found.words == "Not symmetric: ply 2 is at +45° and its mirror, ply 7, at −45°."
    other = stack(0, 45) + [Ply(material=OTHER, angle_deg=45, thickness_m=1.25e-4)] + stack(0)
    assert "ply 2 and its mirror, ply 3, differ in material or thickness" in rules(other)["symmetry"].words
    assert rules(stack(0, 45, 45, 0, 0, 0), core_after=2)["symmetry"].words == "Not symmetric: the core has 2 plies on one side and 4 on the other."
    assert rules(stack(0, 45, 45, 0), core_after=2)["symmetry"].words == "Symmetric about the core."


@pytest.mark.parametrize("limits", [{"min_share": 0}, {"min_share": 0.3}, {"max_in_a_row": 0}, {"max_in_a_row": 2.0}, {"max_in_a_row": True},
                                    {"min_share": float("nan")}, {"angle_step": 60}])
def test_limits_out_of_range_are_refused(limits):
    with pytest.raises(ValidationError):
        RuleLimits(**limits)


def test_a_stack_without_plies_or_with_a_core_at_its_face_is_refused():
    with pytest.raises(ValueError, match="at least one ply"):
        layup_rules([])
    with pytest.raises(ValueError, match="plies on both sides"):
        layup_rules(stack(0, 0), core_after=2)


def example(design_rules=None) -> dict:
    data = tomllib.loads(EXAMPLE.read_text(encoding="utf-8"))
    if design_rules is not None:
        data["design_rules"] = design_rules
    return data


def test_the_wing_reports_the_rules_of_every_layup_and_they_change_no_number():
    wing, envelope = wing_from_dict(example())
    assert wing.design_rules == RuleLimits()
    report = wing_report(analyze_wing(wing, envelope), "SI", "m/s")
    assert report["rule_limits"] == {"min_percent": 10.0, "max_in_a_row": 4}
    assert [(r["part"], r["rule"]) for r in report["rules"]] == [(part, rule) for part in ("skin", "spar", "rib")
                                                                 for rule in ("ten_percent", "in_a_row", "balance", "symmetry")]
    skin = {r["rule"]: r for r in report["rules"] if r["part"] == "skin"}
    assert not skin["ten_percent"]["met"] and skin["symmetry"]["words"] == "Symmetric about the core."
    assert skin["ten_percent"]["source"].startswith("MIL-HDBK-17-3F")

    strict, strict_envelope = wing_from_dict(example({"min_percent": 20, "max_in_a_row": 2}))
    assert strict.design_rules == RuleLimits(min_share=0.2, max_in_a_row=2)
    other = wing_report(analyze_wing(strict, strict_envelope), "SI", "m/s")
    assert other["rule_limits"] == {"min_percent": 20.0, "max_in_a_row": 2}
    assert {key: other[key] for key in ("passes", "design", "governing", "cases")} == {key: report[key] for key in ("passes", "design", "governing", "cases")}
    spar = {r["rule"]: r for r in other["rules"] if r["part"] == "spar"}
    assert not spar["in_a_row"]["met"]  # [45/-45/0/0]s: four 0 plies at the middle, two allowed


@pytest.mark.parametrize("table, message", [
    ({"min_percent": 30}, "at most 25 %"), ({"min_percent": 0}, "above 0"), ({"min_percent": "10"}, "above 0"),
    ({"max_in_a_row": 2.5}, "whole number"), ({"max_in_a_row": 0}, "whole number"), ({"max_in_a_row": True}, "whole number"),
    ({"angle_step": 60}, "unknown keys angle_step"),
])
def test_design_rules_that_are_wrong_are_refused_by_name(table, message):
    with pytest.raises(ValueError, match=message):
        wing_from_dict(example(table))


def test_an_empty_design_rules_table_keeps_the_defaults():
    wing, _ = wing_from_dict(example({}))
    assert wing.design_rules == RuleLimits()
    wing, _ = wing_from_dict(example({"max_in_a_row": 3.0}))  # a page that sends 3 as 3.0
    assert wing.design_rules.max_in_a_row == 3
