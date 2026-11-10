"""The mesh convergence study of a coupon (ADR-0068), on the command line and as the file a coupon run writes.

    uv run python tools/convergence_study.py <spec.toml> --out <coupon>-convergence.json [--factors 1 2 4] [--cap 40000]

Our kernel solves the spec on its own mesh and on refinements that split every element along both axes, and prints the validation
quantities of ADR-0066 on every mesh beside the clamped-edge peaks and the first-ply-failure factors: what settles as the mesh is
refined and what keeps growing. The file is written whatever happens (`studied: false` with the reason when the study does not cover
the coupon), so a run reports the rest; the exit code is 2 only when the spec cannot be read.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from anisotropy_fea.convergence import CAP, FACTORS, ConvergenceError, convergence_study
from anisotropy_fea.spec import SpecError, load_spec
from anisotropy_fea.units import UNIT_LABEL


def percent(change: float | None) -> str:
    return "" if change is None else f"{100 * change:+.2f} %"


def lines_of(study: dict) -> list[str]:
    """The study as text: one column per mesh, the change from the previous mesh beside each value, and the settled flags."""
    if not study["studied"]:
        return [f"not studied: {study['reason']}"]
    meshes, changes = study["meshes"], study["changes"]
    labels = UNIT_LABEL[study["units"]]
    out = [f"{len(meshes)} meshes: " + ", ".join(f"{m['factor']}x = {m['nx']} by {m['ny']}, {m['elements']} elements ({m['solve_s']} s)" for m in meshes)
           + "".join(f"; {o['factor']}x left out: {o['reason']}" for o in study["left_out"])]

    def row(name: str, values: list[float], change: list, digits: str = ".6g") -> str:
        cells = [f"{v:{digits}}" + (f" ({percent(c)})" if c is not None else "") for v, c in zip(values, change)]
        return f"{name:34} " + "  ".join(f"{cell:>24}" for cell in cells)

    out.append(row(f"reaction at {meshes[0]['reaction_set']}, {labels['force']}".strip(", "), [m["reaction"] for m in meshes], changes["reaction"]))
    for i, name in enumerate(("eps_x", "eps_y", "gamma_xy")):
        out.append(row(f"gauge strain {name}", [m["gauge_strain"][i] for m in meshes], [None if c is None else c[i] for c in changes["gauge_strain"]], ".4e"))
    for k, p in enumerate(meshes[0]["plies"]):
        for i, name in enumerate(("sigma_1", "sigma_2", "tau_12")):
            out.append(row(f"ply {p['ply']} ({p['angle']:g} deg) {name}, gauge", [m["plies"][k]["stress_12"][i] for m in meshes],
                           [None if c is None else c[i] for c in changes["plies"][k]["stress_12"]]))
    for k, p in enumerate(meshes[0]["peaks"]):
        out.append(row(f"ply {p['ply']} largest |sigma_1| (clamped edge)", [m["peaks"][k]["s1"] for m in meshes], changes["peaks"][k]["s1"]))
    for criterion in changes["fpf"]:
        out.append(row(f"first-ply failure {criterion}, mesh", [m["fpf"][criterion] for m in meshes], changes["fpf"][criterion]))
    for criterion in changes["fpf_gauge"]:
        out.append(row(f"first-ply failure {criterion}, gauge", [m["fpf_gauge"][criterion] for m in meshes], changes["fpf_gauge"][criterion]))
    settled = study["settled"]
    out.append("settled (last change under " + f"{100 * study['settled_below']:g} %): "
               + ", ".join(f"{name} {'yes' if flag else 'no'}" for name, flag in settled.items()))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", type=Path)
    parser.add_argument("--out", type=Path, help="write the study to this file (the shape of summary.convergence)")
    parser.add_argument("--factors", type=int, nargs="+", default=list(FACTORS), help=f"the refinement factors (default {' '.join(map(str, FACTORS))})")
    parser.add_argument("--cap", type=int, default=CAP, help=f"leave a refinement out past this many elements (default {CAP})")
    args = parser.parse_args(argv)
    try:
        spec = load_spec(args.spec)
    except (SpecError, OSError) as exc:
        print(f"convergence_study: spec refused: {exc}", file=sys.stderr)
        return 2
    try:
        study = convergence_study(spec, tuple(args.factors), args.cap)
    except ConvergenceError as exc:
        print(f"convergence_study: {exc}", file=sys.stderr)
        return 2
    print("\n".join(lines_of(study)))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(study, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(f"written    {args.out}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
