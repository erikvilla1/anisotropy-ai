"""A model sent from Abaqus beside a run of ours (ADR-0094, step 1): `tools/abaqus_upload.py` on bundles made from the public D3039
check. Their side is our own kernel's run written in the shape Abaqus's exporter gives, on our mesh, drawn elsewhere, in the other deck
system, on a coarser mesh, and changed where a difference must be found. No Abaqus runs here; a real run's bundle is checked on the
founder's machine."""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.bundle import write_bundle
from anisotropy_fea.every_output import COLUMNS, QUANTITIES, write_ours
from anisotropy_fea.femodel import build_model
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.spec import load_spec
from anisotropy_fea.units import from_si
from anisotropy_fea.write_abaqus import write_abaqus

TOOLS = Path(__file__).parents[1] / "tools"
SPEC = paths.CHECKS / "d3039-im7-8552" / "d3039-im7-8552.toml"
STRESSES = QUANTITIES[:9]


@pytest.fixture(scope="module")
def tool():
    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location("abaqus_upload", TOOLS / "abaqus_upload.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.path.remove(str(TOOLS))
        sys.modules.pop(spec.name, None)


def run_of(folder: Path, spec, name: str) -> dict:
    """A run of the spec by our kernel: the deck, our every-output file with its JSON, and the same values in the exporter's shape
    (its columns, and the reaction at every node that carries one). Returns the rows and the reactions as numbers."""
    folder.mkdir(parents=True)
    deck = folder / f"{name}.inp"
    deck.write_text(write_abaqus(build_model(spec)), encoding="utf-8", newline="\n")
    solution = solve_deck(read_deck(deck, "mm-MPa"))
    write_ours(folder / "ours-every-output.csv", folder / "ours-every-output.json", spec, solution, "mm-MPa", name, "S4", "test")
    with (folder / "ours-every-output.csv").open(encoding="utf-8", newline="") as handle:
        rows = [{c: r[c] for c in COLUMNS[:-1]} for r in csv.DictReader(handle)]
    reactions = []
    for i, key in enumerate(solution.mesh.node_keys):
        x, y = (float(from_si(v, "length", "mm-MPa")) for v in solution.mesh.xy[i])
        rf = [float(from_si(v, "force", "mm-MPa")) for v in solution.reaction[i, :2]]
        if any(rf):
            reactions.append({"Node": key[1], "X": x, "Y": y, "RF1": rf[0], "RF2": rf[1]})
    return {"folder": folder, "deck": deck, "rows": rows, "reactions": reactions}


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    """Our run of the D3039 check, and the same coupon on a mesh half as fine."""
    root = tmp_path_factory.mktemp("runs")
    spec = load_spec(SPEC)
    coarse = spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"nx": 6, "y_seeds": [14, 14, 6, 14, 14]})})
    return {"ours": run_of(root / "ours", spec, "d3039"), "coarse": run_of(root / "coarse", coarse, "coarse")}


def moved_nodes(text: str, change) -> str:
    """The deck with every node's x and y passed through `change`: a coupon drawn elsewhere, or in another length unit."""
    head, rest = text.split("*Node\n", 1)
    block, tail = rest.split("*", 1)
    lines = []
    for line in block.splitlines():
        label, x, y, z = (part.strip() for part in line.split(","))
        nx, ny = change(float(x), float(y))
        lines.append(f"{label}, {nx!r}, {ny!r}, {z}")
    return head + "*Node\n" + "\n".join(lines) + "\n*" + tail


def bundle_of(folder: Path, run: dict, deck_text: str | None = None, change=None, units: str = "mm-MPa", rf: bool = True, drop_layer: int = 0,
              move=(0.0, 0.0), scale: float = 1.0) -> Path:
    """A bundle of a run as the connector will write it, changed as asked: `change(row)` edits one row's values in place, `move` and
    `scale` place the coupon elsewhere or resize it (the deck's nodes too), `units` writes the numbers in that deck system."""
    folder.mkdir(parents=True)
    length, stress = (1e-3, 1e6) if units == "m-Pa" else (1.0, 1.0)
    place = lambda x, y: ((x * scale + move[0]) * length, (y * scale + move[1]) * length)  # noqa: E731
    text = run["deck"].read_text(encoding="utf-8") if deck_text is None else deck_text
    if move != (0.0, 0.0) or scale != 1.0:
        text = moved_nodes(text, lambda x, y: (x * scale + move[0], y * scale + move[1]))
    deck = folder / "Job-1.inp"
    deck.write_text(text, encoding="utf-8", newline="\n")
    every = folder / "Job-1-every-output.csv"
    with every.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMNS[:-1])
        for source in run["rows"]:
            if drop_layer and int(source["Layer"]) == drop_layer:
                continue
            row = dict(source)
            if change:
                change(row)
            x, y = place(float(row["X"]), float(row["Y"]))
            writer.writerow([row["Element"], row["Layer"], f'"fraction = 0, Layer = {row["Layer"]}"', repr(x), repr(y)]
                            + [repr(float(row[q]) * (stress if q in STRESSES else 1.0)) for q in QUANTITIES])
    files = {"deck": deck, "every_output": every}
    if rf:
        files["reactions"] = folder / "Job-1-every-output-RF.csv"
        with files["reactions"].open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(["Node", "X", "Y", "RF1", "RF2"])
            for r in run["reactions"]:
                x, y = place(r["X"], r["Y"])
                writer.writerow([r["Node"], repr(x), repr(y), repr(r["RF1"]), repr(r["RF2"])])
    write_bundle(folder / "bundle.zip", files, units, "test 1", abaqus="Abaqus/Standard 2025", job="Job-1", created="2026-11-12T21:36:00Z")
    return folder / "bundle.zip"


def compared(tool, runs, bundle: Path, **options) -> dict:
    ours = runs["ours"]
    return tool.compare(bundle, ours["folder"] / "ours-every-output.csv", ours["deck"], **options)


def criteria(result: dict) -> dict:
    return {c["criterion"]: c["met"] for c in result["criteria"]}


def test_our_own_run_sent_back_agrees_item_by_item_and_value_by_value(tool, runs, tmp_path):
    result = compared(tool, runs, bundle_of(tmp_path / "same", runs["ours"]), pairs_out=tmp_path / "pairs.csv")
    assert result["verdict"] == "agrees"
    model = result["model"]
    assert model["compared"] == "item by item" and model["same"] is True and model["largest_node_offset"] == 0.0
    assert not [i for i in model["items"] if i["same"] is False] and {"Layup, bottom first", "Boundary conditions, node by node"} <= {i["item"] for i in model["items"]}
    assert result["pairing"] == {"same_mesh": True, "how": "by element number: your elements are ours", "elements": 1488, "moved_by": [0.0, 0.0]}
    assert criteria(result) == {"Reaction within 1 %": True, "Gauge: every value within 1 %": True, "Free length: every value within 3 %": True}
    assert result["reaction"]["difference"] == pytest.approx(0.0, abs=1e-12) and 0 < result["reaction"]["nodes"] <= 377  # the top grip's nodes that carry one
    assert set(result["zones"]) == {"gauge", "free length", "band", "tab line", "gripped"} and result["zones"]["gauge"]["S11"]["worst"] == 0.0
    with (tmp_path / "pairs.csv").open(encoding="utf-8", newline="") as handle:
        assert sum(1 for _ in handle) == 1 + 1488 * 8


def test_a_coupon_drawn_about_its_centre_is_moved_onto_ours_and_still_compared_item_by_item(tool, runs, tmp_path):
    result = compared(tool, runs, bundle_of(tmp_path / "centred", runs["ours"], move=(-12.5, -125.0)))
    assert result["verdict"] == "agrees" and result["pairing"]["moved_by"] == [12.5, 125.0]
    assert "after moving your coupon by (12.5, 125)" in result["pairing"]["how"]
    assert result["model"]["compared"] == "item by item" and result["model"]["same"] is True
    assert result["model"]["largest_node_offset"] < 1e-9 and criteria(result)["Reaction within 1 %"] is True


def test_a_bundle_in_the_other_deck_system_is_converted_and_agrees(tool, runs, tmp_path):
    spec = load_spec(SPEC)
    in_metres = write_abaqus(build_model(spec), units="m-Pa")
    result = compared(tool, runs, bundle_of(tmp_path / "si", runs["ours"], deck_text=in_metres, units="m-Pa"))
    assert result["converted_from"] == "m-Pa" and result["units"] == "mm-MPa" and result["verdict"] == "agrees"
    assert result["model"]["compared"] == "item by item" and result["model"]["same"] is True
    assert result["zones"]["gauge"]["S11"]["worst"] < 1e-9 and abs(result["reaction"]["difference"]) < 1e-9
    assert result["zones"]["gauge"]["S11"]["yours"] == pytest.approx(result["zones"]["gauge"]["S11"]["ours"], rel=1e-9)


def test_a_model_on_another_mesh_is_compared_without_its_mesh_in_the_gauge_and_at_the_reaction_and_says_so(tool, runs, tmp_path):
    result = compared(tool, runs, bundle_of(tmp_path / "coarse", runs["coarse"]), pairs_out=tmp_path / "pairs.csv")
    assert result["verdict"] == "agrees"
    model, pairing = result["model"], result["pairing"]
    assert model["compared"] == "without the mesh" and model["same"] is True and model["reason"] == "the two meshes differ"
    listed = {i["item"]: i for i in model["items"]}
    assert listed["Outline"]["yours"] == listed["Outline"]["ours"] == "25 by 250 mm" and listed["Outline"]["same"] is True
    assert listed["Elements"] == {"item": "Elements", "yours": "372 S4", "ours": "1488 S4", "same": None}
    assert listed["Grips and boundary conditions"]["same"] is None and listed["Layup, bottom first"]["same"] is True
    assert pairing["same_mesh"] is False and "your model has 372 elements and ours 1488" in pairing["why_not_element_by_element"]
    assert pairing["how"].startswith("by position on two meshes") and pairing["elements"] == 36 + 96  # their gauge and free-length elements
    assert set(result["zones"]) == {"gauge", "free length"} and result["zones"]["gauge"]["elements"] == 36
    by_criterion = {c["criterion"]: c for c in result["criteria"]}
    assert by_criterion["Gauge: every value within 1 %"]["met"] is True and by_criterion["Reaction within 1 %"]["met"] is True
    free = by_criterion["Free length: every value within 3 %"]
    assert free["met"] is None and free["judged"] is False and free["evidence"].startswith("reported, not judged on another mesh: 9216 values")
    assert max(result["zones"]["gauge"][q]["worst"] for q in QUANTITIES) < 0.002  # two meshes of one coupon: the gauge within 0.2 %
    assert abs(result["reaction"]["difference"]) < 0.001
    worst = result["zones"]["gauge"]["S11"]
    assert worst["our_element"] != worst["your_element"] or worst["our_element"] <= 1488  # ours is named by our own number
    with (tmp_path / "pairs.csv").open(encoding="utf-8", newline="") as handle:
        assert sum(1 for _ in handle) == 1 + 132 * 8


def test_a_gauge_value_two_percent_off_differs_and_says_where(tool, runs, tmp_path):
    gauge = json.loads((runs["ours"]["folder"] / "ours-every-output.json").read_text(encoding="utf-8"))["lines"]
    target = next(r for r in runs["ours"]["rows"] if gauge["gauge_from"] < float(r["Y"]) < gauge["gauge_to"] and r["Layer"] == "2")

    def change(row):
        if (row["Element"], row["Layer"]) == (target["Element"], "2"):
            row["S11"] = repr(float(row["S11"]) * 1.02)

    result = compared(tool, runs, bundle_of(tmp_path / "off", runs["ours"], change=change))
    assert result["verdict"] == "differs" and result["model"]["same"] is True
    assert criteria(result) == {"Reaction within 1 %": True, "Gauge: every value within 1 %": False, "Free length: every value within 3 %": True}
    s11 = result["zones"]["gauge"]["S11"]
    assert s11["within_1"] == s11["values"] - 1 and (s11["your_element"], s11["layer"]) == (int(target["Element"]), 2)
    assert s11["worst"] == pytest.approx(0.02 / 1.02, rel=1e-6)


def test_another_layup_in_the_deck_differs_on_the_model_even_when_the_numbers_agree(tool, runs, tmp_path):
    text = runs["ours"]["deck"].read_text(encoding="utf-8")
    ply = re.search(r"^(.*, *)45\.?0*(, *\S+)$", text.split("*Shell Section", 1)[1], re.M)
    assert ply, "the deck's first ply line"
    changed = text.replace(ply.group(0), f"{ply.group(1)}30.{ply.group(2)}", 1)
    result = compared(tool, runs, bundle_of(tmp_path / "layup", runs["ours"], deck_text=changed))
    assert result["verdict"] == "differs" and result["model"]["same"] is False
    assert [i["item"] for i in result["model"]["items"] if i["same"] is False] == ["Layup, bottom first"]
    assert all(criteria(result).values())


def test_a_coupon_of_another_size_differs_and_its_results_are_not_placed_on_ours(tool, runs, tmp_path):
    result = compared(tool, runs, bundle_of(tmp_path / "smaller", runs["coarse"], scale=0.9))
    assert result["verdict"] == "differs"
    outline = next(i for i in result["model"]["items"] if i["item"] == "Outline")
    assert outline == {"item": "Outline", "yours": "22.5 by 225 mm", "ours": "25 by 250 mm", "same": False}
    assert result["zones"] == {} and result["reaction"] is None
    assert {c["evidence"] for c in result["criteria"]} == {"not compared: the two coupons are not the same size"}


def test_without_reactions_the_pull_force_is_not_judged_and_the_verdict_is_incomplete(tool, runs, tmp_path):
    result = compared(tool, runs, bundle_of(tmp_path / "no-rf", runs["ours"], rf=False))
    assert result["verdict"] == "incomplete" and result["reaction"] is None
    assert criteria(result) == {"Reaction within 1 %": None, "Gauge: every value within 1 %": True, "Free length: every value within 3 %": True}


def test_what_is_out_of_scope_is_refused_with_the_reason(tool, runs, tmp_path):
    text = runs["ours"]["deck"].read_text(encoding="utf-8")
    assert "*Step, name=Step-1, nlgeom=NO" in text
    nonlinear = bundle_of(tmp_path / "nlgeom", runs["ours"], deck_text=text.replace("nlgeom=NO", "nlgeom=YES", 1))
    with pytest.raises(tool.OutOfScope, match="our reader does not take the bundle's deck: .*nlgeom"):
        compared(tool, runs, nonlinear)
    checked = tool.check(nonlinear)
    assert checked["in_scope"] is False and checked["deck"]["read"] is False and checked["every_output"]["read"] is True
    with pytest.raises(tool.OutOfScope, match=r"your model has plies \[1, 2, 3, 4, 5, 6, 7\] and ours \[1, 2, 3, 4, 5, 6, 7, 8\]: not the same layup"):
        compared(tool, runs, bundle_of(tmp_path / "seven", runs["ours"], drop_layer=8))


def test_check_says_what_a_bundle_holds(tool, runs, tmp_path):
    checked = tool.check(bundle_of(tmp_path / "same", runs["ours"]))
    assert checked["in_scope"] is True
    assert checked["deck"] == {"read": True, "parts": 1, "steps": ["Step-1"], "notes": checked["deck"]["notes"], "nodes": 1625, "elements": 1488,
                               "element_type": "S4", "plies": 8, "layup": "45/0/-45/90/90/-45/0/45"}
    assert checked["every_output"] == {"read": True, "rows": 11904, "elements": 1488, "layers": 8} and checked["reactions"]["read"] is True
    assert checked["bundle"]["units"] == "mm-MPa" and set(checked["bundle"]["files"]) == {"deck", "every_output", "reactions"}


def test_the_command_packs_checks_and_compares_and_its_exit_code_is_the_verdict(runs, tmp_path):
    ours = runs["ours"]
    source = bundle_of(tmp_path / "files", ours)
    command = lambda *args: subprocess.run([sys.executable, str(TOOLS / "abaqus_upload.py"), *args], capture_output=True, text=True, encoding="utf-8")  # noqa: E731
    packed = tmp_path / "packed.zip"
    done = command("pack", "--deck", str(source.with_name("Job-1.inp")), "--every-output", str(source.with_name("Job-1-every-output.csv")),
                   "--rf", str(source.with_name("Job-1-every-output-RF.csv")), "--units", "mm-MPa", "--out", str(packed))
    assert done.returncode == 0 and "bundle version 1, 3 files" in done.stdout, done.stderr
    done = command("check", str(packed))
    assert done.returncode == 0 and "in scope: the comparison takes this bundle" in done.stdout, done.stderr
    arguments = ("--ours", str(ours["folder"] / "ours-every-output.csv"), "--our-deck", str(ours["deck"]))
    done = command("compare", str(packed), *arguments, "--json", str(tmp_path / "result.json"))
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("Agrees with ours: Job-1 beside d3039") and "The model (item by item): the same as ours on every one of" in done.stdout
    assert json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))["verdict"] == "agrees"
    (tmp_path / "broken.zip").write_bytes(packed.read_bytes()[:-200])
    done = command("compare", str(tmp_path / "broken.zip"), *arguments, "--json", str(tmp_path / "refused.json"))
    assert done.returncode == 2 and done.stderr.startswith("refused:")
    refused = json.loads((tmp_path / "refused.json").read_text(encoding="utf-8"))
    assert refused["verdict"] == "refused" and refused["problems"]
