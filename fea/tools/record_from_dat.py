"""Turn a CalculiX run of one of our specs into a committed comparison record: numbers plus provenance (ADR-0030, ADR-0007).

    uv run python tools/record_from_dat.py validation/specs/tension-coupon-x840-nodal.toml ../.local/fea/calculix-prepomax/tension-coupon/ours/tension-coupon-x840-nodal-ccx.dat \
        --deck-reference validation/decks/generated/tension-coupon-x840-nodal-ccx.inp \
        --deck-kernel validation/decks/generated/tension-coupon-x840-nodal-abaqus.inp \
        --version 2.22 --run-by "Erik Villa" --machine "founder Windows 11, PrePoMax v2.6.0 bundle" \
        --tolerance 0.03 --floor 0.02 --element-probes centre --out validation/records/tension-coupon-x840-nodal-calculix.toml

The reference deck is the one CalculiX ran (order 2, S8R); the kernel deck is the order-1 twin on the same corner nodes.
The record stores both digests, so a changed deck is noticed. The .dat itself stays out of the repository.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from anisotropy_fea.calculix import parse_dat
from anisotropy_fea.compare import format_record, load_conventions, reference_quantities, sha256_of
from anisotropy_fea.femodel import build_model
from anisotropy_fea.spec import load_spec

KNOWN_DIFFERENCES = {
    "kernel": "bilinear four-node membrane element, full 2 by 2 integration, membrane only (B = 0), no transverse shear, strain at the element centroid",
    "reference": "S8R expanded to a C3D20R brick, reduced integration, three-dimensional constitutive law with E3, nu13, nu23, transverse shear, "
                 "drilling rotation removed, values averaged over the element's integration points",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", type=Path)
    parser.add_argument("dat", type=Path)
    parser.add_argument("--deck-reference", type=Path, required=True)
    parser.add_argument("--deck-kernel", type=Path, required=True)
    parser.add_argument("--conventions", type=Path, default=Path("validation/records/_calculix-conventions.toml"))
    parser.add_argument("--version", required=True, help="CalculiX version as `ccx -v` prints it")
    parser.add_argument("--run-by", required=True)
    parser.add_argument("--machine", required=True)
    parser.add_argument("--run-date", default=dt.date.today().isoformat())
    parser.add_argument("--tolerance", type=float, required=True)
    parser.add_argument("--floor", type=float, default=0.0)
    parser.add_argument("--element-probes", nargs="*", default=None,
                        help="element probes whose strain and per-ply values are recorded; default all. Leave out probes in gradient regions "
                             "where the element types are known to differ and say so in the comparison note")
    parser.add_argument("--node-probes", nargs="*", default=None,
                        help="node probes whose displacements are recorded; default all. Same rule as --element-probes")
    parser.add_argument("--notes", default="")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    spec = load_spec(args.spec)
    spec2 = spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"element_order": 2})})
    model = build_model(spec2)
    conventions = load_conventions(args.conventions)
    if conventions["calculix_version"].split(".")[0] != args.version.split(".")[0]:
        raise SystemExit(f"conventions were detected on CalculiX {conventions['calculix_version']}; this run is {args.version}: re-run the detection first")
    dat = parse_dat(args.dat.read_text(encoding="utf-8", errors="replace"))
    expected = reference_quantities(model, dat, conventions, element_probes=args.element_probes, node_probes=args.node_probes)
    expected = {"tolerance": args.tolerance, "floor": args.floor, **expected}
    out_dir = args.out.parent
    record = {
        "title": f"{spec.title}: CalculiX {args.version} S8R against the kernel",
        "units": spec.units,
        "spec": Path(args.spec).resolve().relative_to(out_dir.resolve(), walk_up=True).as_posix(),
        "deck_kernel": args.deck_kernel.resolve().relative_to(out_dir.resolve(), walk_up=True).as_posix(),
        "deck_reference": args.deck_reference.resolve().relative_to(out_dir.resolve(), walk_up=True).as_posix(),
        "deck_kernel_sha256": sha256_of(args.deck_kernel),
        "deck_reference_sha256": sha256_of(args.deck_reference),
        "solver": {"name": "calculix", "version": args.version, "element_type": "S8R", "run_by": args.run_by, "run_date": args.run_date,
                   "machine": args.machine, "source": "dat", "conventions": args.conventions.name, "notes": args.notes},
        "known_differences": KNOWN_DIFFERENCES,
        "expected": expected,
    }
    args.out.write_text(format_record(record), encoding="utf-8", newline="\n")
    counts = {k: (len(v) if isinstance(v, dict) else 1) for k, v in expected.items() if k not in ("tolerance", "floor")}
    print("written", args.out, counts)


if __name__ == "__main__":
    main()
