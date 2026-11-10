"""A coupon solved as a flat shell (bending coupons, plates) through the audit and the package. The package's equilibrium row
summed a membrane's two force components with a shell's five reaction components and crashed every bending coupon; the ply
table and the audit's words assumed one state per ply. These pin the shell path: the force balance on dofs 1 to 3 with the
nose, concentrated loads and pressures counted, two faces per ply, and the in-plane coupons as they were."""

import csv
import dataclasses
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from openpyxl import load_workbook

from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.audit import Evidence, load_rubric, score
from anisotropy_fea.compare import load_record
from anisotropy_fea.femodel import build_model
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.mesh import KernelError
from anisotropy_fea.recovery import FACES, element_ply_states
from anisotropy_fea.results import MembraneSolution, ShellSolution
from anisotropy_fea.side_by_side import pair_reports, ply_values
from anisotropy_fea.spec import TEST_CODES, coupon_card, load_spec
from anisotropy_fea.write_abaqus import write_abaqus

ROOT = Path(__file__).parents[2]
THREE_POINT = paths.CHECKS / "three-point-im7-8552" / "three-point-im7-8552.toml"
PLATE = paths.CHECKS / "plate-pressure-isotropic" / "plate-pressure-isotropic.toml"
UNNOTCHED = paths.spec_path("unnotched-im7-8552-nodal")
THREE_POINT_TEXT = THREE_POINT.read_text(encoding="utf-8")
PLATE_TEXT = PLATE.read_text(encoding="utf-8")


def four_point() -> str:
    """The public three-point coupon on four-point loading: two noses 16 mm apart, centred on the 48 mm span."""
    text = THREE_POINT_TEXT.replace('kind = "three_point_bending"', 'kind = "four_point_bending"').replace("IM7-3PB-L1", "IM7-4PB-L1")
    text = text.replace("IM7-4PB-L1, three-point bending:", "IM7-4PB-L1, four-point bending:")
    text = text.replace("overhang = 6.0\n", "overhang = 6.0\nload_span = 16.0\n")
    assert 'kind = "four_point_bending"' in text and "load_span = 16.0" in text
    return text


def plate_under_a_force() -> str:
    """The public plate with its pressure replaced by a 100 N resultant along z, spread over the face as concentrated loads."""
    pressure = '\n[[loads]]\nregion = "Face"\npressure = -0.01\n'
    assert PLATE_TEXT.count(pressure) == 1, "the public plate no longer states its pressure as this test expects"
    return PLATE_TEXT.replace(pressure, '\n[[loads]]\nregion = "Face"\ndof = 3\ntotal = 100.0\n')


def evidence_of(spec_path: Path) -> Evidence:
    """Our deck and our kernel's solution as the package's audit gathers them, for a coupon the team has not built."""
    spec = load_spec(spec_path)
    deck_path = spec_path.with_name(spec_path.stem + "-abaqus.inp")
    deck_path.write_text(write_abaqus(build_model(spec)), encoding="utf-8")
    deck = read_deck(deck_path, spec.units)
    return Evidence(test_code=TEST_CODES[spec.kind][0], units=spec.units, card=tuple(coupon_card(spec)), our_deck=deck, solution=solve_deck(deck))


def spec_file(tmp_path: Path, text: str, name: str) -> Path:
    path = tmp_path / f"{name}.toml"
    path.write_text(text, encoding="utf-8")
    return path


def row(evidence: Evidence, item_id: str):
    return next(s for s in score(load_rubric(), evidence) if s.item.id == item_id)


@pytest.fixture(scope="module")
def shells(tmp_path_factory):
    folder = tmp_path_factory.mktemp("shells")
    return {"3PB": evidence_of(spec_file(folder, THREE_POINT_TEXT, "three-point")),
            "4PB": evidence_of(spec_file(folder, four_point(), "four-point")),
            "plate, pressure": evidence_of(spec_file(folder, PLATE_TEXT, "plate-pressure")),
            "plate, force": evidence_of(spec_file(folder, plate_under_a_force(), "plate-force"))}


@pytest.mark.parametrize("name", ["3PB", "4PB", "plate, pressure", "plate, force"])
def test_every_shell_coupon_is_scored_and_its_forces_balance(shells, name):
    evidence = shells[name]
    assert isinstance(evidence.solution, ShellSolution) and evidence.solution.reaction.shape[1] == 5
    scored = score(load_rubric(), evidence)  # raised "operands could not be broadcast together with shapes (5,) (2,)" on every bending coupon
    d2 = next(s for s in scored if s.item.id == "D2")
    assert d2.result == "Pass", d2.found.text
    assert d2.found.ours[0].startswith("Reactions sum to (") and d2.found.ours[0].count(",") == 2  # three force components: x, y, z


def test_a_displaced_nose_applies_no_load_and_the_supports_carry_the_nose(shells):
    for name in ("3PB", "4PB"):
        evidence = shells[name]
        d2 = row(evidence, "D2")
        assert d2.found.ours[1] == "Applied loads (0, 0, 0) N"
        noses = [n for n in evidence.our_deck.nsets if n.startswith("Nose")]
        nose = sum(float(evidence.solution.reaction_of(evidence.our_deck.nsets[n])[2]) for n in noses)
        supports = sum(float(evidence.solution.reaction_of(evidence.our_deck.nsets[n])[2]) for n in ("Support-Left", "Support-Right"))
        assert nose < 0.0 and supports == pytest.approx(-nose, rel=1e-9)  # the coupon pushes back up on the nose; the supports carry it


def test_a_pressure_and_a_concentrated_load_out_of_the_plane_are_counted_as_applied(shells):
    # the plate's pressure of -0.01 MPa on 100 mm by 100 mm pushes 100 N toward +z (a positive P pushes against the normal, ADR-0053)
    for name in ("plate, pressure", "plate, force"):
        d2 = row(shells[name], "D2")
        assert d2.found.ours[1] == "Applied loads (0, 0, 100) N", (name, d2.found.text)
        assert shells[name].solution.total_reaction[2] == pytest.approx(-100.0, rel=1e-10)


def test_reactions_that_do_not_balance_the_loads_fail(shells):
    evidence = shells["plate, pressure"]
    unbalanced = dataclasses.replace(evidence.solution, reaction=evidence.solution.reaction * 0.5)
    assert row(dataclasses.replace(evidence, solution=unbalanced), "D2").result == "Fail"
    bent = shells["3PB"]
    reaction = bent.solution.reaction.copy()
    reaction[np.flatnonzero(reaction[:, 2])[0], 2] += 1.0  # one newton too many at one support node
    assert row(dataclasses.replace(bent, solution=dataclasses.replace(bent.solution, reaction=reaction)), "D2").result == "Fail"


def test_a_plate_held_along_the_coupon_on_two_edges_is_measured_against_its_load(tmp_path):
    # a support on dof 2 at the bottom and the top edge makes two gripped groups, whose in-plane reaction is roundoff under a pressure
    text = PLATE_TEXT.replace('region = "Edge-Bottom"\ndofs = [3, 5]', 'region = "Edge-Bottom"\ndofs = [2, 3, 5]')
    text = text.replace('region = "Edge-Top"\ndofs = [3, 5]', 'region = "Edge-Top"\ndofs = [2, 3, 5]').replace('region = "Corner-X"\ndofs = [2]', 'region = "Corner-X"\ndofs = [3]')
    assert text.count("dofs = [2, 3, 5]") == 2
    d2 = row(evidence_of(spec_file(tmp_path, text, "plate-held")), "D2")
    assert d2.result == "Pass", d2.found.text
    assert "of the 50 N scale" in d2.found.difference[0]


def test_the_moments_are_left_out_of_the_force_balance(shells):
    evidence = shells["3PB"]
    reaction = evidence.solution.reaction.copy()
    reaction[:, 3:] += 1e3  # the moment reactions' sum depends on the point taken; it is not a force balance
    assert row(dataclasses.replace(evidence, solution=dataclasses.replace(evidence.solution, reaction=reaction)), "D2").result == "Pass"


def test_an_in_plane_coupon_balances_two_components_as_before(tmp_path):
    evidence = evidence_of(spec_file(tmp_path, UNNOTCHED.read_text(encoding="utf-8").replace('"unnotched-im7-8552-nodal', '"x'), "unnotched"))
    assert isinstance(evidence.solution, MembraneSolution)
    d2 = row(evidence, "D2")
    assert d2.result == "Pass" and d2.found.ours[1] == "Applied loads (0, 0) N" and d2.found.ours[0].count(",") == 1
    d5 = row(evidence, "D5")
    assert d5.found.ours[-1] == "Our engine's model is a membrane, so it shows no bending"


def test_the_audit_says_the_shell_bends_and_shows_the_deflection(shells):
    evidence = shells["3PB"]
    d5 = row(evidence, "D5")
    assert "membrane" not in d5.found.text and d5.found.ours[-1] == "Our engine's model is a flat shell: it bends, with first-order transverse shear"
    assert any(line.startswith("Curvature at element") for line in d5.found.ours)
    c4 = row(evidence, "C4").found.ours[0]
    assert ", U3 -" in c4  # the quarter probe moves down with the nose
    w = float(c4.split(", U3 ")[1].split(" mm")[0])
    probe = evidence.solution.mesh.node(evidence.our_deck.nsets["Probe-quarter"][0])
    assert w == pytest.approx(evidence.solution.displacement[probe, 2] * 1e3, rel=1e-3)


def test_a_shell_has_two_faces_per_ply_and_no_side_by_side_yet(shells, tmp_path):
    solution = shells["3PB"].solution
    values = ply_values(solution, "mm-MPa")
    field = element_ply_states(solution)
    assert values["S11"].shape == (solution.mesh.element_count, 8, len(FACES))
    assert values["S22"][7, 2, 1] == pytest.approx(field.stress_12[7][2, 1, 1] / 1e6)  # element 8, ply 3, the top face
    assert not np.allclose(values["S11"][..., 0], values["S11"][..., 1])  # a bent ply differs between its faces
    with pytest.raises(KernelError, match="built for a membrane solution only"):
        pair_reports([], shells["3PB"].our_deck, solution, None, "mm-MPa")


def test_an_in_plane_coupon_keeps_one_value_per_ply(tmp_path):
    evidence = evidence_of(spec_file(tmp_path, UNNOTCHED.read_text(encoding="utf-8"), "unnotched"))
    assert ply_values(evidence.solution, "mm-MPa")["Mises"].shape == (evidence.solution.mesh.element_count, 8)


@pytest.fixture(scope="module")
def coupon():
    spec = importlib.util.spec_from_file_location("anisotropy_models_coupon", ROOT / "docs/models/coupon.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def public_check_sources(coupon, tmp: Path, spec_path: Path):
    """A public check as a coupon the team has not built: its spec and deck in a coupon's folder, its own CalculiX record."""
    spec = load_spec(spec_path)
    designation = spec.coupon.designation
    local = tmp / f"{designation}.toml"
    local.write_text(spec_path.read_text(encoding="utf-8"), encoding="utf-8")
    paths.deck_path(local, "abaqus").parent.mkdir()
    paths.deck_path(local, "abaqus").write_text(write_abaqus(build_model(load_spec(local))), encoding="utf-8", newline="\n")
    record = spec_path.parent / "records" / f"{spec_path.stem}-calculix.toml"
    twin = (record.parent / load_record(record)["spec"]).resolve()
    return designation, coupon.Sources(coupon=designation, spec=local, twin=twin, record=record, manifest=None,
                                       documents=tmp / designation / paths.DOCUMENTS, team_files=tmp / designation / paths.TEAM_FILES,
                                       latex=tmp / designation / paths.OURS / paths.LATEX)


@pytest.mark.parametrize("spec_path", [THREE_POINT, PLATE], ids=["three-point bending", "plate"])
def test_a_shell_coupon_makes_its_package(coupon, tmp_path, spec_path):
    designation, sources = public_check_sources(coupon, tmp_path, spec_path)
    _, package = coupon.build_document(sources, pdf=False, theory=False)  # the three-point coupon crashed here, in the audit's equilibrium row
    with (package / "4-results" / "ours-all-plies.csv").open(encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0][:7] == ["team element", "our element", "x (mm)", "y (mm)", "ply (1 = bottom)", "face", "angle (deg)"]
    spec = load_spec(spec_path)
    plies = len(spec.layup.angles) * (2 if spec.layup.symmetric else 1)
    assert len(rows) - 1 == spec.mesh.nx * spec.mesh.ny * plies * 2 and [r[5] for r in rows[1:3]] == list(FACES)
    form = load_workbook(package / f"{package.name}-audit.xlsx")["Rubric"]
    results = {r[0]: r[6] for r in form.iter_rows(min_row=2, values_only=True) if r[0]}
    assert results["D2"] == "Pass"


def test_the_engine_step_solves_a_plate_under_pressure(tmp_path):
    # examples/build_model.py took a plate under pressure, which bends, for a bending coupon and looked for its loading nose
    result = subprocess.run([sys.executable, str(ROOT / "fea/examples/build_model.py"), str(PLATE), "--out", str(tmp_path / "out")],
                            capture_output=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    summary = (tmp_path / "out" / "summary.txt").read_text(encoding="utf-8")
    assert "kernel solve (flat shell): reactions at the supports" in summary and "sum of reactions [0.0, 0.0, -100.0] N" in summary
