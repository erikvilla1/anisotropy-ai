"""Convert a deck our reader accepts (the team's Abaqus coupon decks) to CalculiX, run it, and compare with our kernel.

    uv run python examples/convert_to_calculix.py ../.local/fea/tension-coupon/team/2026-10-16/Tension-test.inp --units mm-MPa --nu23 0.45 --out ../.local/fea/tension-coupon/runs/team-in-calculix

The Abaqus LAMINA material has no E3, nu13, nu23; CalculiX's three-dimensional law needs them, so you state nu23 and
either transverse isotropy (E3 = E2, nu13 = nu12, the default) or --E3 and --nu13 in the deck's stress unit. The
converted deck and the results (.dat, .frd for PrePoMax) land in --out. Pass --no-run to only convert. Material
values are not printed by this script.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.calculix import CalculixError, parse_dat, run_calculix
from anisotropy_fea.convert_deck import TransverseChoice, calculix_from_deck
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.mesh import mesh_from_deck
from anisotropy_fea.model import coupled_nodes, node_name, reference_node
from anisotropy_fea.units import from_si, to_si


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("deck", type=Path)
    parser.add_argument("--units", required=True)
    parser.add_argument("--nu23", type=float, default=None, help="required unless --plane-stress")
    parser.add_argument("--plane-stress", action="store_true", help="write nu13 = nu23 = 0 so CalculiX's three-dimensional law reduces to plane stress like Abaqus LAMINA")
    parser.add_argument("--E3", type=float, default=None, help="in the deck's stress unit; with --nu13 it replaces transverse isotropy")
    parser.add_argument("--nu13", type=float, default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-run", action="store_true")
    args = parser.parse_args()
    units = args.units
    deck = read_deck(args.deck, units)
    isotropy = args.E3 is None and args.nu13 is None
    transverse = TransverseChoice(nu23=args.nu23, transverse_isotropy=isotropy, plane_stress=args.plane_stress,
                                  E3=None if isotropy else to_si(args.E3, "stress", units), nu13=None if isotropy else args.nu13)
    mesh = mesh_from_deck(deck)
    centre = np.argmin(np.linalg.norm(mesh.xy[mesh.connectivity].mean(axis=1) - mesh.xy.mean(axis=0), axis=1))
    probes = [mesh.element_keys[int(centre)]]
    text = calculix_from_deck(deck, transverse, probe_elements=probes, units=units)
    args.out.mkdir(parents=True, exist_ok=True)
    ccx_deck = args.out / f"{args.deck.stem}-ccx.inp"
    ccx_deck.write_text(text, encoding="utf-8", newline="\n")
    print("written", ccx_deck, "| probe element", probes[0])
    if args.no_run:
        return
    try:
        result = run_calculix(ccx_deck)
    except CalculixError as exc:
        raise SystemExit(str(exc)) from None
    print(f"CalculiX {result.version}: {result.elapsed_s:.1f} s, {len(result.warnings)} warnings; results next to the deck (.dat, .frd)")
    for warning in result.warnings[:5]:
        print("  warning:", warning[:200])
    dat = parse_dat(result.dat_text)
    solution = solve_membrane(deck)
    for coupling in deck.couplings:
        ref = reference_node(deck, coupling)
        total = dat.total_force(f"Coupled-{coupling.name}")
        ours = solution.reaction_of([ref])
        print(f"{coupling.name} ({node_name(ref)}, {len(coupled_nodes(deck, coupling))} coupled nodes): CalculiX total force "
              f"[{total[0]:.6g}, {total[1]:.6g}] N; kernel [{from_si(ours[0], 'force', units):.6g}, {from_si(ours[1], 'force', units):.6g}] N")
    e = int(centre)
    strains = dat.strains("Probe").values[:, [0, 1, 3]].mean(axis=0)
    print(f"centre element {mesh.element_keys[e][1]}: CalculiX mean strain [{strains[0]:.4g}, {strains[1]:.4g}, gamma {2 * strains[2]:.4g}]; "
          f"kernel centroid [{solution.strain[e][0]:.4g}, {solution.strain[e][1]:.4g}, {solution.strain[e][2]:.4g}]")
    u = dat.displacements("Nall")
    top = max(u.values[:, 1])
    print(f"largest axial displacement in CalculiX {top:.6g}; in the kernel {from_si(float(solution.displacement[:, 1].max()), 'length', units):.6g}")


if __name__ == "__main__":
    main()
