"""The numbers behind a model comparison document, and the document generator itself (ADR-0031)."""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.compare import compare_record, load_record
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.mesh import KernelError
from anisotropy_fea.report import COMPONENTS, comparison_rows, element_centroids, laminate_check, not_reported, parse_key, solve_record, summarize
from anisotropy_fea import paths  # where the files live (ADR-0036)

FEA = Path(__file__).parents[1]
ROOT = FEA.parent
RECORD = paths.CHECKS / "unnotched-im7-8552" / "records" / "unnotched-im7-8552-nodal-calculix.toml"
DECKS = paths.CHECK_DECKS


def test_parse_key_reads_every_label_shape():
    assert parse_key("rf[Grip-Top][1]") == ("rf", "Grip-Top", None, 1)
    assert parse_key("ply_stress_local[Coupon-1.626][4][2]") == ("ply_stress_local", "Coupon-1.626", 4, 2)
    assert parse_key("fpf[max_stress][ratio][0]") == ("fpf", "max_stress", None, 0)
    with pytest.raises(ValueError, match="not a comparison label"):
        parse_key("rf[Grip-Top]")


def test_rows_are_the_record_comparison_one_for_one():
    record = load_record(RECORD)
    comparisons, _ = compare_record(record)
    rows, problems = comparison_rows(record)
    assert not problems and len(rows) == len(comparisons) == 59
    for row, c in zip(rows, comparisons):
        assert row.key == c.key and row.reference == c.expected and row.kernel == c.engine and row.allowed == c.allowed
        assert row.agrees == c.agrees and row.difference == c.engine - c.expected
        assert row.component_name == COMPONENTS[row.group][row.component]
    assert not_reported(record) == 0


def test_group_summaries_are_consistent_with_their_rows():
    rows, _ = comparison_rows(load_record(RECORD))
    summaries = summarize(rows)
    assert [s.group for s in summaries] == ["rf", "u", "strain", "ply_stress_local", "ply_strain_local"]
    for s in summaries:
        members = [r for r in rows if r.group == s.group]
        assert s.count == len(members) and s.agreeing == sum(r.agrees for r in members)
        assert s.scale == max(abs(r.reference) for r in members)
        assert s.worst.of_allowed == max(r.of_allowed for r in members)
        assert 0 <= s.mean_relative_to_scale <= s.max_relative_to_scale < 0.01  # the record: within 0.3 % of each group's largest magnitude
    assert all(r.agrees for r in rows)


def test_element_centroids_are_in_the_record_units():
    record = load_record(RECORD)
    deck, solution = solve_record(record)
    centroids = element_centroids(solution, record["units"])
    assert len(centroids) == 1250
    x, y = centroids["Coupon-1.626"]
    assert 11 < x < 14 and 124 < y < 126  # the centre probe of the 25 by 250 mm coupon (2.5 mm elements), in mm


def test_laminate_check_equals_the_kernel_on_the_free_edge_patch():
    """One element, lateral edges free, prescribed axial strain: laminate theory and the kernel must coincide."""
    deck = read_deck(DECKS / "coupon-1x1-im7-8552.inp", "mm-MPa")
    solution = solve_membrane(deck)
    check = laminate_check(deck, solution)
    assert check.control == "displacement" and len(check.plies) == 10
    assert check.strain == pytest.approx(check.kernel_strain, abs=1e-12)
    assert check.section_force == pytest.approx(check.kernel_section_force, rel=1e-9, abs=1e-6)  # N/m; zero components are roundoff
    assert check.reaction_N == pytest.approx(check.kernel_reaction_N, rel=1e-9)
    assert np.allclose(check.ply_stress_12, check.kernel_ply_stress_12, rtol=1e-9, atol=1e-3)


def test_laminate_check_on_the_committed_record_sits_near_both_solvers():
    record = load_record(RECORD)
    deck, solution = solve_record(record)
    check = laminate_check(deck, solution)
    assert check.centre_element == "Coupon-1.626"
    assert check.free_length_m == pytest.approx(0.138) and check.width_m == pytest.approx(0.025)
    assert abs(check.reaction_N - check.kernel_reaction_N) / check.kernel_reaction_N < 0.01  # the whole-tab grips stiffen the coupon slightly
    assert abs(check.strain[1] - check.kernel_strain[1]) / check.kernel_strain[1] < 0.01


def test_laminate_check_refuses_a_deck_with_no_gripped_rows():
    deck = read_deck(DECKS / "plate-1x1-isotropic-shear.inp", "mm-MPa")
    solution = solve_membrane(deck)
    with pytest.raises(KernelError, match="hand check|gripped"):
        laminate_check(deck, solution)


def test_model_facts_of_the_generated_coupon():
    """The facts a rebuild guide prints, read from the generated unnotched coupon deck (nodal grips, 10 by 125 grid)."""
    from anisotropy_fea.report import model_facts

    record = load_record(RECORD)
    deck, solution = solve_record(record)
    f = model_facts(deck, solution)
    assert f.parts == (("Coupon", 1386, 1250, "S4R"),) and f.instances == (("Coupon-1", "Coupon"),)
    assert f.extent_x == pytest.approx((0.0, 0.025)) and f.extent_y == pytest.approx((0.0, 0.25))
    assert f.grid == (10, 125) and len(f.node_rows_y) == 126
    assert f.partition_lines_y == pytest.approx((0.0, 0.056, 0.194, 0.25)) and f.row_counts == (28, 69, 28)
    assert [(b[2], b[3], b[4]) for b in f.element_bands] == [(280, 1, 280), (690, 281, 970), (280, 971, 1250)]
    assert f.edge_length_range == pytest.approx((0.002, 0.0025))
    grips = {s.name: s for s in f.node_sets if s.name.startswith("Grip")}
    assert grips["Grip-Bottom"].count == 319 and grips["Grip-Bottom"].y_range == pytest.approx((0.0, 0.056))
    assert f.couplings == () and f.reference_nodes == () and f.loads == () and f.step == ("Step-1", False)
    pulls = [b for b in f.boundaries if b.value]
    assert len(pulls) == 1 and pulls[0].target == "Grip-Top" and pulls[0].dof_first == 2 and pulls[0].value == pytest.approx(0.001)
    (section,) = f.sections
    assert section.symmetric and section.layup_name == "Layup-1" and section.orientation == "Ori-1"
    assert [p.angle_deg for p in section.listed] == [45, 0, -45, 90]
    assert [p.angle_deg for p in section.expanded] == [45, 0, -45, 90, 90, -45, 0, 45]
    assert section.expanded[0].z_bottom_m == pytest.approx(-section.total_thickness_m / 2) and section.expanded[-1].z_top_m == pytest.approx(section.total_thickness_m / 2)
    assert section.expanded[3].z_top_m == pytest.approx(0.0, abs=1e-12)
    assert section.angle_fractions == ((45.0, 2), (0.0, 2), (-45.0, 2), (90.0, 2))
    assert "*output" in f.ignored_keywords


def test_model_facts_of_the_coupled_grips_fixture():
    from anisotropy_fea.report import model_facts

    deck = read_deck(DECKS / "coupon-2x8-grips-im7-8552.inp", "mm-MPa")
    f = model_facts(deck, solve_membrane(deck))
    assert f.grid == (2, 8)
    assert [(c.name, c.reference, c.slaves, c.dofs) for c in f.couplings] == [("Grip-Top", "Assembly.1", 3, (1, 2, 3, 4, 5, 6)), ("Grip-Bottom", "Assembly.2", 3, (1, 2, 3, 4, 5, 6))]
    assert f.reference_nodes == (("Assembly.1", (pytest.approx(0.0125), pytest.approx(0.1))), ("Assembly.2", (pytest.approx(0.0125), pytest.approx(0.0))))
    assert f.partition_lines_y == pytest.approx((0.0, 0.1)) and f.row_counts == (8,)  # the end rows are the grips: no inner partition
    assert {s[0] for s in f.surfaces} == {"s_Surf-1", "s_Top_CNS_", "s_Bottom_CNS_"}


def test_the_generator_writes_a_document_for_the_committed_record(tmp_path):
    """docs/models/build.py on the committed record, LaTeX only, without the twenty-page theory section."""
    pytest.importorskip("matplotlib")
    result = subprocess.run([sys.executable, str(ROOT / "docs/models/build.py"), str(RECORD), "--out", str(tmp_path), "--no-pdf", "--no-theory"],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    tex = (tmp_path / "unnotched-im7-8552-nodal-calculix.tex").read_text(encoding="utf-8")
    assert tex.startswith(r"\documentclass") and tex.rstrip().endswith(r"\end{document}")
    for label in ("sec:summary", "sec:model", "sec:rebuild", "sec:clt", "sec:theory", "sec:reference", "sec:method", "sec:comparison", "sec:reading"):
        assert rf"\label{{{label}}}" in tex
    assert tex.count(r"\evidence{INP}") > 20 and r"\evidence{MANUAL p.8}" in tex and r"\evidence{OPEN}" in tex  # the rebuild guide tags every value
    # the partition lines y = 56 and 194 mm of the 25 by 250 mm coupon, typed in sketch coordinates centred on the face (12.5, 125)
    assert r"\texttt{-12.5,-69} & \texttt{12.5,-69}" in tex and r"\texttt{-12.5,69} & \texttt{12.5,69}" in tex
    assert "vertical and on the right" in tex and "Offset From Principal Plane" in tex
    assert "Ply table as entered (4 rows)" in tex and "Expanded stack (8 plies" in tex
    assert "59 of 59 compared values agree" in tex
    assert r"\filefrom" in tex and "unnotched-im7-8552-nodal.toml" in tex  # the spec is listed
    assert "Reading: the unnotched IM7/8552 coupon" in tex  # the reading note beside the record
    assert (tmp_path / "figures" / "differences.png").is_file() and (tmp_path / "figures" / "solution.png").is_file()
    assert not (tmp_path / "figures" / "element-map.png").exists()  # one probe element: no map
