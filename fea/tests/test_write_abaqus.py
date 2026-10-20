"""The Abaqus-dialect writer: deterministic text our own reader round-trips and our kernel solves (ADR-0030)."""

import hashlib
from pathlib import Path

import numpy as np
import pytest

from anisotropy_engine.mixed import mixed_response
from anisotropy_fea.abaqus_reader import parse_deck, read_deck
from anisotropy_fea.femodel import build_model
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.mesh import mesh_from_deck
from anisotropy_fea.model import section_plies, validate_deck
from anisotropy_fea.spec import load_spec, parse_spec, to_si
from anisotropy_fea.write_abaqus import number, write_abaqus

SPECS = Path(__file__).parents[1] / "validation" / "specs"
NODAL = (SPECS / "unnotched-im7-8552-nodal.toml").read_text(encoding="utf-8")


def test_numbers_are_written_with_a_decimal_point_and_ten_digits():
    assert number(1.0) == "1." and number(0.18288) == "0.18288" and number(162095.74) == "162095.74" and number(-285.72) == "-285.72"
    assert number(1e-5) == "1e-05" and number(1 / 3) == "0.3333333333"


def test_the_deck_is_deterministic_and_round_trips_through_our_reader(tmp_path):
    spec = load_spec(SPECS / "unnotched-im7-8552-nodal.toml")
    model = build_model(spec)
    text = write_abaqus(model)
    assert text == write_abaqus(model)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert len(digest) == 64
    assert "*Element, type=S4R" in text and "*Shell Section, elset=All, composite, orientation=Ori-1, layup=Layup-1, symmetric" in text
    assert "0.18288, 3, IM7-8552, 45., Ply-1" in text
    assert "*Fail Stress\n2558.506536, -1731.480399, 64.05229525, -285.7187422, 91.14869142, 0." in text
    assert "*Node Print, nset=Grip-Top, totals=YES\nRF" in text and "*El Print, elset=Probe-near_grip, position=CENTROIDAL" in text
    assert "** rights class open-publisher" in "\n".join(line for line in text.splitlines() if line.startswith("**")) or "rights class open-publisher" in text
    deck = parse_deck(text, source_path="generated")
    assert validate_deck(deck) == () and deck.ignored_keywords  # the print requests are skipped, listed, never refused
    path = tmp_path / "generated.inp"
    path.write_text(text, encoding="utf-8")
    read = read_deck(path, "mm-MPa")
    mesh = mesh_from_deck(read)
    assert mesh.node_count == model.mesh.node_count and mesh.element_count == model.mesh.element_count
    assert mesh.xy == pytest.approx(model.mesh.xy, abs=1e-12)
    assert mesh.connectivity.tolist() == model.mesh.connectivity().tolist()
    plies = section_plies(read.parts["Coupon"].sections[0], read.materials)
    assert [p.angle_deg for p in plies] == [45, 0, -45, 90, 90, -45, 0, 45] and plies[0].material.strengths.F1c == pytest.approx(1731.4804e6, rel=1e-7)


def test_nodal_and_coupled_grips_give_the_same_solution(tmp_path):
    solutions = {}
    for name in ("unnotched-im7-8552-nodal", "unnotched-im7-8552-coupling"):
        path = tmp_path / f"{name}.inp"
        path.write_text(write_abaqus(build_model(load_spec(SPECS / f"{name}.toml"))), encoding="utf-8")
        deck = read_deck(path, "mm-MPa")
        solutions[name] = (deck, solve_membrane(deck))
    nodal_deck, nodal = solutions["unnotched-im7-8552-nodal"]
    coupled_deck, coupled = solutions["unnotched-im7-8552-coupling"]
    assert nodal.displacement == pytest.approx(coupled.displacement[: nodal.mesh.node_count], abs=1e-15)
    rf_nodal, rf_coupled = nodal.reaction_of(nodal_deck.nsets["Grip-Top"]), coupled.reaction_of(coupled_deck.nsets["RF-Top"])
    assert rf_nodal == pytest.approx(rf_coupled, abs=1e-10 * abs(rf_nodal[1]))  # the x components are roundoff
    assert nodal.total_reaction == pytest.approx([0.0, 0.0], abs=1e-9 * abs(nodal.reaction_of(nodal_deck.nsets["Grip-Top"])[1]))


def test_a_free_lateral_edge_coupon_with_line_grips_in_x_only_reproduces_the_engine(tmp_path):
    # Line grips holding y only (v = 0 at the bottom row, v = pull at the top row) plus one corner held in x: the uniform state exists
    text = NODAL.replace('region = "tabs"', 'region = "line"')
    spec = to_si(parse_spec(text))
    model = build_model(spec)
    deck_text = write_abaqus(model)
    # relax the grips to the free-lateral-edge conditions by editing the written boundary block (a test of the kernel path, not of the writer)
    deck_text = deck_text.replace("*Boundary\nGrip-Bottom, 1, 6\nGrip-Top, 1, 1\nGrip-Top, 3, 6\nGrip-Top, 2, 2, 1.\n",
                                  "*Boundary\nGrip-Bottom, 2, 2\nCoupon-1.1, 1, 1\nGrip-Top, 2, 2, 1.\n")
    assert "Coupon-1.1, 1, 1" in deck_text
    path = tmp_path / "free.inp"
    path.write_text(deck_text, encoding="utf-8")
    deck = read_deck(path, "mm-MPa")
    solution = solve_membrane(deck)
    plies = section_plies(deck.parts["Coupon"].sections[0], deck.materials)
    mixed = mixed_response(plies, {"Nx": 0.0, "eps_y": 1e-3 / 0.250, "Nxy": 0.0, "Mx": 0.0, "My": 0.0, "Mxy": 0.0}, None)
    assert solution.strain == pytest.approx(np.tile(mixed.midplane_strain, (solution.mesh.element_count, 1)), rel=1e-10, abs=1e-15)
    assert solution.reaction_of(deck.nsets["Grip-Top"])[1] == pytest.approx(mixed.loads.Ny * 0.025, rel=1e-10)


def test_force_control_deck_carries_the_consistent_loads_and_balances(tmp_path):
    text = NODAL.replace('control = "displacement"\nvalue = 1.0', 'control = "force"\nvalue = 5000.0').replace('region = "tabs"', 'region = "line"')
    deck_text = write_abaqus(build_model(to_si(parse_spec(text))))
    assert "*Cload\nCoupon-1.1376, 2, 250.\nCoupon-1.1377, 2, 500." in deck_text
    path = tmp_path / "force.inp"
    path.write_text(deck_text, encoding="utf-8")
    deck = read_deck(path, "mm-MPa")
    solution = solve_membrane(deck)
    assert solution.total_reaction == pytest.approx([0.0, -5000.0], abs=1e-6)
    assert solution.reaction_of(deck.nsets["Grip-Bottom"])[1] == pytest.approx(-5000.0, rel=1e-10)


@pytest.mark.parametrize("name", ["unnotched-im7-8552-nodal", "unnotched-im7-8552-coupling", "compression-im7-8552",
                                  "tension-coupon-x840-nodal", "tension-coupon-x840-coupling"])
def test_the_committed_generated_decks_match_their_specs(name):
    """A committed deck is what the writer produces from its spec today; regenerate it when the spec or the writer changes."""
    text = write_abaqus(build_model(load_spec(SPECS / f"{name}.toml")))
    committed = (SPECS.parent / "decks" / "generated" / f"{name}-abaqus.inp").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert committed == text, f"{name}: regenerate with examples/build_model.py --no-solve and copy the deck into validation/decks/generated/"


def test_order_two_decks_are_written_as_s8r_with_nine_entries_per_element():
    spec = to_si(parse_spec(NODAL.replace("element_order = 1", "element_order = 2").replace("nx = 10\nny = 125", "nx = 2\nny = 125")))
    text = write_abaqus(build_model(spec))
    assert "*Element, type=S8R" in text
    first = [line for line in text.splitlines() if line.startswith("1, ") and line.count(",") == 8][0]
    assert first.split(", ")[1:5] == ["1", "2", "5", "4"]
