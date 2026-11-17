"""A model brought in as an Abaqus deck (ADR-0105): the answer is the kernel's on the deck as it stands, the reading counts what the
reader took and names what it skipped, the preview draws the deck's own sets, supports and loads, a deck outside the subset is refused
with its line, and a deck the kernel cannot solve is still read. On the public check decks, nothing under .local/."""

import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.fields import field_data
from anisotropy_fea.imported import BY_ELEMENT, KIND, MAX_BYTES, import_model
from anisotropy_fea.kernel import solve_deck

DECKS = paths.CHECK_DECKS
STUDIO = Path(__file__).parents[1] / "tools" / "studio_tool.py"
GRIPS = DECKS / "coupon-2x8-grips-im7-8552.inp"
EDGE = DECKS / "coupon-2x2-im7-8552.inp"
UNITS = "mm-MPa"


PLACE = re.compile(r"at element \d+ \([^)]*\)")


def placeless(sentences: list[str]) -> list[str]:
    """Sentences with each element's number and centroid set aside: what is said, apart from which of two level elements is named."""
    return [PLACE.sub("at element N", sentence) for sentence in sentences]


def brought(path: Path, units: str = UNITS, text: str | None = None) -> dict:
    return import_model(path.read_bytes() if text is None else text.encode("utf-8"), path.name, units)


@pytest.mark.parametrize("name", sorted(p.name for p in DECKS.glob("*.inp")))
def test_every_public_check_deck_is_read_and_solved(name):
    answer = brought(DECKS / name)
    assert answer["state"] == "solved" and answer["problem"] is None
    json.dumps(answer)  # JSON-ready
    assert answer["reading"]["elements"] == answer["preview"]["mesh"]["element_count"] == answer["fields"]["mesh"]["element_count"]


def test_the_answer_is_the_kernels_on_the_deck_as_it_stands():
    answer = brought(GRIPS)
    deck = read_deck(GRIPS, UNITS)
    expected = field_data(deck, solve_deck(deck), UNITS, coupon=answer["fields"]["coupon"])
    assert answer["fields"]["nodal"]["displacement"] == expected["nodal"]["displacement"]
    assert answer["fields"]["summary"]["fpf"] == expected["summary"]["fpf"]
    assert answer["fields"]["coupon"]["kind"] == KIND and answer["fields"]["coupon"]["designation"] == GRIPS.stem
    assert answer["explanation"]["sentences"]


def test_the_reading_counts_what_was_taken_and_names_what_was_skipped():
    reading = brought(GRIPS)["reading"]
    assert (reading["nodes"], reading["reference_nodes"], reading["elements"], reading["couplings"]) == (27, 2, 16, 2)
    assert reading["element_types"] == {"S4R": 16} and reading["layup"] == "[0/30/-30/30/0]s" and reading["step"] == "Step-1"
    assert reading["sections"] == [{"element_set": "Layup-A-1", "plies": 10, "symmetric": True, "thickness": pytest.approx(1.8288),
                                    "materials": ["IM7-8552"], "rotation_deg": 0.0}]
    assert reading["materials"] == [{"name": "IM7-8552", "kind": "lamina", "strengths": True}]
    assert any("*preprint" in line for line in reading["skipped"]) and all(line.startswith("line ") for line in reading["skipped"])
    assert any("reference node" in note for note in reading["notes"])  # the reader's own note on this deck
    assert len(reading["sha256"]) == 64 and reading["warnings"] == []


def test_the_preview_draws_the_decks_own_supports_and_loads():
    preview = brought(GRIPS)["preview"]
    mesh = preview["mesh"]
    assert set(preview) >= {"units", "labels", "coupon", "geometry", "mesh", "held", "loaded", "loads", "plies", "material", "probes"}
    assert preview["coupon"]["kind"] == KIND and preview["geometry"]["width"] == pytest.approx(25.0) and preview["geometry"]["length"] == pytest.approx(100.0)
    # a support on a coupling's reference point holds the coupled surface's nodes, once per set whatever the lines of the deck
    assert [(h["set"], h["through"], h["dofs"]) for h in preview["held"]] == [("s_Bottom_CNS_", "Set-Encastre", [1, 2, 3, 4, 5, 6]),
                                                                              ("s_Top_CNS_", "Set-TopFix", [1, 3, 4, 5, 6])]
    assert preview["held"][0]["directions"][:2] == ["x", "y"]
    load = preview["loaded"]
    assert (load["set"], load["through"], load["control"], load["direction"], load["unit"]) == ("s_Top_CNS_", "Set-TopPull", "displacement", "+y", "mm")
    assert load["value"] == pytest.approx(0.8)
    for entry in [*preview["held"], *preview["loads"]]:
        assert len(mesh["node_sets"][entry["set"]]) == entry["nodes"] > 0
    assert all(0 <= k < mesh["node_count"] for nodes in mesh["node_sets"].values() for k in nodes)
    assert [ply["angle"] for ply in preview["plies"]] == [0, 30, -30, 30, 0, 0, 30, -30, 30, 0]
    material = preview["material"]
    assert material["name"] == "IM7-8552" and material["rights"] == "user-supplied" and "coupon-2x8-grips" in material["source"]
    assert material["E1"] == pytest.approx(162095.74) and material["strengths"]["F1t"] == pytest.approx(2558.51)


def test_a_force_is_the_whole_sets_and_a_pressure_stated_element_by_element_is_one_load_with_its_range():
    force = brought(DECKS / "coupon-1x1-cload-im7-8552.inp")["preview"]["loaded"]
    assert (force["control"], force["direction"], force["unit"], force["nodes"]) == ("force", "+y", "N", 2) and force["value"] == pytest.approx(1000.0)
    loads = brought(DECKS / "plate-ss-32x32-cross-ply-im7-8552.inp")["preview"]["loads"]
    assert len(loads) == 1 and loads[0]["set"] == BY_ELEMENT and loads[0]["control"] == "pressure"
    low, high = loads[0]["range"]
    assert low < high <= 0 and loads[0]["value"] == pytest.approx(low)  # the largest in magnitude
    uniform = brought(DECKS / "plate-ss-16x16-isotropic.inp")["preview"]["loads"]
    assert [(l["set"], "range" in l) for l in uniform] == [("All", False)]


@pytest.mark.parametrize(("change", "line", "words"), [
    (lambda t: t.replace("*Step", "*Include, input=/etc/hostname\n*Step", 1), 47, "*include is not supported"),
    (lambda t: t.replace("S4R", "C3D8R"), 15, "element type 'C3D8R' is not supported"),
    (lambda t: t.replace("nlgeom=NO", "nlgeom=YES"), 47, "nlgeom=YES"),
    (lambda t: "a letter, not a deck\n", 1, "data before any keyword"),
    (lambda t: "", None, "no *Step"),
])
def test_a_deck_outside_the_subset_is_refused_with_its_line(change, line, words):
    answer = brought(EDGE, text=change(EDGE.read_text(encoding="utf-8")))
    assert answer["state"] == "refused" and set(answer) == {"state", "name", "units", "problem"}
    assert answer["problem"]["line"] == line and words in answer["problem"]["message"]
    assert "README" not in answer["problem"]["message"] and "anisotropy_fea" not in answer["problem"]["message"]  # words for the engineer's screen


def test_a_file_that_is_no_deck_and_a_unit_system_nobody_states_are_refused():
    binary = import_model(b"\x00\x01\x02" + EDGE.read_bytes(), "model.cae", UNITS)
    assert binary["state"] == "refused" and "not text" in binary["problem"]["message"]
    large = import_model(b"*" * (MAX_BYTES + 1), "big.inp", UNITS)
    assert large["state"] == "refused" and str(MAX_BYTES) in large["problem"]["message"]
    units = brought(EDGE, "cm-kPa")
    assert units["state"] == "refused" and "units must be stated" in units["problem"]["message"]
    assert import_model(EDGE.read_bytes(), "../../etc/model.inp", UNITS)["name"] == "model.inp"  # a name, never a path


def test_a_generated_set_of_a_billion_labels_is_refused_before_it_is_built():
    text = EDGE.read_text(encoding="utf-8").replace("*Elset, elset=All, generate\n1, 4, 1\n", "*Elset, elset=All, generate\n1, 4, 1\n*Elset, elset=Huge, generate\n1, 4000000000, 1\n")
    answer = brought(EDGE, text=text)
    assert answer["state"] == "refused" and answer["problem"]["line"] == 23 and "generate lines of this deck name more than" in answer["problem"]["message"]


def test_the_stated_system_scales_the_values_and_a_modulus_far_from_any_material_is_warned():
    si, inch = brought(EDGE), brought(EDGE, "in-psi")
    assert inch["state"] == "solved" and inch["fields"]["labels"]["stress"] == "psi" and inch["preview"]["labels"]["length"] == "in"
    # the same digits read as inches and psi are the same strains, so the same failure factor, and stresses of the same digits
    for criterion, found in si["fields"]["summary"]["fpf"].items():
        assert inch["fields"]["summary"]["fpf"][criterion]["factor"] == pytest.approx(found["factor"], rel=1e-9)
    assert np.allclose(inch["fields"]["nodal"]["displacement"], si["fields"]["nodal"]["displacement"], rtol=1e-9, atol=1e-12)
    assert si["reading"]["warnings"] == [] and any("check that the deck is really written in 'in-psi'" in w for w in inch["reading"]["warnings"])


def test_a_deck_the_kernel_cannot_solve_is_still_read_and_drawn():
    text = EDGE.read_text(encoding="utf-8").replace("*Boundary\nBottom, 2, 2\n*Boundary\nCorner, 1, 1\n", "")
    answer = brought(EDGE, text=text)
    assert answer["state"] == "read" and "fields" not in answer and "explanation" not in answer
    assert "singular" in answer["problem"]["message"] and answer["problem"]["line"] is None
    assert answer["reading"]["boundaries"] == 1 and answer["preview"]["mesh"]["element_count"] == 4 and answer["preview"]["held"] == []


def run_tool(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(STUDIO), *args], capture_output=True, text=True, encoding="utf-8")


def test_the_studio_tool_writes_the_import_and_its_files(tmp_path):
    done = run_tool("import", str(GRIPS), "--units", UNITS, "--out", str(tmp_path / "solved"))
    assert done.returncode == 0 and done.stdout.startswith("solved: coupon-2x8-grips-im7-8552.inp"), done.stderr
    assert {p.name for p in (tmp_path / "solved").iterdir()} == {"import.json", "preview.json", "fields.json", "summary.json", "explanation.json", "timings.json"}
    head = json.loads((tmp_path / "solved" / "import.json").read_text(encoding="utf-8"))
    assert set(head) == {"state", "name", "units", "problem", "reading"} and head["reading"]["elements"] == 16
    fields = json.loads((tmp_path / "solved" / "fields.json").read_text(encoding="utf-8"))
    assert fields["summary"] == json.loads((tmp_path / "solved" / "summary.json").read_text(encoding="utf-8"))

    bad = tmp_path / "solid.inp"
    bad.write_text(EDGE.read_text(encoding="utf-8").replace("S4R", "C3D8R"), encoding="utf-8")
    done = run_tool("import", str(bad), "--units", UNITS, "--name", "their-name.inp", "--out", str(tmp_path / "refused"))
    assert done.returncode == 0 and done.stdout.startswith("refused: their-name.inp: line 15")  # the answer says; the exit code does not
    assert {p.name for p in (tmp_path / "refused").iterdir()} == {"import.json", "timings.json"}
    assert json.loads((tmp_path / "refused" / "import.json").read_text(encoding="utf-8"))["problem"]["line"] == 15


def test_the_warm_worker_answers_a_deck_between_live_solves(tmp_path):
    worker = subprocess.Popen([sys.executable, str(STUDIO), "--root", str(tmp_path / "root"), "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    try:
        assert json.loads(worker.stdout.readline())["ready"] is True
        for request, expected in (({"deck": str(EDGE), "units": UNITS, "name": "edge.inp", "out": str(tmp_path / "a")}, {"state": "solved"}),
                                  ({"deck": str(tmp_path / "missing.inp"), "units": UNITS, "out": str(tmp_path / "b")}, None),
                                  ({"deck": str(EDGE), "units": "in-psi", "out": str(tmp_path / "c")}, {"state": "solved"})):
            worker.stdin.write(json.dumps(request) + "\n")
            worker.stdin.flush()
            answer = json.loads(worker.stdout.readline())
            assert answer == expected if expected else "error" in answer
        assert json.loads((tmp_path / "a" / "import.json").read_text(encoding="utf-8"))["name"] == "edge.inp"
    finally:
        worker.stdin.close()
        worker.wait(timeout=30)


def test_the_pages_fixture_is_the_packages_answer_today():
    """tests/fixtures/studio-import is what the page's tests show of an imported model; it must be the package's answer to the public
    gripped coupon today (rewrite it with `uv run python tools/studio_tool.py import checks/decks/coupon-2x8-grips-im7-8552.inp --units
    mm-MPa --out ../tests/fixtures/studio-import`, then remove its timings.json and summary.json)."""
    folder = paths.ROOT / "tests" / "fixtures" / "studio-import"
    kept = {name: json.loads((folder / f"{name}.json").read_text(encoding="utf-8")) for name in ("import", "preview", "fields", "explanation")}
    answer = brought(GRIPS)
    without_digest = lambda head: {**head, "reading": {k: v for k, v in head["reading"].items() if k != "sha256"}}  # noqa: E731  (a checkout may change line ends)
    assert without_digest(kept["import"]) == without_digest({key: answer[key] for key in ("state", "name", "units", "problem", "reading")})
    for part in ("mesh", "held", "loads", "plies", "coupon"):
        assert kept["preview"][part] == answer["preview"][part], part
    assert kept["fields"]["mesh"]["quads"] == answer["fields"]["mesh"]["quads"] and set(kept["fields"]["summary"]) == set(answer["fields"]["summary"])
    for criterion, found in answer["fields"]["summary"]["fpf"].items():
        assert kept["fields"]["summary"]["fpf"][criterion]["factor"] == pytest.approx(found["factor"], rel=1e-9)
    assert np.allclose(kept["fields"]["nodal"]["displacement"], answer["fields"]["nodal"]["displacement"], rtol=1e-9, atol=1e-12)
    # The public coupon is the same seen from either end, so each extreme is held by two elements, level to the last digit, and which of
    # the two a machine names is round-off (CI named element 3 where the fixture names element 14, 2026-11-17). The sentences are held
    # with the element's number and place set aside, and the element the fixture names is held to carry today's extreme.
    assert placeless(kept["explanation"]["sentences"]) == placeless(answer["explanation"]["sentences"])
    assert kept["explanation"]["sentences"] != placeless(kept["explanation"]["sentences"])  # the sentences do name elements
    stress = np.asarray(answer["fields"]["element"]["ply"]["stress_12"])
    for column, quantity in enumerate(("S11", "S22", "S12")):
        today = answer["fields"]["summary"]["ply_extremes"]["overall"][quantity]
        for end, named in kept["fields"]["summary"]["ply_extremes"]["overall"][quantity].items():
            assert (named is None) == (today[end] is None), (quantity, end)
            if named is not None:
                assert named["ply"] == today[end]["ply"] and named["angle"] == today[end]["angle"], (quantity, end)
                assert abs(stress[named["element"], named["ply"] - 1, column]) == pytest.approx(abs(today[end]["value"]), rel=1e-8), (quantity, end)
    for criterion, found in answer["fields"]["summary"]["fpf"].items():
        named = kept["fields"]["summary"]["fpf"][criterion]
        ratio = answer["fields"]["element"]["failure"][criterion]["ratio"][named["element"]][named["ply"] - 1]
        assert ratio == pytest.approx(found["factor"], rel=1e-8) and (named["ply"], named["mode"], named["tied_plies"]) == (found["ply"], found["mode"], found["tied_plies"])
