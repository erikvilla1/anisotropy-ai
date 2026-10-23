"""One document per homework set, docs/problems/homework.py (ADR-0040): the physics once, a chapter per problem with labels of its
own, the reading, built in a temporary folder from the committed cases."""

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
HOMEWORK = ROOT / "docs/problems/homework.py"


def test_a_set_has_one_chapter_per_problem_and_labels_of_its_own(tmp_path):
    reading = tmp_path / "HW3" / "comparison" / "key-comparison.md"
    reading.parent.mkdir(parents=True)
    reading.write_text("# Reading: a test note for HW3\n\nWritten by the test.\n", encoding="utf-8")
    result = subprocess.run([sys.executable, str(HOMEWORK), "HW3", "--root", str(tmp_path), "--no-pdf", "--no-theory"],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    cases = sorted(p.stem for p in (ROOT / "engine/validation/cases").glob("se142-hw3-*.toml"))
    assert f"HW3: {len(cases)} problems" in result.stdout
    tex = (tmp_path / "HW3" / "documents" / "HW3.tex").read_text(encoding="utf-8")
    assert sorted(p.name for p in (tmp_path / "HW3" / "documents").iterdir()) == ["HW3.tex"]  # one document, no copy
    assert r"\chapter{The physics: how our engine solves these problems}" in tex and r"\chapter{Reading}" in tex
    assert "Reading: a test note for HW3" in tex and "Written by the test." in tex  # the set's reading, from its comparison/ under --root
    assert all(rf"\label{{ch:{stem}}}" in tex and rf"\label{{sec:comparison-{stem}}}" in tex for stem in cases)
    labels = re.findall(r"\\label\{([^}]+)\}", tex)
    assert len(labels) == len(set(labels)), "a label appears twice"
    assert set(re.findall(r"\\ref\{([^}]+)\}", tex)) <= set(labels), "a reference points nowhere"


def test_the_build_writes_the_engines_output_beside_the_reading(tmp_path):
    result = subprocess.run([sys.executable, str(HOMEWORK), "HW3", "--root", str(tmp_path), "--no-pdf", "--no-theory"],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    cases = sorted(p.stem for p in (ROOT / "engine/validation/cases").glob("se142-hw3-*.toml"))
    comparison = tmp_path / "HW3" / "comparison"
    assert sorted(p.name for p in comparison.iterdir()) == sorted([f"{stem}.json" for stem in cases] + ["key-vs-engine.csv"])
    compared = int(re.search(r"HW3: \d+ problems, \d+ of (\d+) values agree", result.stdout)[1])
    with (comparison / "key-vs-engine.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == compared and {row["problem"] for row in rows} == set(cases)
    first = json.loads((comparison / f"{cases[0]}.json").read_text(encoding="utf-8"))
    assert first["case"] == f"engine/validation/cases/{cases[0]}.toml" and first["results"] and first["problems"] == []
    mine = [row for row in rows if row["problem"] == cases[0]]
    assert [(c["key"], "yes" if c["agrees"] else "no") for c in first["comparison"]] == [(row["result"], row["agrees"]) for row in mine]
    assert all(float(row["engine"]) == float(f"{c['engine']:.9g}") for row, c in zip(mine, first["comparison"]))  # the CSV is the JSON's numbers


def test_an_unknown_set_is_refused_by_name(tmp_path):
    result = subprocess.run([sys.executable, str(HOMEWORK), "HW9", "--root", str(tmp_path), "--no-pdf"], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode != 0 and "no committed case for HW9" in result.stdout + result.stderr
