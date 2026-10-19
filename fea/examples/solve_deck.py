"""Solve an Abaqus deck with the membrane kernel and print reactions, reference-node displacements and strain ranges.

    uv run python examples/solve_deck.py validation/decks/coupon-2x8-grips-im7-8552.inp --units mm-MPa
    uv run python examples/solve_deck.py ../.local/fea/abaqus/tension-coupon/team/Tension-test.inp --units mm-MPa

Results print in the deck's units. Material values are never printed here; use deck_summary.py for those.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.mesh import KernelError
from anisotropy_fea.model import node_name, reference_node
from anisotropy_fea.recovery import deck_f12_star, element_ply_states, strength_ratios
from anisotropy_fea.units import from_si


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("deck", type=Path)
    parser.add_argument("--units", required=True, help="the unit system the deck is written in: mm-MPa or m-Pa")
    args = parser.parse_args()
    units = args.units
    deck = read_deck(args.deck, units)
    solution = solve_membrane(deck)
    mesh = solution.mesh
    print(f"{args.deck}  {mesh.node_count} nodes, {mesh.element_count} elements, units {units}")
    for coupling in deck.couplings:
        key = reference_node(deck, coupling)
        rf = solution.reaction_of([key])
        u = solution.displacement_of(key)
        print(f"reference {node_name(key)} ({coupling.name}): RF = [{from_si(rf[0], 'force', units):.6g}, {from_si(rf[1], 'force', units):.6g}] N, "
              f"U = [{from_si(u[0], 'length', units):.6g}, {from_si(u[1], 'length', units):.6g}]")
    for name, keys in deck.nsets.items():
        rf = solution.reaction_of(keys)
        if np.any(rf != 0) and not any(key[0] is None for key in keys):
            print(f"set {name!r}: RF = [{from_si(rf[0], 'force', units):.6g}, {from_si(rf[1], 'force', units):.6g}] N")
    total = solution.total_reaction
    print(f"sum of reactions = [{total[0]:.3g}, {total[1]:.3g}] N (equilibrium check); largest free-dof residual {solution.free_residual:.3g} N")
    for i, label in enumerate(("eps_x", "eps_y", "gamma_xy")):
        print(f"{label}: min {solution.strain[:, i].min():.6g}  max {solution.strain[:, i].max():.6g}  "
              f"mean {solution.strain[:, i].mean():.6g}")
    for i, label in enumerate(("Nx", "Ny", "Nxy")):
        values = np.array([from_si(v, "force_per_length", units) for v in solution.section_force[:, i]])
        print(f"{label}: min {values.min():.6g}  max {values.max():.6g} (force per length)")
    f12_star = deck_f12_star(deck)
    field = element_ply_states(solution)
    for criterion in ("max_stress", "tsai_hill", "tsai_wu", "max_strain"):
        try:
            failure = strength_ratios(solution, criterion, f12_star, field)
        except KernelError as exc:
            print(f"first-ply failure, {criterion}: not available ({exc})")
            continue
        print(f"first-ply failure, {criterion}: factor {failure.factor:.6g} on the applied loading, element "
              f"{failure.element[0]}.{failure.element[1]}, ply {failure.ply} (bottom = 1), mode {failure.governing_mode}")


if __name__ == "__main__":
    main()
