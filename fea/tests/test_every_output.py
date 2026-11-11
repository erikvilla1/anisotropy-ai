"""Every output of ours for the team's engineers, and the comparison they run on it (ADR-0089 amendment 3): our file for the D3039 check,
and `tools/compare_every_output.py` on it beside an Abaqus-shaped file, run with the standard library only."""

from __future__ import annotations

import csv
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.every_output import COLUMNS, QUANTITIES, ZONES, top_reaction, write_ours
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.spec import load_spec

TOOLS = Path(__file__).parents[1] / "tools"
SCRIPT = TOOLS / "compare_every_output.py"
SPEC = paths.CHECKS / "d3039-im7-8552" / "d3039-im7-8552.toml"
ABAQUS_COLUMNS = COLUMNS[:-1]  # tools/abaqus_every_output.py's columns: ours without the zone


@pytest.fixture(scope="module")
def ours(tmp_path_factory):
    """Our every-output file of the D3039 check, from its committed deck, and the solution it came from."""
    folder = tmp_path_factory.mktemp("ours")
    spec = load_spec(SPEC)
    solution = solve_deck(read_deck(paths.deck_path(SPEC, "abaqus"), "mm-MPa"))
    rows = write_ours(folder / "ours-every-output.csv", folder / "ours-every-output.json", spec, solution, "mm-MPa", "d3039-im7-8552", "S4", "test")
    return folder, spec, solution, rows


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def theirs(folder: Path, ours_folder: Path, solution, spec, relabel: dict[int, int] | None = None, shift=(0.0, 0.0),
           change=None, drop: int = 0) -> Path:
    """An Abaqus-shaped run made from our own file: renumbered, moved, one value changed or elements dropped as asked."""
    folder.mkdir(parents=True, exist_ok=True)
    rows = read(ours_folder / "ours-every-output.csv")
    dropped = sorted({int(r["Element"]) for r in rows})[:drop]
    path = folder / "job-every-output.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(ABAQUS_COLUMNS)
        for r in rows:
            element = int(r["Element"])
            if element in dropped:
                continue
            values = {q: float(r[q]) for q in QUANTITIES}
            if change and (element, int(r["Layer"])) == change[0]:
                values[change[1]] *= change[2]
            writer.writerow([(relabel or {}).get(element, element), r["Layer"], f'"fraction = 0, Layer = {r["Layer"]}"',
                             float(r["X"]) + shift[0], float(r["Y"]) + shift[1], *(values[q] for q in QUANTITIES)])
    meta = json.loads((ours_folder / "ours-every-output.json").read_text(encoding="utf-8"))
    from anisotropy_fea.units import from_si
    with (folder / "job-every-output-RF.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["Node", "X", "Y", "RF1", "RF2"])
        for i, key in enumerate(solution.mesh.node_keys):
            x, y = (float(from_si(v, "length", "mm-MPa")) for v in solution.mesh.xy[i])
            if y >= meta["reaction"]["top_from"] - 1e-6:
                writer.writerow([key[1], x + shift[0], y + shift[1], 0.0, float(from_si(solution.reaction[i, 1], "force", "mm-MPa"))])
    return path


def compare(ours_folder: Path, job: Path, *extra: str) -> subprocess.CompletedProcess:
    """The team's comparison as they run it, under a Python with no site packages: it must need the standard library alone."""
    return subprocess.run([sys.executable, "-I", "-S", str(SCRIPT), str(ours_folder / "ours-every-output.csv"), str(job), *extra],
                          capture_output=True, text=True, encoding="utf-8")


def test_our_file_holds_every_element_and_ply_in_the_exporters_columns_with_its_zone_and_our_reaction(ours):
    folder, spec, solution, count = ours
    rows = read(folder / "ours-every-output.csv")
    assert tuple(rows[0]) == COLUMNS and count == len(rows) == 1488 * 8
    zones = {int(r["Element"]): r["Zone"] for r in rows}
    assert {zone: sum(1 for z in zones.values() if z == zone) for zone in ZONES} == {
        "gauge": 144, "free length": 384, "band": 264, "tab line": 24, "gripped": 672}  # as tools/abaqus_compare.py draws them
    for r in rows[:64]:  # Tresca is the largest principal less the smallest, the zero through the thickness among them
        principals = [float(r[q]) for q in ("Max. Principal", "Mid. Principal", "Min. Principal")]
        assert float(r["Tresca"]) == pytest.approx(max(principals) - min(principals), abs=1e-9 * max(1.0, abs(float(r["Tresca"]))))
    meta = json.loads((folder / "ours-every-output.json").read_text(encoding="utf-8"))
    nodes, reaction = top_reaction(solution, spec, "mm-MPa")
    assert meta["reaction"] == {"along": "Y", "top_from": 194.0, "nodes": nodes, "ours": reaction} and reaction > 0
    assert meta["acceptance"] == {"reaction": 0.01, "gauge": 0.01, "free length": 0.03} and meta["element"] == "S4"
    assert meta["quantities"] == list(QUANTITIES) and meta["layers"] == 8 and meta["stress_unit"] == "MPa"


def test_the_script_names_the_same_quantities_and_zones_as_our_file():
    namespace: dict = {}
    source = SCRIPT.read_text(encoding="utf-8")
    exec(compile(source.split("class Refused")[0], str(SCRIPT), "exec"), namespace)  # its constants, without running it
    assert namespace["QUANTITIES"] == QUANTITIES and namespace["ZONES"] == ZONES


def test_our_values_beside_themselves_agree_everywhere_and_meet_the_acceptance(ours, tmp_path):
    folder, spec, solution, _ = ours
    job = theirs(tmp_path / "run", folder, solution, spec)
    done = compare(folder, job, "--out", str(tmp_path / "pairs.csv"))
    assert done.returncode == 0, done.stderr
    assert "by element number: your elements are ours" in done.stdout
    assert "ours +0.000 % from yours" in done.stdout
    for line in ("met: Reaction within 1 %", "met: Gauge: every value within 1 %", "met: Free length: every value within 3 %"):
        assert line in done.stdout, line
    pairs = read(tmp_path / "pairs.csv")
    assert len(pairs) == 1488 * 8 and all(float(p["S11 difference (%)"]) == 0 for p in pairs)


def test_a_coupon_built_in_cae_is_paired_by_position_even_when_numbered_and_placed_otherwise(ours, tmp_path):
    folder, spec, solution, _ = ours
    labels = sorted({int(r["Element"]) for r in read(folder / "ours-every-output.csv")})
    shuffled = labels[:]
    random.Random(7).shuffle(shuffled)
    job = theirs(tmp_path / "cae", folder, solution, spec, relabel={a: b + 10000 for a, b in zip(labels, shuffled)}, shift=(-12.5, -125.0))
    done = compare(folder, job)
    assert done.returncode == 0, done.stderr
    assert "by position" in done.stdout and "after moving your coupon by (12.5, 125)" in done.stdout
    assert "met: Gauge: every value within 1 %" in done.stdout and "met: Reaction within 1 %" in done.stdout


def test_a_gauge_value_two_percent_off_fails_the_verdict_and_says_where(ours, tmp_path):
    folder, spec, solution, _ = ours
    gauge = next(r for r in read(folder / "ours-every-output.csv") if r["Zone"] == "gauge" and r["Layer"] == "2")
    element = int(gauge["Element"])
    job = theirs(tmp_path / "off", folder, solution, spec, change=((element, 2), "S11", 1.02))
    done = compare(folder, job)
    assert done.returncode == 1
    assert "NOT MET: Gauge: every value within 1 %" in done.stdout and "met: Free length: every value within 3 %" in done.stdout
    s11 = next(line for line in done.stdout.split("gauge (")[1].splitlines() if line.strip().startswith("S11"))
    assert "1151/1152 within 1 %" in s11 and f"at our element {element} (yours {element}) ply 2" in s11


def test_another_mesh_is_refused_and_says_why(ours, tmp_path):
    folder, spec, solution, _ = ours
    done = compare(folder, theirs(tmp_path / "coarse", folder, solution, spec, drop=12))
    assert done.returncode != 0 and "refused: your model has 1476 elements and ours 1488: not the same mesh" in done.stderr
    labels = sorted({int(r["Element"]) for r in read(folder / "ours-every-output.csv")})
    rotated = tmp_path / "rotated"
    job = theirs(rotated, folder, solution, spec, relabel={label: label + 5000 for label in labels})
    rows = read(job)
    with job.open("w", encoding="utf-8", newline="") as handle:  # the coupon drawn with its length along X
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows({**r, "X": r["Y"], "Y": r["X"]} for r in rows)
    done = compare(folder, job)
    assert done.returncode != 0 and "have no element of yours at the same place" in done.stderr and "along Y" in done.stderr


def test_the_script_and_the_odb_readers_it_ships_with_import_nothing_beyond_the_standard_library():
    """The package copies these three into 5-verify/ for Abaqus's own Python: none may import our package or numpy."""
    import ast

    allowed = set(sys.stdlib_module_names) | {"abaqus_extract_fields", "abaqusConstants", "odbAccess"}
    for name in ("compare_every_output.py", "abaqus_every_output.py", "abaqus_extract_fields.py"):
        tree = ast.parse((TOOLS / name).read_text(encoding="utf-8"))
        imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        imported |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        assert imported <= allowed, (name, imported - allowed)
