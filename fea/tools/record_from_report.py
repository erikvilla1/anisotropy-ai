"""Turn Abaqus/CAE field reports (CSV) of a deck into a comparison record: numbers plus provenance (ADR-0030, amendment 2).

    uv run python tools/record_from_report.py ../.local/abaqus/Tension-test.inp --units mm-MPa \
        --reports ../.local/abaqus/team-files/results/Test_01_S11.csv ../.local/abaqus/team-files/results/Test_01_S22.csv \
                  ../.local/abaqus/team-files/results/Test_01_Mises.csv \
        --elements 545 546 --version 2026 --run-by "the team" --machine "UCSD lab, Abaqus/CAE 2026" \
        --tolerance 0.01 --floor 0.02 --title "..." --out ../.local/abaqus/comparisons/tension-test-abaqus.toml

Both solvers ran the same deck, so `deck_kernel` and `deck_reference` are that deck. A record of a deck whose material is not
public stays under `.local/` (R-16). Choose `--elements` away from the tab-line corners, where the stress is singular and the
element formulations differ; say so in `--notes`.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.abaqus_report import read_field_report, report_quantities
from anisotropy_fea.compare import format_record, sha256_of, validate_record

KNOWN_DIFFERENCES = {
    "kernel": "bilinear four-node membrane element, full 2 by 2 integration, membrane only (B = 0), no transverse shear, strain at the element centroid",
    "reference": "Abaqus S4R: one reduced-integration point with hourglass control, drilling stiffness, transverse shear; values at the centroid, "
                 "section points at the layer faces (SNEG bottom, SPOS top); S11, S22 in the ply's material axes",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("deck", type=Path)
    parser.add_argument("--units", required=True)
    parser.add_argument("--reports", type=Path, nargs="+", required=True)
    parser.add_argument("--elements", type=int, nargs="+", default=None, help="element labels whose values are recorded")
    parser.add_argument("--within", type=float, nargs=4, metavar=("XMIN", "XMAX", "YMIN", "YMAX"), default=None,
                        help="instead of labels: every reported element whose centroid lies inside this box (report units)")
    parser.add_argument("--title", required=True)
    parser.add_argument("--version", required=True, help="Abaqus version, as the deck heading or the team states it")
    parser.add_argument("--run-by", required=True)
    parser.add_argument("--machine", required=True)
    parser.add_argument("--run-date", default=dt.date.today().isoformat())
    parser.add_argument("--tolerance", type=float, required=True)
    parser.add_argument("--floor", type=float, default=0.0)
    parser.add_argument("--notes", default="")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    deck = read_deck(args.deck, args.units)
    reports = [read_field_report(path) for path in args.reports]
    if (args.elements is None) == (args.within is None):
        raise SystemExit("give --elements or --within, not both and not neither")
    elements = args.elements
    if args.within is not None:
        xmin, xmax, ymin, ymax = args.within
        elements = sorted(e for e, (x, y) in reports[0].centroids.items() if xmin <= x <= xmax and ymin <= y <= ymax)
        if not elements:
            raise SystemExit("no reported element has its centroid inside --within")
        print(f"{len(elements)} elements inside the box")
    expected = report_quantities(reports, deck, elements)
    expected = {"tolerance": args.tolerance, "floor": args.floor, **expected}
    element_types = {part.elements.element_type for part in deck.parts.values() if part.elements is not None}
    out_dir = args.out.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    deck_path = args.deck.resolve().relative_to(out_dir.resolve(), walk_up=True).as_posix()
    record = {
        "title": args.title,
        "units": args.units,
        "spec": "none: the reference solver and the kernel ran the same hand-built deck",
        "deck_kernel": deck_path,
        "deck_reference": deck_path,
        "deck_kernel_sha256": sha256_of(args.deck),
        "deck_reference_sha256": sha256_of(args.deck),
        "solver": {"name": "abaqus", "version": args.version, "element_type": "/".join(sorted(element_types)), "run_by": args.run_by,
                   "run_date": args.run_date, "machine": args.machine, "source": "csv",
                   "reports": ", ".join(f"{Path(r.path).name} ({r.quantity}: {r.rows} rows in {r.blocks} blocks)" for r in reports),
                   "odb": reports[0].odb, "step": f"{reports[0].step}, {reports[0].frame}", "notes": args.notes},
        "known_differences": KNOWN_DIFFERENCES,
        "expected": expected,
    }
    record["_dir"] = str(out_dir)
    validate_record(record)
    del record["_dir"]
    args.out.write_text(format_record(record), encoding="utf-8", newline="\n")
    counts = {k: sum(len(plies) for plies in v.values()) for k, v in expected.items() if k not in ("tolerance", "floor")}
    print("written", args.out, "| (element, ply) rows per group:", counts)


if __name__ == "__main__":
    main()
