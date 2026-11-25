"""The tension coupon from its material and layup (ADR-0090): what the standard and our rules choose, why, and that the reference pick
builds the public D3039 check."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.checks import setup_checklist
from anisotropy_fea.equivalence import deck_equivalence
from anisotropy_fea.femodel import build_model
from anisotropy_fea.intake import FIELDS, FORM_VERSION, IntakeError, read_values
from anisotropy_fea.spec import load_spec
from anisotropy_fea.tension_input import complete_tension, d3039_class, transverse_estimates
from anisotropy_fea.write_abaqus import write_abaqus

from test_checks import TOOLS

DAY = date(2026, 11, 11)
D3039 = "ASTM D3039/D3039M-17"
REFERENCE = {"library": "im7-8552", "angles": [45, 0, -45, 90], "symmetric": "yes"}
CHECK = paths.CHECKS / "d3039-im7-8552" / "d3039-im7-8552.toml"


@pytest.fixture(autouse=True)
def versions(monkeypatch):
    monkeypatch.setattr("anisotropy_fea.checks.ccx_version", lambda ccx: "2.22" if ccx is not None else None)  # as tests/test_checks.py


def values_file(folder: Path, values: dict) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "values.json"
    path.write_text(json.dumps({"form_version": FORM_VERSION, "input": "tension", **values}), encoding="utf-8")
    return path


def chosen(built) -> dict:
    return {b.row: b.value for b in built}


@pytest.mark.parametrize(("angles", "symmetric", "size"), [
    ([0, 0, 0, 0], "yes", (15.0, 250.0, 56.0)),     # 0 deg unidirectional: Table 2's tabbed strip
    ([90, 90, 90, 90], "yes", (25.0, 175.0, 25.0)),  # 90 deg unidirectional
    ([45, 0, -45, 90], "yes", (25.0, 250.0, 56.0)),  # balanced and symmetric: Table 2 gives no grip length, 56 mm is ours
])
def test_the_size_comes_from_the_layups_d3039_class(angles, symmetric, size):
    values, built = complete_tension({"library": "im7-8552", "angles": angles, "symmetric": symmetric}, DAY)
    assert (values["width"], values["length"], values["tab_length"]) == size
    assert values["size_from"].startswith(f"{D3039}, Table 2, ")
    if angles == [45, 0, -45, 90]:  # the grip length Table 2 does not give says who chose it, on the card and the README ("here" had no referent)
        assert "the 56 mm grip length is the software's choice, since Table 2 gives none for this class" in values["size_from"]
        assert next(b.reason for b in built if b.row == "tab_length").endswith("56 mm is the software's choice")
    assert values["test"] == "unnotched tension" and values["standard"] == D3039 and values["units"] == "mm-MPa"
    assert values["date"] == "2026-11-11"


def test_a_layup_in_no_class_gets_no_size_and_the_check_asks_for_it_by_row(tmp_path):
    values, built = complete_tension({"library": "im7-8552", "angles": [0, 45], "symmetric": "no"}, DAY)
    assert d3039_class(values) is None
    assert not {"length", "width", "tab_length"} & set(chosen(built))
    assert values["size_from"] == f"the dimensions you give: the layup is in no {D3039} Table 2 class"  # a customer reads it (audit review R2-10)
    checklist = setup_checklist(read_values(values_file(tmp_path, {"library": "im7-8552", "angles": [0, 45], "symmetric": "no"})),
                                tmp_path / "none", **TOOLS)[0]
    assert checklist.state == "blocked"
    problems = "; ".join(checklist.problems)
    assert "Length (mm): required" in problems and "Width (mm): required" in problems and "Where the size comes from" not in problems


@pytest.mark.parametrize(("given", "size", "yours"), [
    ({"width": 30.0}, (30.0, 250.0, 56.0), "the width"),  # the founder's case of 2026-11-14: a wider strip keeps Table 2's length and the grip length
    ({"length": 300.0, "tab_length": 60.0}, (25.0, 300.0, 60.0), "the length and the tab length"),
])
def test_each_size_row_left_blank_is_chosen_on_its_own(tmp_path, given, size, yours):
    """ADR-0090 amendment 1: under D3039, a size row the engineer typed is kept and every other one comes from Table 2 (the grip length from
    the software's default), where one typed row once dropped all three; the deviation is reported, never refused."""
    values, built = complete_tension({**REFERENCE, **given}, DAY)
    assert (values["width"], values["length"], values["tab_length"]) == size
    assert not set(given) & set(chosen(built)), "a row the engineer gave is never chosen again"
    assert values["size_from"].startswith(f"{yours} as you gave, the rest from {D3039}, Table 2, ")
    assert values["size_from"].endswith(f"; a deviation from {D3039} Table 2 is reported, never refused")
    assert ("56 mm grip length is the software's choice" in values["size_from"]) == ("tab_length" not in given)
    checklist = setup_checklist(read_values(values_file(tmp_path, {**REFERENCE, **given})), tmp_path / "none", **TOOLS)[0]
    assert checklist.state == "ready", checklist.problems


def test_every_choice_names_its_row_and_its_reason_and_no_given_row_is_changed():
    given = {**REFERENCE, "control": "force", "value": 5000.0, "width": 20.0, "length": 200.0, "tab_length": 40.0, "element_size": 1.5}
    values, built = complete_tension(given, DAY)
    for key, value in given.items():
        assert values[key] == value, key
    rows = chosen(built)
    assert not set(given) & set(rows), "a row the engineer gave is never chosen again"
    assert all(b.row in FIELDS and b.reason.strip() for b in built)
    assert values["size_from"].startswith("the dimensions you gave: a deviation from " + D3039)
    assert "control" not in rows and "value" not in rows


def test_the_transverse_moduli_follow_the_forms_estimate_for_a_tape_and_equal_g12_otherwise():
    values, _ = complete_tension(REFERENCE, DAY)
    assert values["G13"] == 4688.43 and values["G23"] == 2987.73  # IM7/8552: G12, and E2 / 3
    own, built = complete_tension({"own_name": "X", "own_E1": 80000, "own_E2": 80000, "own_G12": 5100, "own_nu12": 0.06, "own_source": "a sheet",
                                   "angles": [0, 45], "symmetric": "yes"}, DAY)
    assert own["G13"] == 5100 and own["G23"] == 5100
    assert all("does not load it" in b.reason for b in built if b.row in ("G13", "G23"))


def test_a_values_file_names_only_the_tension_screen(tmp_path):
    path = tmp_path / "values.json"
    path.write_text(json.dumps({"form_version": FORM_VERSION, "input": "panels", **REFERENCE}), encoding="utf-8")
    with pytest.raises(IntakeError, match="input 'panels' is not one this tool reads"):
        read_values(path)


def test_the_reference_pick_builds_the_public_d3039_check_and_the_checklist_says_how(tmp_path):
    checklist, model, _ = setup_checklist(read_values(values_file(tmp_path, REFERENCE)), tmp_path / "none", **TOOLS)
    assert checklist.state == "ready", checklist.problems
    built = checklist.as_dict()["built"]
    assert {b["row"] for b in built} >= {"width", "length", "tab_length", "strain_length", "grips", "value", "element_size", "G13", "G23"}
    check = build_model(load_spec(CHECK))
    assert np.array_equal(model.mesh.xy, check.mesh.xy) and np.array_equal(model.mesh.corners, check.mesh.corners)
    assert sorted(model.node_sets) == sorted(check.node_sets) and all(np.array_equal(model.node_sets[k], check.node_sets[k]) for k in check.node_sets)
    assert model.boundaries == check.boundaries
    for part in ("geometry", "mesh", "layup", "material", "grips", "loading", "probes", "strain", "test_method"):
        assert getattr(model.spec, part) == getattr(check.spec, part), part
    ours = tmp_path / "ours-abaqus.inp"
    ours.write_text(write_abaqus(model), encoding="utf-8")
    equivalence = deck_equivalence(read_deck(CHECK.parent / "decks" / "d3039-im7-8552-abaqus.inp", "mm-MPa"), read_deck(ours, "mm-MPa"), 1e-9, "mm-MPa")
    assert equivalence.same_model, [item.what for item in equivalence.differences]


@pytest.mark.parametrize("given", [REFERENCE, {"library": "im7-8552", "angles": [0, 45], "symmetric": "no"},
                                   {"own_name": "X", "own_E1": 80000, "own_E2": 80000, "own_G12": 5100, "own_nu12": 0.06, "own_source": "a sheet"}])
def test_no_reason_the_screen_shows_names_a_tool_a_file_or_the_team(given):
    """The tension screen lists every choice with its reason to a customer (ADR-0091): no program, record, script or team word."""
    _, built = complete_tension(given, DAY)
    banned = ("abaqus", "calculix", "prepomax", "spooles", ".toml", ".py", "ours", "our engine", "the team", "studio's", "change a choice")
    for choice in built:
        assert not [word for word in banned if word in choice.reason.lower()], (choice.row, choice.reason)


def test_the_material_steps_estimates_are_the_ones_the_coupon_is_built_with_and_given_values_are_kept():
    """The Material step shows G13 and G23 before any check from the same function the coupon is built with (ADR-0111 amendment 5); values
    the engineer gives for a library material are kept and not chosen again."""
    estimate = transverse_estimates("im7-8552")
    values, built = complete_tension(REFERENCE, DAY)
    assert (values["G13"], values["G23"]) == (estimate.G13, estimate.G23)
    assert {b.row: b.reason for b in built if b.row in ("G13", "G23")} == estimate.reasons
    assert "E2 / 3" in estimate.rule
    given, built = complete_tension({**REFERENCE, "G13": 5200, "G23": 3400}, DAY)
    assert (given["G13"], given["G23"]) == (5200, 3400)
    assert not {"G13", "G23"} & {b.row for b in built}
    one, built = complete_tension({**REFERENCE, "G13": 5200}, DAY)  # one given: the other is still estimated
    assert (one["G13"], one["G23"]) == (5200, estimate.G23) and [b.row for b in built if b.row in ("G13", "G23")] == ["G23"]



def test_a_coupon_stated_in_inches_is_completed_in_inches(tmp_path):
    """The screen sends its units when they are not mm-MPa (ADR-0090 amendment 2): Table 2's own inch sizes, our choices converted, so the
    mesh is the 2 mm one and not 2 mm read as inches (the second site check, 2026-11-25: "switch to inches" sent a 0.0787 in mesh read as
    0.0787 mm, and the setup check never finished)."""
    values, built = complete_tension({**REFERENCE, "units": "in-psi"}, DAY)
    assert (values["width"], values["length"]) == (1.0, 10.0)  # D3039 Table 2's inch-pound values, not 25 mm converted
    assert (values["tab_length"], values["strain_length"], values["value"], values["element_size"]) == (2.20472, 0.984252, 0.0393701, 0.0787402)
    assert (values["G13"], values["G23"]) == (679999.0, 433334.0)  # psi
    assert "units" not in chosen(built), "the engineer's units are kept, not chosen"
    reasons = {b.row: b.reason for b in built}
    assert "2.20472 in (56 mm)" in reasons["tab_length"] and reasons["strain_length"].startswith("0.984252 in (25 mm), within")
    metric, _ = complete_tension({**REFERENCE, "units": "m-Pa"}, DAY)
    assert (metric["width"], metric["tab_length"], metric["element_size"], metric["value"]) == (0.025, 0.056, 0.002, 0.001)
    inches, model, _ = setup_checklist(read_values(values_file(tmp_path / "in", {**REFERENCE, "units": "in-psi"})), tmp_path / "none", **TOOLS)
    assert inches.state == "ready", inches.problems
    _, mm_model, _ = setup_checklist(read_values(values_file(tmp_path / "mm", REFERENCE)), tmp_path / "none", **TOOLS)
    # 1.0 x 10 in against 25 x 250 mm, both at 2 mm: a row or two more across the wider coupon (1,764 elements against 1,488), not a
    # mesh 25 times finer each way
    assert mm_model.mesh.element_count < model.mesh.element_count < 1.25 * mm_model.mesh.element_count
