"""Results side by side: our values written as an Abaqus/CAE field report, and paired with a reference deck's reports (ADR-0035)."""

from pathlib import Path

import numpy as np
import pytest

from anisotropy_fea.abaqus_reader import parse_deck, read_deck
from anisotropy_fea.abaqus_report import ReportError, read_field_report, write_field_report
from anisotropy_fea.equivalence import deck_equivalence
from anisotropy_fea.femodel import build_model
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.mesh import KernelError
from anisotropy_fea.model import to_si
from anisotropy_fea.side_by_side import agreement, kernel_difference, pair_reports, ply_values
from anisotropy_fea.spec import parse_spec, to_si as spec_to_si
from anisotropy_fea.write_abaqus import write_abaqus

from test_equivalence import FIXTURE_SPEC, GRIPS_FIXTURE

UNITS = "mm-MPa"


def kernel_reports(deck_path: Path, out: Path, quantities=("S11", "S22", "Mises"), layers=((1, "SNEG"), (10, "SPOS"))) -> list[Path]:
    """What the team's export would hold if Abaqus gave our kernel's numbers: one CAE-layout report per quantity, the deck's numbering."""
    deck = read_deck(deck_path, units=UNITS)
    solution = solve_membrane(deck)
    values = ply_values(solution, UNITS)
    paths = []
    for q in quantities:
        rows = []
        for index, (instance, label) in enumerate(solution.mesh.element_keys):
            x, y = solution.mesh.xy[solution.mesh.connectivity[index]].mean(axis=0) * 1e3
            rows += [(label, layer, face, float(x), float(y), float(values[q][index, layer - 1])) for layer, face in layers]
        path = out / f"Test_{q}.csv"
        write_field_report(path, q, rows, "fixture.odb", "Step-1", "Increment 1", "CFRP-COUPON-1", "CFRP-COUPON-1_COMPOSITELAYUP-1-1", "IM7-8552")
        paths.append(path)
    return paths


def test_a_written_report_reads_back_exactly(tmp_path):
    rows = [(3, 1, "SNEG", 2.5, 7.5, 1234.5), (3, 10, "SPOS", 2.5, 7.5, 1234.5), (8, 4, "SMID", 7.5, 12.5, -0.125)]
    path = tmp_path / "ours-S22.csv"
    write_field_report(path, "S22", rows, "kernel (no .odb)", "Step-1", "linear static solve", "CFRP-COUPON-1", "COUPON-1_ALL", "X840-Z60-PW")
    report = read_field_report(path)
    assert report.quantity == "S22" and report.instance == "CFRP-COUPON-1" and report.blocks == 1 and report.rows == 3
    assert report.values == {(3, 1): 1234.5, (3, 10): 1234.5, (8, 4): -0.125}
    assert report.faces == {(3, 1): "SNEG", (3, 10): "SPOS", (8, 4): "SMID"} and report.centroids == {3: (2.5, 7.5), 8: (7.5, 12.5)}
    with pytest.raises(ReportError, match="not one of"):
        write_field_report(path, "E22", rows, "o", "s", "f", "i", "s", "m")
    with pytest.raises(ReportError, match="face 'TOP'"):
        write_field_report(path, "S22", [(1, 1, "TOP", 0.0, 0.0, 1.0)], "o", "s", "f", "i", "s", "m")


def test_reports_of_the_reference_deck_pair_with_our_generated_deck_element_by_element(tmp_path):
    reports = [read_field_report(p) for p in kernel_reports(GRIPS_FIXTURE, tmp_path)]
    team = read_deck(GRIPS_FIXTURE, units=UNITS)
    ours = to_si(parse_deck(write_abaqus(build_model(spec_to_si(parse_spec(FIXTURE_SPEC))))), UNITS)
    eq = deck_equivalence(team, ours, 1e-8, UNITS)
    solution = solve_membrane(ours)
    paired = pair_reports(reports, team, solution, eq, UNITS)
    assert len(paired) == 3 * 16 * 2
    # the same model gives the same numbers, to the nine significant digits the report keeps
    assert max(abs(p.difference) for p in paired) <= 1e-8 * max(abs(p.reference) for p in paired)
    assert all(eq.element_map[("CFRP-Coupon-1", p.reference_element)][1] == p.our_element for p in paired)
    a = agreement(paired, "S22", "free length", (0.0, 80.0), 0.01)
    assert a.count == 32 and a.within == 32 and a.worst_fraction <= 1e-8 and a.largest > 0
    assert agreement(paired, "S22", "nowhere", (90.0, 95.0), 0.01).count == 0
    difference, largest = kernel_difference(solve_membrane(team), solution, eq, UNITS)
    assert difference <= 1e-9 * largest


def test_a_report_whose_centroids_do_not_match_is_refused(tmp_path):
    path = kernel_reports(GRIPS_FIXTURE, tmp_path, quantities=("S22",))[0]
    lines = path.read_text(encoding="utf-8").splitlines()
    moved = []
    for line in lines[1:3]:  # element 1 at layers 1 and 10: both rows, or the reader refuses the report itself
        cells = line.split(",")
        cells[6] = f"{float(cells[6]) + 0.01:.9g}"  # its reported centroid 0.01 mm to the side
        moved.append(",".join(cells))
    path.write_text("\n".join([lines[0], *moved, *lines[3:]]) + "\n", encoding="utf-8")
    team = read_deck(GRIPS_FIXTURE, units=UNITS)
    ours = to_si(parse_deck(write_abaqus(build_model(spec_to_si(parse_spec(FIXTURE_SPEC))))), UNITS)
    eq = deck_equivalence(team, ours, 1e-8, UNITS)
    with pytest.raises(KernelError, match="centroid"):
        pair_reports([read_field_report(path)], team, solve_membrane(ours), eq, UNITS)


def test_ply_values_hold_every_ply_in_material_axes():
    solution = solve_membrane(read_deck(GRIPS_FIXTURE, units=UNITS))
    values = ply_values(solution, UNITS)
    assert set(values) == {"S11", "S22", "S12", "Mises"} and values["S22"].shape == (16, 10)
    s11, s22, s12 = values["S11"], values["S22"], values["S12"]
    assert np.allclose(values["Mises"], np.sqrt(s11 ** 2 - s11 * s22 + s22 ** 2 + 3 * s12 ** 2))
