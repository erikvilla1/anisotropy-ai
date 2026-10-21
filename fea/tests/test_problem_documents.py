"""The solved-problem document generator, docs/problems/build.py (ADR-0033): one document per validation case."""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
BUILD = ROOT / "docs/problems/build.py"
CASES = ROOT / "engine/validation/cases"


def run(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(BUILD), *arguments], capture_output=True, text=True, cwd=ROOT)


def test_the_generator_documents_a_thermal_bending_failure_problem(tmp_path):
    case = CASES / "se142-hw5-p1-thermal-bending-laminate.toml"
    result = run(str(case), "--out", str(tmp_path), "--no-pdf")
    assert result.returncode == 0, result.stdout + result.stderr
    tex = (tmp_path / "se142-hw5-p1-thermal-bending-laminate.tex").read_text(encoding="utf-8")
    assert tex.startswith(r"\documentclass") and tex.rstrip().endswith(r"\end{document}")
    for label in ("sec:summary", "sec:problem", "sec:steps", "sec:comparison", "sec:method", "sec:reading"):
        assert rf"\label{{{label}}}" in tex
    assert "28 of 28 compared values agree" in tex
    # the steps this problem needs, in order, each with its theory section and the code it names
    for step in ("Step 1. Ply stiffness", "Step 2. Rotation", "Step 3. Laminate stiffness", "Step 4. Temperature change", "Step 5. Mid-plane strains",
                 "Step 6. Strain and stress in every ply", "Step 7. First-ply failure", "Step 8. Laminate engineering constants"):
        assert step in tex, step
    assert tex.index("Step 4. Temperature") < tex.index("Step 5. Mid-plane") < tex.index("Step 7. First-ply")
    assert r"\codefrom{thermal\_resultants}" in tex and r"\codefrom{first\_ply\_failure\_combined}" in tex and r"\codefrom{solve\_case}" in tex
    assert "transverse tension" in tex and r"\Delta T" in tex  # the governing mode and the temperature change
    assert "Reading: SE142/253A Homework 5" in tex  # the set's reading note, matched by prefix
    assert r"\filefrom" in tex and "fpf_ratio_max_stress" in tex  # the case file is in the appendix


def test_a_mixed_condition_problem_has_no_thermal_or_failure_step_and_names_the_known_quantities(tmp_path):
    case = CASES / "se142-hw2-p2-cr-3-8-walls-30deg.toml"
    result = run(str(case), "--out", str(tmp_path), "--no-pdf", "--no-theory")
    assert result.returncode == 0, result.stdout + result.stderr
    tex = (tmp_path / "se142-hw2-p2-cr-3-8-walls-30deg.tex").read_text(encoding="utf-8")
    assert "13 of 13 compared values agree" in tex
    assert "Step 4. Mid-plane strains" in tex and "Temperature change" not in tex.split(r"\section{The solution")[1].split(r"\section{Every compared")[0]
    assert "First-ply failure" not in tex.split(r"\section{The solution")[1].split(r"\section{Every compared")[0]
    assert r"\codefrom" not in tex.split(r"\section{The solution")[1].split(r"\section{Every compared")[0]  # --no-theory
    assert r"\varepsilon^0_x$, $\varepsilon^0_y$, $\tau_{xy}$" in tex  # the known quantities of the mixed problem
    assert r"\bar{\mathbf{S}}" in tex  # a single lamina shows its transformed compliance


def test_reading_notes_are_matched_by_the_longest_prefix():
    spec = importlib.util.spec_from_file_location("problems_build", BUILD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.reading_note(CASES / "se142-hw3-p3a-boron-symmetric.toml").name == "se142-hw3.md"
    assert module.reading_note(CASES / "course-reader-5-9-sglass-curing.toml").name == "course-reader-5-9.md"
    assert module.reading_note(CASES / "daniel-ishai-problem-7-11.toml") is None
    assert set(module.FRAGMENTS) >= {"Ply stiffness", "Rotation", "Laminate stiffness", "Response to loads", "Known forces and prescribed curvature",
                                     "Mixed load and deformation conditions", "Ply surface recovery", "Failure", "Fixed and variable loading",
                                     "Laminate engineering constants", "Temperature change", "Plate buckling"}
