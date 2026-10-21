"""Model equivalence: our generated deck against another deck of the same coupon, item by item (ADR-0035)."""

from pathlib import Path

import numpy as np
import pytest

from anisotropy_fea.abaqus_reader import parse_deck, read_deck
from anisotropy_fea.equivalence import EquivalenceError, deck_equivalence
from anisotropy_fea.femodel import build_model
from anisotropy_fea.mesher import Mesh2D
from anisotropy_fea.model import to_si
from anisotropy_fea.spec import load_spec, parse_spec, to_si as spec_to_si
from anisotropy_fea.write_abaqus import write_abaqus
from anisotropy_fea import paths  # where the files live (ADR-0036)

ROOT = Path(__file__).parents[1]
GRIPS_FIXTURE = paths.CHECK_DECKS / "coupon-2x8-grips-im7-8552.inp"
TEAM_SPEC = paths.spec_path("tension-coupon")
TOLERANCE = 1e-8  # m, 0.01 micrometre

# The grips fixture (the team's CAE structure: CFRP-Coupon, CompositeLayup-1, Set-9-style sets, a reference node listed in its own
# coupled set) written as a spec our generator builds: 10 by 80 mm, 2 by 8 S4R, couplings on the end rows, 0.8 mm pull.
FIXTURE_SPEC = """
title = "The grips fixture as a spec"
kind = "unnotched_tension"
units = "mm-MPa"
[geometry]
length = 80.0
width = 10.0
tab_length = 0.0
[mesh]
mesher = "structured"
element_order = 1
nx = 2
ny = 8
[layup]
angles = [0, 45, -45, 45, 0]
symmetric = true
ply_thickness = 0.18288
[material]
E1 = 162095.74
E2 = 8963.18
G12 = 4688.43
nu12 = 0.316
F1t = 2558.51
F1c = 1731.48
F2t = 64.05
F2c = 285.72
F6 = 91.15
f12_star = 0.0
[material.transverse]
G13 = 4688.43
G23 = 3000.0
nu23 = 0.45
transverse_isotropy = true
plane_stress = false
[grips]
kind = "coupling"
region = "line"
[loading]
control = "displacement"
value = 0.8
[output]
fpf_criteria = ["max_stress"]
abaqus = { field_preselect = true, node_print = false, el_print = false }
calculix = { node_print = false, el_print = false, frd = false, el_print_global = false }
"""


def generated(spec_text: str | None = None, mesh=None) -> str:
    spec = load_spec(TEAM_SPEC) if spec_text is None else spec_to_si(parse_spec(spec_text))
    return write_abaqus(build_model(spec, mesh))


def deck_of(text: str):
    return to_si(parse_deck(text), "mm-MPa")


def test_a_hand_built_deck_in_the_teams_structure_and_our_generated_deck_are_the_same_model():
    team = read_deck(GRIPS_FIXTURE, units="mm-MPa")
    ours = deck_of(generated(FIXTURE_SPEC))
    eq = deck_equivalence(team, ours, TOLERANCE, "mm-MPa")
    assert eq.same_model, [(i.item, i.team, i.ours) for i in eq.differences]
    assert len(eq.element_map) == 16 and eq.largest_node_offset == 0.0
    listed = {i.item: i for i in eq.items if i.same is None}
    assert listed["Part / instance names"].team == "CFRP-Coupon / CFRP-Coupon-1" and listed["Part / instance names"].ours == "Coupon / Coupon-1"
    couplings = [i for i in eq.items if i.item.startswith("Coupling")]
    assert len(couplings) == 2 and all(i.same and "drives 3 nodes" in i.team for i in couplings)  # the listed reference node is dropped on both sides


def test_renumbered_nodes_and_elements_are_matched_by_position():
    spec = load_spec(TEAM_SPEC)
    model = build_model(spec)
    mesh = model.mesh
    n, ne = mesh.node_count, mesh.element_count
    flipped = Mesh2D(xy=mesh.xy[::-1].copy(), corners=(n - 1 - mesh.corners)[::-1].copy(), midside=None,
                     node_sets={k: np.sort(n - 1 - v) for k, v in mesh.node_sets.items()},
                     element_sets={k: np.sort(ne - 1 - v) for k, v in mesh.element_sets.items()}, order=1, mesher="structured")
    eq = deck_equivalence(deck_of(write_abaqus(model)), deck_of(write_abaqus(build_model(spec, flipped))), TOLERANCE, "mm-MPa")
    assert eq.same_model, [(i.item, i.team, i.ours) for i in eq.differences]
    assert eq.node_map[("CFRP-Coupon-1", 1)] == ("CFRP-Coupon-1", n) and eq.element_map[("CFRP-Coupon-1", 1)] == ("CFRP-Coupon-1", ne)
    assert len(eq.element_map) == 800 and len([k for k in eq.node_map if k[0] is None]) == 2


CHANGES = [
    ("RF-Top, 2, 2, 10.", "RF-Top, 2, 2, 9.", "Boundary conditions, node by node"),
    ("0.1, 3, X840-Z60, -45., Ply-3", "0.1, 3, X840-Z60, 45., Ply-3", "Layup, bottom first"),
    ("0.1, 3, X840-Z60, 0., Ply-1", "0.2, 3, X840-Z60, 0., Ply-1", "Ply thickness"),
    ("0.1, 3, X840-Z60, 45., Ply-2", "0.1, 5, X840-Z60, 45., Ply-2", "Integration points per ply"),
    ("80000., 80000., 0.06,", "80000., 79000., 0.06,", "Material E2 (MPa)"),
    ("RF-Top, 1, 1\n", "", "Boundary conditions, node by node"),
]


@pytest.mark.parametrize("old, new, item", CHANGES, ids=[c[2] + ": " + c[1][:20] for c in CHANGES])
def test_a_physical_change_is_named(old, new, item):
    text = generated()
    assert old in text
    eq = deck_equivalence(deck_of(text), deck_of(text.replace(old, new, 1)), TOLERANCE, "mm-MPa")
    assert not eq.same_model and [i.item for i in eq.differences] == [item]


def test_names_read_same_when_they_match_and_are_only_listed_when_they_differ():
    text = generated()
    same = {i.item: i.same for i in deck_equivalence(deck_of(text), deck_of(text), TOLERANCE, "mm-MPa").items}
    assert same["Part / instance names"] is True and same["Material names"] is True and same["Section set / layup names"] is True
    renamed = text.replace("X840-Z60", "MY-FABRIC").replace("CFRP-Coupon", "Strip")
    eq = deck_equivalence(deck_of(text), deck_of(renamed), TOLERANCE, "mm-MPa")
    listed = {i.item: i for i in eq.items if i.same is None}
    assert eq.same_model and set(listed) == {"Part / instance names", "Material names", "Strengths (*Fail Stress)"}  # strengths are always listed
    assert listed["Material names"].ours == "MY-FABRIC" and listed["Part / instance names"].ours == "Strip / Strip-1"


def test_a_moved_node_or_a_missing_node_is_refused():
    text = generated()
    first_rows = [line for line in text.splitlines()[:40] if line.startswith("12, ")]
    assert first_rows, "the deck no longer writes node 12 near the top"
    label, x, y, z = (part.strip() for part in first_rows[0].split(","))
    moved = text.replace(first_rows[0], f"{label}, {x}, {float(y) + 0.01:g}, {z}", 1)
    with pytest.raises(EquivalenceError, match="no point of ours within"):
        deck_equivalence(deck_of(text), deck_of(moved), TOLERANCE, "mm-MPa")
    with pytest.raises(EquivalenceError, match="needs both decks in SI"):
        deck_equivalence(parse_deck(text), deck_of(text), TOLERANCE, "mm-MPa")
    with pytest.raises(EquivalenceError, match="positive length"):
        deck_equivalence(deck_of(text), deck_of(text), 0.0, "mm-MPa")
