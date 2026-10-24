"""Write the CalculiX deck for a spec, run the solver, and print what it reported next to our kernel's answer.

    uv run python examples/run_calculix.py ../.local/fea/<coupon>/ours/<coupon>-nodal.toml --out ../.local/fea/<coupon>/ours/runs/attempt-NN_<date>/run/calculix

Needs CalculiX (ANISOTROPY_CCX or ccx on PATH; docs/installation-fea-tools.md). The CalculiX deck is eight-node (S8R,
the only composite shell CalculiX has); the kernel solves the order-1 twin on the same corner nodes. Leaves <spec>-ccx.inp,
.dat, .frd (open it in PrePoMax: File, Open results) and <spec>-kernel.inp in the output folder.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.calculix import CalculixError, parse_dat, run_calculix
from anisotropy_fea.femodel import build_model
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.spec import load_spec
from anisotropy_fea.units import from_si
from anisotropy_fea.write_abaqus import write_abaqus
from anisotropy_fea.write_calculix import write_calculix


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    spec = load_spec(args.spec)
    units = spec.units
    spec2 = spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"element_order": 2})})
    model = build_model(spec2)
    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.spec.stem
    ccx_deck = args.out / f"{stem}-ccx.inp"
    ccx_deck.write_text(write_calculix(model), encoding="utf-8", newline="\n")
    print("written", ccx_deck, f"({model.mesh.node_count} nodes, {model.mesh.element_count} S8R elements)")
    try:
        result = run_calculix(ccx_deck)
    except CalculixError as exc:
        raise SystemExit(str(exc)) from None
    print(f"CalculiX {result.version}: {result.elapsed_s:.1f} s, {len(result.warnings)} warnings; results in {result.workdir} (.dat, .frd)")
    for warning in result.warnings[:5]:
        print("  warning:", warning[:200])
    dat = parse_dat(result.dat_text)
    twin = build_model(spec, model.mesh.corner_mesh())
    kernel_deck = args.out / f"{stem}-kernel.inp"
    kernel_deck.write_text(write_abaqus(twin), encoding="utf-8", newline="\n")
    deck = read_deck(kernel_deck, units)
    solution = solve_membrane(deck)
    for grip in ("Grip-Top", "Grip-Bottom"):
        try:
            total = dat.total_force(grip)
        except KeyError:
            continue
        ours = solution.reaction_of(deck.nsets[grip])
        print(f"{grip}: CalculiX total force [{total[0]:.6g}, {total[1]:.6g}] N; kernel [{from_si(ours[0], 'force', units):.6g}, {from_si(ours[1], 'force', units):.6g}] N")
    for name, index in twin.probe_nodes.items():
        theirs = dat.displacements(f"Probe-{name}").row(index + 1)
        ours = solution.displacement_of((twin.instance, index + 1))
        print(f"probe node {name} (node {index + 1}): CalculiX U [{theirs[0]:.6g}, {theirs[1]:.6g}]; kernel [{from_si(ours[0], 'length', units):.6g}, {from_si(ours[1], 'length', units):.6g}]")
    for name, index in twin.probe_elements.items():
        strains = dat.strains(f"Probe-{name}").values[:, [0, 1, 3]].mean(axis=0)
        ours = solution.strain[index]
        print(f"probe element {name} (element {index + 1}): CalculiX mean strain [{strains[0]:.4g}, {strains[1]:.4g}, gamma {2 * strains[2]:.4g}]; "
              f"kernel centroid [{ours[0]:.4g}, {ours[1]:.4g}, {ours[2]:.4g}]")
    print("equilibrium (kernel): sum of reactions", np.round(solution.total_reaction, 6), "N")


if __name__ == "__main__":
    main()
