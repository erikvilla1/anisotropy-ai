"""The hand calculation of a coupon (ADR-0112): every result it writes is the engine's value, and every formula, evaluated again from the
values written into it, gives that value; working that does not lead to its result is refused. On the public IM7/8552 coupon, nothing under
.local/."""

from __future__ import annotations

import dataclasses
import re

import pytest
from anisotropy_engine.engineering import engineering_constants
from public_coupon import PUBLIC_COUPON

from anisotropy_fea import hand_calculation as hand
from anisotropy_fea.abaqus_reader import parse_deck
from anisotropy_fea.femodel import build_model
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.model import to_si
from anisotropy_fea.recovery import deck_f12_star
from anisotropy_fea.report import laminate_check
from anisotropy_fea.spec import load_spec
from anisotropy_fea.write_abaqus import write_abaqus

STIFFNESS = ["ply_stiffness", "rotation", "laminate", "constants"]
STATE = ["loading", "ply_strain", "ply_stress"]


@pytest.fixture(scope="module")
def coupon(tmp_path_factory):
    path = tmp_path_factory.mktemp("hand") / "public.toml"
    path.write_text(PUBLIC_COUPON, encoding="utf-8")
    spec = load_spec(path)
    deck = to_si(parse_deck(write_abaqus(build_model(spec)), source_path="public.inp"), "mm-MPa")
    solution = solve_deck(deck)
    return spec, deck, laminate_check(deck, solution)


def calculation(coupon, with_state: bool = True):
    spec, deck, check = coupon
    section = check  # the check carries the laminate's plies and their stated angles
    return hand.hand_calculation(section.plies, section.angles_deg, "mm-MPa", tuple(spec.output.fpf_criteria), deck_f12_star(deck),
                                 check if with_state else None)


def test_the_steps_run_from_the_ply_to_first_ply_failure_and_end_on_the_engines_values(coupon):
    hc = calculation(coupon)
    ids = [step["id"] for step in hc["steps"]]
    assert ids[:7] == STIFFNESS + STATE and ids[-1] == "first_ply_failure"
    assert [i for i in ids if i.startswith("failure_")] == [f"failure_{c}" for c in coupon[0].output.fpf_criteria]
    _, _, check = coupon
    engine = engineering_constants(check.plies)
    assert hc["constants"]["Ey"] == pytest.approx(engine.Ey / 1e6, rel=1e-5)  # MPa, written to six figures
    assert hc["state"]["control"] == "displacement" and hc["state"]["reaction"] == pytest.approx(check.reaction_N, rel=1e-5)
    # the [45/0/-45/90]s laminate under a pull: the two 90-degree plies in the middle fail first, by transverse tension, a little past
    # the applied loading, by every criterion
    for criterion, f in hc["failure"].items():
        assert f["plies"] == [4, 5] and f["angles"] == [90.0], criterion
        assert 1.0 < f["ratio"] < 1.2, criterion
    # the ratios are ordered as the criteria's interactions make them: maximum stress ignores the other components, Tsai-Wu adds the most
    assert hc["failure"]["max_stress"]["ratio"] > hc["failure"]["tsai_hill"]["ratio"] > hc["failure"]["tsai_wu"]["ratio"]


def test_every_line_writes_its_formula_its_values_and_a_result_of_six_figures(coupon):
    hc = calculation(coupon)
    lines = [e for step in hc["steps"] for e in [*step.get("equations", []), *step.get("coefficients", []),
                                                *(x for g in step.get("groups", []) for x in g["equations"])]]
    assert len(lines) > 40
    for e in lines:
        assert e["lhs"] and e["shown"], e
        digits = re.sub(r"\\times 10\^\{-?\d+\}|[^0-9]", "", e["shown"]).lstrip("0")
        assert len(digits) <= hand.GIVEN_DIGITS, e  # never more figures than the next step reads
    ply = next(step for step in hc["steps"] if step["id"] == "ply_stiffness")
    q11 = next(e for e in ply["equations"] if e["lhs"] == "Q_{11}")
    assert "162096" in q11["substituted"] or "162095" in q11["substituted"]  # E1 of the NCAMP record, put in
    assert all(step["source"] for step in hc["steps"])  # every step says where its equations come from


def test_without_the_coupons_state_only_the_stiffness_steps_are_written(coupon):
    hc = calculation(coupon, with_state=False)
    assert [step["id"] for step in hc["steps"]] == STIFFNESS
    assert hc["state"] is None and hc["failure"] is None


def test_working_that_does_not_reach_the_engines_value_is_refused(coupon, monkeypatch):
    """The report never prints a formula beside a result it does not give: an engine value 0.1 % off is caught at its step."""
    def off(plies):
        right = engineering_constants(plies)
        return dataclasses.replace(right, Ex=right.Ex * 1.001)

    monkeypatch.setattr(hand, "engineering_constants", off)
    with pytest.raises(hand.HandCalculationError, match="E_x"):
        calculation(coupon)


def test_the_hand_calculation_names_no_code_of_ours(coupon):
    """ADR-0112: the working is physics and arithmetic; no function, module or file of ours appears in it."""
    hc = calculation(coupon)
    text = repr(hc)
    assert not re.search(r"anisotropy|\.py\b|def |import |_ratio\(|laminate_check|abd_", text)
