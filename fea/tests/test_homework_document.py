"""One document per homework set, docs/problems/homework.py (ADR-0040): the physics once, a chapter per problem with labels of its
own, the reading, built in a temporary folder from the committed cases."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
HOMEWORK = ROOT / "docs/problems/homework.py"


def test_a_set_has_one_chapter_per_problem_and_labels_of_its_own(tmp_path):
    result = subprocess.run([sys.executable, str(HOMEWORK), "HW3", "--root", str(tmp_path), "--no-pdf", "--no-theory"],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    cases = sorted(p.stem for p in (ROOT / "engine/validation/cases").glob("se142-hw3-*.toml"))
    assert f"HW3: {len(cases)} problems" in result.stdout
    tex = (tmp_path / "HW3" / "documents" / "latex" / "HW3" / "HW3.tex").read_text(encoding="utf-8")
    assert r"\chapter{The physics: how our engine solves these problems}" in tex and r"\chapter{Reading}" in tex
    assert all(rf"\label{{ch:{stem}}}" in tex and rf"\label{{sec:comparison-{stem}}}" in tex for stem in cases)
    labels = re.findall(r"\\label\{([^}]+)\}", tex)
    assert len(labels) == len(set(labels)), "a label appears twice"
    assert set(re.findall(r"\\ref\{([^}]+)\}", tex)) <= set(labels), "a reference points nowhere"


def test_an_unknown_set_is_refused_by_name(tmp_path):
    result = subprocess.run([sys.executable, str(HOMEWORK), "HW9", "--root", str(tmp_path), "--no-pdf"], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode != 0 and "no committed case for HW9" in result.stdout + result.stderr
