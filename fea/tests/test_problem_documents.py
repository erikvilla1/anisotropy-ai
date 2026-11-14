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


def test_the_generator_documents_a_thermal_failure_problem(tmp_path):
    case = CASES / "constructed-cross-ply-cooling-first-ply-failure.toml"
    result = run(str(case), "--out", str(tmp_path), "--no-pdf")
    assert result.returncode == 0, result.stdout + result.stderr
    tex = (tmp_path / f"{case.stem}.tex").read_text(encoding="utf-8")
    assert tex.startswith(r"\documentclass") and tex.rstrip().endswith(r"\end{document}")
    for label in ("sec:summary", "sec:problem", "sec:steps", "sec:comparison", "sec:method"):
        assert rf"\label{{{label}}}" in tex
    # no reading has been written for this case: the document has no Reading section and no instruction to us to write one
    assert r"\label{sec:reading}" not in tex and "To add one, write" not in tex and "No reading has been written" not in tex
    assert "14 of 14 compared values agree" in tex
    # the steps this problem needs, in order, each with its theory section and the code it names
    for step in ("Step 1. Ply stiffness", "Step 2. Rotation", "Step 3. Laminate stiffness", "Step 4. Temperature change", "Step 5. Mid-plane strains",
                 "Step 6. Strain and stress in every ply", "Step 7. First-ply failure", "Step 8. Laminate engineering constants"):
        assert step in tex, step
    assert tex.index("Step 4. Temperature") < tex.index("Step 5. Mid-plane") < tex.index("Step 7. First-ply")
    assert r"\codefrom{thermal\_resultants}" in tex and r"\codefrom{first\_ply\_failure\_combined}" in tex
    # the case runner, the same for every problem, is printed once, in the engine manual, and pointed to here
    assert r"\codefrom{solve\_case}" not in tex and "printed once, in the engine manual" in tex
    assert "transverse tension" in tex and r"\Delta T" in tex  # the governing mode and the temperature change
    assert r"\filefrom" in tex and "fpf_ratio_max_stress" in tex  # the case file is in the appendix


def test_a_mixed_condition_problem_has_no_thermal_or_failure_step_and_names_the_known_quantities(tmp_path):
    case = CASES / "constructed-mixed-angle-lamina.toml"
    result = run(str(case), "--out", str(tmp_path), "--no-pdf", "--no-theory")
    assert result.returncode == 0, result.stdout + result.stderr
    tex = (tmp_path / f"{case.stem}.tex").read_text(encoding="utf-8")
    assert "6 of 6 compared values agree" in tex
    steps = tex.split(r"\section{The solution")[1].split(r"\section{Every compared")[0]
    assert "Step 4. Mid-plane strains" in tex and "Temperature change" not in steps
    assert "First-ply failure" not in steps
    assert r"\codefrom" not in steps  # --no-theory
    assert r"Known quantities: $\sigma_x$, $\varepsilon^0_y$, $\tau_{xy}$" in tex  # the known quantities of the mixed problem
    assert r"\bar{\mathbf{S}}" in tex  # a single lamina shows its transformed compliance


def load_build():
    spec = importlib.util.spec_from_file_location("problems_build", BUILD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_homework_case_prints_the_reading_of_its_set(tmp_path):
    module = load_build()
    note = tmp_path / "HW3" / "comparison" / "key-comparison.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Reading: a test note\n\nWritten by the test.\n", encoding="utf-8")
    case = tmp_path / "HW3" / "ours" / "p1.toml"  # a homework case sits in its set's ours/ (ADR-0042)
    assert module.reading_note(case) == note
    assert module.reading_note(CASES / "daniel-ishai-problem-7-11.toml") is None  # not in a set, and nothing beside it
    text, found = module.reading_section(case)
    assert found and "Reading: a test note" in text and "Written by the test." in text
    text, found = module.reading_section(tmp_path / "HW5" / "ours" / "p1.toml")  # HW5 has no note
    assert not found and "HW5/comparison/key-comparison.md" in text.replace(r"\allowbreak{}", "")  # names where to write it


def test_every_step_has_its_theory_fragment():
    module = load_build()
    assert set(module.FRAGMENTS) >= {"Ply stiffness", "Rotation", "Laminate stiffness", "Response to loads", "Known forces and prescribed curvature",
                                     "Mixed load and deformation conditions", "Ply surface recovery", "Failure", "Fixed and variable loading",
                                     "Laminate engineering constants", "Temperature change", "Plate buckling"}


def test_a_result_is_named_for_a_reader_and_counted_in_words():
    build = load_build()
    assert build.result_label("fpf_ratio_max_stress").startswith("the first-ply-failure strength ratio by maximum stress")
    assert "fpf" in build.result_label("fpf_ratio_max_stress") and build.result_label("Ex") == build.code("Ex")
    assert build.plural(1, "number") == "1 number" and build.plural(2, "ply", "plies") == "2 plies" and build.plural(1, "ply", "plies") == "1 ply"
    assert build.material_name({"material": {}}, "material") == "The case's material" and build.material_name({}, "AS4") == "AS4"


def test_a_source_formula_keeps_its_products(tmp_path):
    """The audit of 2026-11-12 found the source note 'nu21 = 0.27*10.3/147, ... N*m' printed as 'nu21 = 0.27\\emph{10.3/147 ...}': a star
    inside a word is a product, never emphasis, on the cover, in the problem section and in the manual's validation table."""
    build = load_build()
    assert build.inline("nu21 = 0.27*10.3/147, D11 = 10.881625 N*m") == "nu21 = 0.27*10.3/147, D11 = 10.881625 N*m"
    assert build.inline("(1000 - 0.27*20) and nu21*1000") == "(1000 - 0.27*20) and nu21*1000"
    assert build.inline("a *stated* choice, *Finite Element Procedures*.") == r"a \emph{stated} choice, \emph{Finite Element Procedures}."
    case = CASES / "constructed-cross-ply-plate-buckling.toml"
    result = run(str(case), "--out", str(tmp_path), "--no-pdf", "--no-theory")
    assert result.returncode == 0, result.stdout + result.stderr
    tex = (tmp_path / f"{case.stem}.tex").read_text(encoding="utf-8")
    assert r"\emph" not in tex.split(r"\section{The solution")[0] and tex.count("0.27*10.3/147") >= 2  # the cover and the problem section
    assert "as the case gives them; the engine converts them to SI on entry and back on exit." in tex and "and back on exit (ADR-0002)" not in tex

