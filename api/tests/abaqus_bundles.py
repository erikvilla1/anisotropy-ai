"""Bundles and a run of ours for the upload tests, made once per test session by the fea package's own code:

    uv run --project fea python api/tests/abaqus_bundles.py <folder>

It solves the public D3039 check with our kernel and writes, under <folder>:

    package/2026-11-13_D3039-CHECK/         a run's package as far as the comparison reads it: the deck for Abaqus under
                                            2-our-model/abaqus/ and 4-results/ours-every-output.csv with its JSON
    agrees.zip                              that run sent back as a bundle, in the shape Abaqus's exporter gives: it agrees with ours
    differs.zip                             the same with every reaction 5 % larger: the pull force differs
    unnamed.zip                             the first again, naming no coupon of ours
    out-of-scope.zip                        a bundle of version 1 whose deck our reader does not take

No Abaqus runs here: their side is our own run, as in fea/tests/test_abaqus_upload.py. This file is run by the fea environment and
imported by nothing.
"""

import csv
import sys
from pathlib import Path

from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.bundle import write_bundle
from anisotropy_fea.every_output import COLUMNS, QUANTITIES, write_ours
from anisotropy_fea.femodel import build_model
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.spec import load_spec
from anisotropy_fea.units import from_si
from anisotropy_fea.write_abaqus import write_abaqus

SPEC = paths.CHECKS / "d3039-im7-8552" / "d3039-im7-8552.toml"
COUPON = "D3039-CHECK"
CREATED = "2026-11-13T08:30:00Z"


def bundle(folder: Path, name: str, deck_text: str, rows: list[dict], reactions: list[dict], coupon: str | None, factor: float = 1.0) -> None:
    work = folder / f"{name}-files"
    work.mkdir()
    deck = work / "Job-1.inp"
    deck.write_text(deck_text, encoding="utf-8", newline="\n")
    every = work / "Job-1-every-output.csv"
    with every.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMNS[:-1])
        for row in rows:
            writer.writerow([row["Element"], row["Layer"], f'"fraction = 0, Layer = {row["Layer"]}"', row["X"], row["Y"]] + [row[q] for q in QUANTITIES])
    forces = work / "Job-1-every-output-RF.csv"
    with forces.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["Node", "X", "Y", "RF1", "RF2"])
        for r in reactions:
            writer.writerow([r["Node"], repr(r["X"]), repr(r["Y"]), repr(r["RF1"] * factor), repr(r["RF2"] * factor)])
    write_bundle(folder / f"{name}.zip", {"deck": deck, "every_output": every, "reactions": forces}, "mm-MPa", "test 1", abaqus="Abaqus/Standard 2025",
                 job="Job-1", coupon=coupon, created=CREATED)


def main(folder: Path) -> None:
    spec = load_spec(SPEC)
    package = folder / "package" / f"2026-11-13_{COUPON}"
    (package / "2-our-model" / "abaqus").mkdir(parents=True)
    (package / "4-results").mkdir()
    deck = package / "2-our-model" / "abaqus" / f"{COUPON}-abaqus.inp"
    deck.write_text(write_abaqus(build_model(spec)), encoding="utf-8", newline="\n")
    (package / "2-our-model" / "abaqus" / f"{COUPON}-build.py").write_text("# the build script lives beside the deck in a package\n", encoding="utf-8")
    solution = solve_deck(read_deck(deck, "mm-MPa"))
    write_ours(package / "4-results" / "ours-every-output.csv", package / "4-results" / "ours-every-output.json", spec, solution, "mm-MPa", COUPON,
               "S4", "test")
    with (package / "4-results" / "ours-every-output.csv").open(encoding="utf-8", newline="") as handle:
        rows = [{c: r[c] for c in COLUMNS[:-1]} for r in csv.DictReader(handle)]
    reactions = []
    for i, key in enumerate(solution.mesh.node_keys):
        x, y = (float(from_si(v, "length", "mm-MPa")) for v in solution.mesh.xy[i])
        rf = [float(from_si(v, "force", "mm-MPa")) for v in solution.reaction[i, :2]]
        if any(rf):
            reactions.append({"Node": key[1], "X": x, "Y": y, "RF1": rf[0], "RF2": rf[1]})
    text = deck.read_text(encoding="utf-8")
    bundle(folder, "agrees", text, rows, reactions, COUPON)
    bundle(folder, "differs", text, rows, reactions, COUPON, factor=1.05)
    bundle(folder, "unnamed", text, rows, reactions, None)
    bundle(folder, "out-of-scope", "*Heading\nnot a deck our reader takes\n", rows, reactions, COUPON)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
