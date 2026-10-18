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

FEA = Path(__file__).parents[1]
ROOT = FEA.parent
RECORD = FEA / "validation" / "records" / "unnotched-im7-8552-nodal-calculix.toml"
DECKS = FEA / "validation" / "decks"


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


def test_the_generator_writes_a_document_for_the_committed_record(tmp_path):
    """docs/models/build.py on the committed record, LaTeX only, without the twenty-page theory section."""
    pytest.importorskip("matplotlib")
    result = subprocess.run([sys.executable, str(ROOT / "docs/models/build.py"), str(RECORD), "--out", str(tmp_path), "--no-pdf", "--no-theory"],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    tex = (tmp_path / "unnotched-im7-8552-nodal-calculix.tex").read_text(encoding="utf-8")
    assert tex.startswith(r"\documentclass") and tex.rstrip().endswith(r"\end{document}")
    for label in ("sec:summary", "sec:model", "sec:clt", "sec:theory", "sec:reference", "sec:method", "sec:comparison", "sec:reading"):
        assert rf"\label{{{label}}}" in tex
    assert "59 of 59 compared values agree" in tex
    assert r"\filefrom" in tex and "unnotched-im7-8552-nodal.toml" in tex  # the spec is listed
    assert "Reading: the unnotched IM7/8552 coupon" in tex  # the reading note beside the record
    assert (tmp_path / "figures" / "differences.png").is_file() and (tmp_path / "figures" / "solution.png").is_file()
    assert not (tmp_path / "figures" / "element-map.png").exists()  # one probe element: no map
