"""Run one of our specs in Abaqus/Standard without the GUI, export its fields, and write the comparison record against the kernel (ADR-0045).

    uv run python tools/run_abaqus.py ../.local/fea/<coupon>/ours/<coupon>.toml --out ../.local/fea/<coupon>/ours/runs/attempt-NN_<date>/run/abaqus \
        --run-by "Erik Villa" --machine "founder Windows 11, Abaqus 2025, UCSD teaching licence" --tolerance 0.01 --floor 0.02 \
        --within 0 10 25 55 [--element-probes centre] [--elements 395 396] [--notes "..."] [--record <path>]

Needs Abaqus (ANISOTROPY_ABAQUS or abaqus on PATH; docs/installation-fea-tools.md) and a licence seat. Writes into --out the deck
`<spec>-abaqus.inp` (S4R, the same deck our kernel reads), Abaqus's .odb .dat .sta .msg, the CSV field reports and the reactions
the extraction script makes, and the record `<spec>-abaqus-record.toml` (--record puts it elsewhere); then prints how many of the
record's numbers the kernel reproduces. The elements recorded are those named (--elements), the spec's element probes
(--element-probes), or every element whose centroid lies in a box (--within XMIN XMAX YMIN YMAX, deck units): one of the three.
The reaction at every RF-* and Grip-* node set that carries one is recorded as [RF1, RF2]. The licence is a teaching licence:
the course and the team comparison only, never a customer deliverable.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from anisotropy_fea.abaqus import QUANTITIES, AbaqusError, extract_fields, reactions_by_set, read_provenance, read_reactions, run_abaqus
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.abaqus_report import read_field_report, report_quantities
from anisotropy_fea.compare import compare_record, format_record, load_record, record_disagreements, sha256_of, validate_record
from anisotropy_fea.femodel import build_model
from anisotropy_fea.mesher import MeshError
from anisotropy_fea.spec import SpecError, load_spec
from anisotropy_fea.write_abaqus import write_abaqus

KNOWN_DIFFERENCES = {
    "kernel": "bilinear four-node membrane element, full 2 by 2 integration, membrane only (B = 0), no transverse shear, strain at the element centroid",
    "reference": "Abaqus S4R: one reduced-integration point with hourglass control, drilling stiffness, transverse shear; values at the centroid, "
                 "section points at the layer faces (SNEG bottom, SPOS top); S11, S22 in the ply's material axes",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="the run folder, normally <attempt>/run/abaqus from tools/new_attempt.py")
    parser.add_argument("--record", type=Path, default=None, help="where the record goes; default <out>/<spec>-abaqus-record.toml")
    parser.add_argument("--elements", type=int, nargs="+", default=None, help="element labels whose values are recorded")
    parser.add_argument("--element-probes", nargs="+", default=None, help="the spec's element probes to record, by name")
    parser.add_argument("--within", type=float, nargs=4, metavar=("XMIN", "XMAX", "YMIN", "YMAX"), default=None,
                        help="every element whose centroid lies inside this box (deck units)")
    parser.add_argument("--layer-point", choices=("bottom", "middle", "top"), default=None, help="passed to the extraction when a layer has several section points")
    parser.add_argument("--cpus", type=int, default=1)
    parser.add_argument("--run-by", required=True)
    parser.add_argument("--machine", required=True)
    parser.add_argument("--run-date", default=dt.date.today().isoformat())
    parser.add_argument("--tolerance", type=float, required=True)
    parser.add_argument("--floor", type=float, default=0.0)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    if sum(x is not None for x in (args.elements, args.element_probes, args.within)) != 1:
        raise SystemExit("give exactly one of --elements, --element-probes or --within")

    try:
        spec = load_spec(args.spec)
        model = build_model(spec)
    except (SpecError, MeshError) as exc:
        raise SystemExit(f"spec refused: {exc}") from None
    units = spec.units
    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.spec.stem
    deck_path = args.out / f"{stem}-abaqus.inp"
    # the same text as the spec's deck in decks/ (ADR-0045 amendment 2): the kernel reads this file too, so the record's two digests are its own
    deck_path.write_text(write_abaqus(model), encoding="utf-8", newline="\n")
    print("written", deck_path, f"({model.mesh.node_count} nodes, {model.mesh.element_count} S4R elements)")
    try:
        result = run_abaqus(deck_path, workdir=args.out, cpus=args.cpus)
        print(f"Abaqus {result.version}: {result.elapsed_s:.1f} s, {len(result.warnings)} warnings; results in {args.out} (.odb, .dat, .sta, .msg)")
        for warning in result.warnings[:5]:
            print("  warning:", warning[:200])
        files = extract_fields(result.odb_path, args.out, layer_point=args.layer_point)
    except AbaqusError as exc:
        raise SystemExit(str(exc)) from None
    provenance = read_provenance(files["json"])
    for key in (*QUANTITIES, "RF"):
        if key in files:
            print(f"exported {files[key].name}: {provenance['files'][key]['rows']} rows, sha256 {provenance['files'][key]['sha256'][:16]}...")

    deck = read_deck(deck_path, units)
    reports = [read_field_report(files[quantity]) for quantity in QUANTITIES]
    if args.elements is not None:
        elements = args.elements
    elif args.element_probes is not None:
        unknown = [name for name in args.element_probes if name not in model.probe_elements]
        if unknown:
            raise SystemExit(f"no element probe named {unknown}; the spec has {list(model.probe_elements)}")
        elements = sorted(model.probe_elements[name] + 1 for name in args.element_probes)
    else:
        xmin, xmax, ymin, ymax = args.within
        elements = sorted(e for e, (x, y) in reports[0].centroids.items() if xmin <= x <= xmax and ymin <= y <= ymax)
        if not elements:
            raise SystemExit("no reported element has its centroid inside --within")
        print(f"{len(elements)} elements inside the box")
    expected = report_quantities(reports, deck, elements)
    if "RF" in files:
        rf = reactions_by_set(deck, read_reactions(files["RF"]))
        if rf:
            expected["rf"] = rf
    expected = {"tolerance": args.tolerance, "floor": args.floor, **expected}

    record_path = args.record or (args.out / f"{stem}-abaqus-record.toml")
    record_dir = record_path.parent
    record_dir.mkdir(parents=True, exist_ok=True)
    relative = lambda path: Path(path).resolve().relative_to(record_dir.resolve(), walk_up=True).as_posix()  # noqa: E731
    record = {
        "title": f"{spec.title}: Abaqus {result.version} S4R against the kernel",
        "units": units,
        "spec": relative(args.spec),
        "deck_kernel": relative(deck_path),
        "deck_reference": relative(deck_path),
        "deck_kernel_sha256": sha256_of(deck_path),
        "deck_reference_sha256": sha256_of(deck_path),
        "solver": {"name": "abaqus", "version": f"{result.version} ({provenance['solver']})", "element_type": provenance["element_type"], "run_by": args.run_by,
                   "run_date": args.run_date, "machine": args.machine, "source": "csv",
                   "reports": ", ".join(f"{Path(r.path).name} ({r.quantity}: {r.rows} rows in {r.blocks} blocks)" for r in reports),
                   "odb": provenance["odb"], "created": provenance["created"], "step": f"{provenance['step']}, {provenance['frame']}",
                   "section_points": "; ".join(f"layer {k}: {v}" for k, v in provenance["section_points"].items()),
                   "extraction": f"tools/abaqus_extract_fields.py under abaqus python; {files['json'].name}", "notes": args.notes},
        "known_differences": KNOWN_DIFFERENCES,
        "expected": expected,
    }
    record["_dir"] = str(record_dir)
    validate_record(record)
    del record["_dir"]
    record_path.write_text(format_record(record), encoding="utf-8", newline="\n")
    counts = {k: (sum(len(plies) for plies in v.values()) if k != "rf" else len(v)) for k, v in expected.items() if k not in ("tolerance", "floor")}
    print("written", record_path, "| rows per group:", counts)

    loaded = load_record(record_path)
    comparisons, problems = compare_record(loaded)
    disagreements = record_disagreements(loaded)
    print(f"kernel against the record: {len(comparisons)} numbers compared, {len(disagreements)} outside {args.tolerance:g} (floor {args.floor:g})"
          + (f", {len(problems)} problems" if problems else ""))
    for line in disagreements[:10]:
        print("  ", line)
    if len(disagreements) > 10:
        print(f"   ... {len(disagreements) - 10} more")


if __name__ == "__main__":
    main()
