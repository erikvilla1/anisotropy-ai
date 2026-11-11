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
from anisotropy_fea.tension_input import complete_tension, d3039_class
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
    assert values["test"] == "unnotched tension" and values["standard"] == D3039 and values["units"] == "mm-MPa"
    assert values["date"] == "2026-11-11"


def test_a_layup_in_no_class_gets_no_size_and_the_check_asks_for_it_by_row(tmp_path):
    values, built = complete_tension({"library": "im7-8552", "angles": [0, 45], "symmetric": "no"}, DAY)
    assert d3039_class(values) is None
    assert not {"length", "width", "tab_length"} & set(chosen(built))
    assert values["size_from"] == f"the engineer's own size: the layup is in no {D3039} Table 2 class"
    checklist = setup_checklist(read_values(values_file(tmp_path, {"library": "im7-8552", "angles": [0, 45], "symmetric": "no"})),
                                tmp_path / "none", **TOOLS)[0]
    assert checklist.state == "blocked"
    problems = "; ".join(checklist.problems)
    assert "Length (mm): required" in problems and "Width (mm): required" in problems and "Where the size comes from" not in problems


def test_every_choice_names_its_row_and_its_reason_and_no_given_row_is_changed():
    given = {**REFERENCE, "control": "force", "value": 5000.0, "width": 20.0, "length": 200.0, "tab_length": 40.0, "element_size": 1.5}
    values, built = complete_tension(given, DAY)
    for key, value in given.items():
        assert values[key] == value, key
    rows = chosen(built)
    assert not set(given) & set(rows), "a row the engineer gave is never chosen again"
    assert all(b.row in FIELDS and b.reason.strip() for b in built)
    assert values["size_from"].startswith("the engineer's own size: a deviation from " + D3039)
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
