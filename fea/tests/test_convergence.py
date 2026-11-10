"""The mesh convergence study (ADR-0068): the refinements keep the tab lines on node rows, the gauge values settle while the clamped-edge
peaks grow, a coupon the study does not cover gets a reason and not an error, and the tool writes the file a run reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from anisotropy_fea import paths
from anisotropy_fea.convergence import CAP, SETTLED, ConvergenceError, changes_of, convergence_study, refined, relative_change, settled_of
from anisotropy_fea.spec import load_spec, mesh_counts, node_lines, row_coordinates

sys.path.insert(0, str(paths.FEA / "tools"))
import convergence_study as tool  # noqa: E402

PUBLIC = paths.FEA / "checks" / "unnotched-im7-8552" / "unnotched-im7-8552-nodal.toml"


@pytest.fixture(scope="module")
def spec():
    return load_spec(PUBLIC)


@pytest.fixture(scope="module")
def study(spec):
    return convergence_study(spec, factors=(1, 2))  # the finest mesh is left to the tool's default run: two meshes hold the contract in a few seconds


def test_a_refinement_splits_every_element_and_keeps_the_tab_lines_on_node_rows(spec):
    assert refined(spec, 1) is spec
    twice = refined(spec, 2)
    assert mesh_counts(twice) == (2 * spec.mesh.nx, 2 * spec.mesh.ny)
    rows = [k * twice.geometry.length / mesh_counts(twice)[1] for k in range(mesh_counts(twice)[1] + 1)]
    for y in node_lines(spec).values():
        assert min(abs(r - y) for r in rows) < 1e-9  # the tab lines fall on node rows of the finer mesh too
    seeded = spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"ny": None, "y_partitions": [0.056, 0.194], "y_seeds": [28, 69, 28]})})
    assert refined(seeded, 2).mesh.y_seeds == [56, 138, 56] and refined(seeded, 2).mesh.nx == 2 * spec.mesh.nx
    assert row_coordinates(refined(seeded, 2))[56] == pytest.approx(0.056)
    sized = spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"nx": None, "ny": None, "element_size": 0.002})})
    assert refined(sized, 4).mesh.element_size == pytest.approx(0.0005)
    with pytest.raises(ConvergenceError, match="whole number"):
        refined(spec, 0)
    gmsh = spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"mesher": "gmsh"})})
    with pytest.raises(ConvergenceError, match="structured mesh only"):
        refined(gmsh, 2)


def test_the_gauge_values_settle_and_the_clamped_edge_peaks_grow(study):
    assert study["studied"] and [m["factor"] for m in study["meshes"]] == [1, 2] and study["left_out"] == []
    coarse, fine = study["meshes"]
    assert (coarse["nx"], coarse["ny"], coarse["elements"]) == (10, 125, 1250) and (fine["nx"], fine["ny"], fine["elements"]) == (20, 250, 5000)
    assert coarse["gauge_element"] == 626  # the record's centre probe (ADR-0066), by the model's own nearest-element rule
    assert coarse["reaction"] == pytest.approx(16211.75, abs=0.01) and abs(study["changes"]["reaction"][1]) < 1e-3
    assert study["changes"]["reaction"][0] is None
    for k in range(len(coarse["plies"])):
        assert all(c is None or abs(c) < SETTLED for c in study["changes"]["plies"][k]["stress_12"][1])
    assert coarse["peaks"][1]["touches_grip"] and fine["peaks"][1]["touches_grip"]  # the 0° ply peaks at the clamped edge
    assert study["changes"]["peaks"][1]["s1"][1] > 0.1  # and its corner value grows by more than a tenth per refinement
    assert abs(study["changes"]["peaks"][3]["s1"][1]) < SETTLED  # the 90° ply's (compression along its fibres, across the width) does not: not every peak is singular
    assert study["settled"] == {"reaction": True, "gauge_strain": True, "plies": True, "peaks": False, "fpf": False, "fpf_gauge": False}
    assert set(coarse["fpf"]) == {"max_stress", "tsai_hill", "tsai_wu"} and fine["fpf"]["tsai_wu"] < coarse["fpf"]["tsai_wu"]
    assert coarse["solve_s"] > 0  # a timing is recorded
    assert "ADR-0066" in study["note"] and study["settled_below"] == SETTLED and study["cap"] == CAP


def test_a_change_is_read_against_the_triples_largest_component():
    assert relative_change(100.0, 101.0) == pytest.approx(0.01 / 1.01)
    assert relative_change(1.0, 0.0) is None
    meshes = [{"reaction": 100.0, "gauge_strain": [1e-3, 2e-3, 1e-15], "plies": [{"stress_12": [500.0, 1.0, 1e-14]}], "peaks": [{"s1": 500.0}],
               "fpf": {"a": 1.0}, "fpf_gauge": {"a": 1.1}},
              {"reaction": 100.1, "gauge_strain": [1e-3, 2e-3, 1e-13], "plies": [{"stress_12": [500.2, 1.0, 5e-14]}], "peaks": [{"s1": 560.0}],
               "fpf": {"a": 0.9}, "fpf_gauge": {"a": 1.1}}]
    changes = changes_of(meshes)
    assert changes["gauge_strain"][1][2] == pytest.approx(0.99e-13 / 2e-3)  # noise against the largest component, not against itself
    assert changes["plies"][0]["stress_12"][1][2] == pytest.approx(4e-14 / 500.2)
    assert changes["peaks"][0]["s1"][1] == pytest.approx(60.0 / 560.0) and changes["fpf"]["a"][1] == pytest.approx(-0.1 / 0.9)
    assert settled_of(changes) == {"reaction": True, "gauge_strain": True, "plies": True, "peaks": False, "fpf": False, "fpf_gauge": True}


def test_a_coupon_the_study_does_not_cover_gets_a_reason_not_an_error(spec):
    bending = spec.model_copy(update={"kind": "three_point_bending"})
    out = convergence_study(bending, factors=(1, 2))
    assert out["studied"] is False and "bending" in out["reason"] and out["meshes"] == []
    gmsh = spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"mesher": "gmsh"})})
    assert convergence_study(gmsh, factors=(1, 2))["reason"].startswith("the study refines a structured mesh only")
    capped = convergence_study(spec, factors=(1, 2), cap=2000)
    assert capped["studied"] is False and capped["left_out"] == [{"factor": 2, "elements": 5000, "reason": "5000 elements is past the study's cap of 2000"}]
    assert len(capped["meshes"]) == 1 and "fewer than two meshes" in capped["reason"]
    with pytest.raises(ConvergenceError, match="rising order"):
        convergence_study(spec, factors=(2, 1))


def test_the_tool_prints_the_table_and_writes_the_file(tmp_path, capsys):
    out = tmp_path / "unnotched-convergence.json"
    assert tool.main([str(PUBLIC), "--out", str(out), "--factors", "1", "2"]) == 0
    text = capsys.readouterr().out
    assert "2 meshes: 1x = 10 by 125, 1250 elements" in text and "reaction at Grip-Top, N" in text and "ply 2 (0 deg) sigma_1, gauge" in text
    assert "ply 2 largest |sigma_1| (clamped edge)" in text and "settled (last change under 1 %): reaction yes" in text and "peaks no" in text
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["studied"] and written["units"] == "mm-MPa" and len(written["meshes"]) == 2
    assert tool.main([str(tmp_path / "missing.toml")]) == 2
    assert "spec refused" in capsys.readouterr().err
