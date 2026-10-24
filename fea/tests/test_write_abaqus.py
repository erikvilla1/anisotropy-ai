"""The Abaqus-dialect writer: deterministic text our own reader round-trips and our kernel solves (ADR-0030)."""

import hashlib
from pathlib import Path

import numpy as np
import pytest

from public_coupon import PUBLIC_COUPON

from anisotropy_engine.mixed import mixed_response
from anisotropy_fea.abaqus_reader import parse_deck, read_deck
from anisotropy_fea.femodel import build_model
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.mesh import mesh_from_deck
from anisotropy_fea.model import section_plies, validate_deck
from anisotropy_fea import paths  # where the files live (ADR-0036)
from anisotropy_fea.mesher import gmsh_available
from anisotropy_fea.spec import load_spec, parse_spec, to_si
from anisotropy_fea.write_abaqus import number, write_abaqus

NODAL = paths.spec_path("unnotched-im7-8552-nodal").read_text(encoding="utf-8")


def test_numbers_are_written_with_a_decimal_point_and_ten_digits():
    assert number(1.0) == "1." and number(0.18288) == "0.18288" and number(162095.74) == "162095.74" and number(-285.72) == "-285.72"
    assert number(1e-5) == "1e-05" and number(1 / 3) == "0.3333333333"


def test_the_deck_is_deterministic_and_round_trips_through_our_reader(tmp_path):
    spec = load_spec(paths.spec_path("unnotched-im7-8552-nodal"))
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
        path.write_text(write_abaqus(build_model(load_spec(paths.spec_path(name)))), encoding="utf-8")
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


SPECS = paths.all_specs()  # the checks', and the local coupon models' on the founder's machine (ADR-0042)
GMSH = gmsh_available() is not None


def needs_mesher(spec_path):
    if not GMSH and parse_spec(spec_path.read_text(encoding="utf-8")).mesh.mesher == "gmsh":
        pytest.skip("Gmsh is not installed (uv sync --extra mesh); the Gmsh specs are checked where it is")


@pytest.mark.parametrize("spec_path", SPECS, ids=[p.stem for p in SPECS])
def test_every_abaqus_deck_is_what_its_spec_writes_today(spec_path):
    """Every spec in a test folder has its Abaqus deck in decks/; regenerate with tools/regenerate_decks.py when a spec or the writer changes."""
    needs_mesher(spec_path)
    deck = paths.deck_path(spec_path, "abaqus")
    assert deck.is_file(), f"{spec_path.name} has no deck {deck.name}; run tools/regenerate_decks.py"
    text = write_abaqus(build_model(load_spec(spec_path)))
    assert deck.read_text(encoding="utf-8").replace("\r\n", "\n") == text, f"{deck.name}: regenerate with tools/regenerate_decks.py"


CCX_SPECS = [p for p in SPECS if paths.deck_path(p, "ccx").is_file()]


@pytest.mark.parametrize("spec_path", CCX_SPECS, ids=[p.stem for p in CCX_SPECS])
def test_every_calculix_deck_is_what_its_spec_writes_today(spec_path):
    """A CalculiX deck is the same spec promoted to order 2 (S8R), as examples/run_calculix.py writes it."""
    from anisotropy_fea.write_calculix import write_calculix

    needs_mesher(spec_path)
    spec = load_spec(spec_path)
    order2 = spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"element_order": 2})})
    text = write_calculix(build_model(order2))
    deck = paths.deck_path(spec_path, "ccx")
    assert deck.read_text(encoding="utf-8").replace("\r\n", "\n") == text, f"{deck.name}: regenerate with tools/regenerate_decks.py"
    assert "*ELEMENT, TYPE=S8R" in text


def test_every_test_folder_has_the_same_shape():
    """A spec at the root, its decks in decks/, records with a reading beside each (ADR-0036): in records/ for a check, in
    verification/ for a coupon's ours/. A coupon's folder is local and holds three parts beside its case page: team/, ours/ and
    documents/ (ADR-0040 amendment 3, ADR-0042); ours/ also holds our runs and the document's LaTeX."""
    assert len([d for d in paths.test_dirs() if d.parent == paths.CHECKS]) >= 4
    coupons = [d for d in paths.test_dirs() if d.parent != paths.CHECKS]
    assert {d.parent for d in coupons} == set(paths.model_dirs()) and all(d.name == paths.OURS for d in coupons)  # every local test folder is a coupon's ours/
    for folder in paths.model_dirs():
        assert {p.name for p in folder.iterdir()} <= {"README.md", paths.TEAM_FILES, paths.OURS, paths.DOCUMENTS}, folder
    for folder in paths.test_dirs():
        parts = {paths.VERIFICATION, paths.RUNS, paths.LATEX} if folder.name == paths.OURS else {"records", "README.md"}
        allowed = {"decks"} | parts | {p.name for p in folder.glob("*.toml")}
        assert set(p.name for p in folder.iterdir()) <= allowed, folder
        for record in paths.records_dir(folder).glob("*.toml"):
            if record in paths.all_records():  # the team summary's reading is the team comparison's (ADR-0039); the manifest is not a record
                assert record.with_suffix(".md").is_file(), f"{record} has no reading note"
    assert len([r for r in paths.all_records() if paths.CHECKS in r.parents]) == 2 and paths.CONVENTIONS.is_file() and any(paths.CASES.glob("*.toml"))


def test_order_two_decks_are_written_as_s8r_with_nine_entries_per_element():
    spec = to_si(parse_spec(NODAL.replace("element_order = 1", "element_order = 2").replace("nx = 10\nny = 125", "nx = 2\nny = 125")))
    text = write_abaqus(build_model(spec))
    assert "*Element, type=S8R" in text
    first = [line for line in text.splitlines() if line.startswith("1, ") and line.count(",") == 8][0]
    assert first.split(", ")[1:5] == ["1", "2", "5", "4"]


def test_a_names_table_gives_the_deck_its_names_and_our_names_otherwise():
    """[names] reaches every place a name appears in the deck; without it the deck keeps our names (ADR-0035, amendment 1)."""
    named = write_abaqus(build_model(to_si(parse_spec(PUBLIC_COUPON))))
    for line in ("*Part, name=Strip", "*Instance, name=Strip-1, part=Strip", "*Material, name=IM7-8552-Lamina",
                 "*Elset, elset=Layup-A-1, generate",
                 "*Shell Section, elset=Layup-A-1, composite, orientation=Ori-1, layup=Layup-A, symmetric",
                 "0.18288, 3, IM7-8552-Lamina, 45., Ply-1", "*Nset, nset=Grip-Top, instance=Strip-1"):
        assert line in named.splitlines(), line
    deck = read_deck_text(named)
    assert set(deck.parts) == {"Strip"} and set(deck.instances) == {"Strip-1"} and set(deck.materials) == {"IM7-8552-Lamina"}
    plain = write_abaqus(build_model(to_si(parse_spec(NODAL))))
    assert "*Part, name=Coupon" in plain and "*Instance, name=Coupon-1, part=Coupon" in plain and "layup=Layup-1" in plain
    with pytest.raises(ValueError, match="names.material"):
        parse_spec(PUBLIC_COUPON.replace('material = "IM7-8552-Lamina"', 'material = "IM7 8552 Lamina"'))
    with pytest.raises(ValueError, match="must differ"):
        parse_spec(PUBLIC_COUPON.replace('instance = "Strip-1"', 'instance = "Strip"'))


def read_deck_text(text: str):
    return parse_deck(text)
