"""Abaqus's numbers beside ours, read from the `.dat` of a run of our own deck (ADR-0066 amendment 1): the validation table's rows, on the
command line, for the founder's own check of a coupon against Abaqus. The site's table shows laminate theory, Anisotropy and CalculiX
only (the founder, 2026-11-08: "open source calculix is enough"); this tool is the Abaqus column, printed when he runs the deck.

    abaqus job=<coupon>-abaqus input=<coupon>-abaqus.inp interactive          # on the machine with Abaqus, in a working folder
    uv run python tools/abaqus_beside.py <coupon>-abaqus.inp <coupon>-abaqus.dat [--units mm-MPa] [--json <file>]

The deck is the one downloaded from the job's Files ("Our Abaqus deck"), which prints every layer's middle section point at the probe
elements and the reaction at the moving grip; the `.dat` is the run's. Every number printed is either Abaqus's own printed value or our
kernel's on the same deck at the same gauge element (`anisotropy_fea.abaqus_summary`); the agreement rule is the CalculiX record's.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from anisotropy_fea.abaqus_dat import AbaqusDatError
from anisotropy_fea.abaqus_summary import abaqus_beside
from anisotropy_fea.mesh import KernelError
from anisotropy_fea.units import UNIT_LABEL


def lines_of(summary: dict) -> list[str]:
    """The validation table's rows as text: quantity, Abaqus, ours, and a mark for a cell outside the tolerance."""
    labels = UNIT_LABEL[summary["units"]]
    mark = lambda ok: "" if ok else "  ✕"
    out = [f"{summary['solver']} on {summary['deck']} ({summary['dat']}); {summary['agree']} values agree within {100 * summary['tolerance']:g} % "
           f"(floor {100 * summary['floor']:g} % of the group's largest); gauge element {summary['gauge_element']}",
           f"{'quantity':38} {'Abaqus':>14} {'Anisotropy':>14}"]
    r = summary["reaction"]
    out.append(f"{'reaction ' + summary['reaction_set'] + ', ' + labels['force']:38} {r['abaqus']:14.6g} {r['ours']:14.6g}  ({r['difference']}){mark(r['agrees'])}")
    strain = summary.get("gauge_strain")
    if strain:
        for i, name in enumerate(("eps_x", "eps_y", "gamma_xy")):
            out.append(f"{'gauge strain ' + name:38} {strain['abaqus'][i]:14.6g} {strain['ours'][i]:14.6g}{mark(strain['agrees'][i])}")
    for g in summary["gauge"]:
        for i, name in enumerate(("sigma_1", "sigma_2", "tau_12")):
            out.append(f"{f'ply {g['ply']} ({g['angle']:g} deg) {name}, {labels['stress']}':38} {g['abaqus'][i]:14.6g} {g['ours'][i]:14.6g}{mark(g['agrees'][i])}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("deck", type=Path, help="our Abaqus deck, as downloaded from the job's Files")
    parser.add_argument("dat", type=Path, help="the .dat Abaqus wrote for it")
    parser.add_argument("--units", default="mm-MPa", help="the coupon's stated unit system, the fields' (default mm-MPa)")
    parser.add_argument("--json", type=Path, help="also write the summary (the shape of summary.calculix) to this file")
    args = parser.parse_args(argv)
    try:
        summary = abaqus_beside(args.deck, args.dat.read_text(encoding="utf-8", errors="replace"), args.units, args.dat.name)
    except (AbaqusDatError, KernelError, OSError) as exc:
        print(f"abaqus_beside: {exc}", file=sys.stderr)
        return 2
    print("\n".join(lines_of(summary)))
    if args.json:
        args.json.write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(f"written    {args.json}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
