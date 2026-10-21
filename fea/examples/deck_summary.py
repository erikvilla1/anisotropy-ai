"""Print what anisotropy_fea read from an Abaqus deck: counts, layup, materials, constraints, and what it skipped.

    uv run python examples/deck_summary.py checks/decks/coupon-2x8-grips-im7-8552.inp --units mm-MPa
    uv run python examples/deck_summary.py ../.local/fea/abaqus/tension-coupon/team/Tension-test.inp --units mm-MPa --no-materials

Pass --no-materials for a deck whose material values may be proprietary, so nothing numeric about the material is printed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from anisotropy_fea.abaqus_reader import parse_deck, read_deck
from anisotropy_fea.model import coupled_nodes, expanded_layers, node_name, reference_node, validate_deck


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("deck", type=Path)
    parser.add_argument("--units", required=True, help="the unit system the deck is written in: mm-MPa or m-Pa")
    parser.add_argument("--no-materials", action="store_true", help="do not print material values or layer angles")
    args = parser.parse_args()

    text = args.deck.read_text(encoding="utf-8")
    deck = parse_deck(text, source_path=str(args.deck))  # as written, for display
    notes = validate_deck(deck)
    read_deck(args.deck, args.units)  # the SI conversion must also succeed

    print(f"{args.deck}  sha256 {deck.source_sha256[:12]}  units {args.units}")
    print(f"heading: {deck.heading or '(none)'}")
    for part in deck.parts.values():
        elements = f"{len(part.elements)} {part.elements.element_type}" if part.elements is not None else "no"
        print(f"part {part.name!r}: {len(part.nodes)} nodes, {elements} elements, {len(part.nsets)} node sets, {len(part.elsets)} element sets")
        for section in part.sections:
            layers = expanded_layers(section)
            kind = "composite" + (", symmetric" if section.symmetric else "") if len(section.layers) > 1 or section.symmetric else "homogeneous"
            print(f"  shell section on {section.elset!r}: {kind}, {len(layers)} plies, orientation {section.orientation or 'global'}")
            if not args.no_materials:
                print("   angles bottom-first: " + ", ".join(f"{layer.angle_deg:g}" for layer in layers))
                print("   thicknesses: " + ", ".join(f"{layer.thickness:g}" for layer in layers))
    print(f"assembly: {len(deck.instances)} instance(s), {len(deck.assembly_nodes)} reference node(s), "
          f"{len(deck.nsets)} node sets, {len(deck.elsets)} element sets, {len(deck.surfaces)} surfaces")
    for material in deck.materials.values():
        if args.no_materials or material.elastic is None:
            print(f"material {material.name!r}: {'(values withheld)' if material.elastic else 'no *Elastic'}"
                  f"{', with *Fail Stress' if material.fail_stress else ''}")
        else:
            e = material.elastic
            print(f"material {material.name!r}: {e.kind} E1 {e.E1:g} E2 {e.E2:g} nu12 {e.nu12:g} G12 {e.G12:g}"
                  f"{' with *Fail Stress' if material.fail_stress else ''}")
    for coupling in deck.couplings:
        print(f"coupling {coupling.name!r}: reference {node_name(reference_node(deck, coupling))} drives "
              f"{len(coupled_nodes(deck, coupling))} nodes, dofs {sorted(coupling.dofs)}")
    for step in deck.steps:
        print(f"step {step.name!r}: linear static, {len(step.boundaries)} boundary entries, {len(step.cloads)} concentrated loads")
        for boundary in step.boundaries:
            target = boundary.target if isinstance(boundary.target, str) else node_name(boundary.target)
            dofs = f"{boundary.dof_first}" if boundary.dof_first == boundary.dof_last else f"{boundary.dof_first}..{boundary.dof_last}"
            print(f"  {target}: dof {dofs} = {boundary.value:g}")
    print("ignored keywords: " + (", ".join(deck.ignored_keywords) or "none"))
    for note in notes:
        print(f"note: {note}")


if __name__ == "__main__":
    main()
