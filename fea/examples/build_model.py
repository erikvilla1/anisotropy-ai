"""Build a coupon model from a spec: write the deck, draw the model, solve it with our kernel, draw and export the result.

    uv run python examples/build_model.py validation/specs/unnotched-im7-8552-nodal.toml --out ../.local/fea-models/unnotched

Writes into the output folder: <spec>-abaqus.inp (the complete model in our Abaqus dialect), <spec>-model.png (the mesh
and sets before solving), summary.txt (counts, sets, layup, material citation, boundary table, SHA-256 of the deck),
and when --solve is kept (default) <spec>-solved.png and <spec>.vtu from our membrane kernel. Pass --no-solve to only
generate. The deck for CalculiX arrives in a later chunk.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.femodel import build_model
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.mesh import KernelError
from anisotropy_fea.recovery import deck_f12_star, element_ply_states, strength_ratios
from anisotropy_fea.spec import SpecError, load_spec
from anisotropy_fea.units import from_si
from anisotropy_fea.write_abaqus import write_abaqus

from plot_model import plot_model  # noqa: E402  (examples share a folder)


def summary(model, deck_text: str, units: str) -> str:
    mesh, spec = model.mesh, model.spec
    lines = [spec.title, f"kind {spec.kind}; units {units}; spec sha256 {spec.source_sha256}", f"deck sha256 {hashlib.sha256(deck_text.encode('utf-8')).hexdigest()}",
             f"mesh: {mesh.mesher}, order {mesh.order}, {mesh.node_count} nodes, {mesh.element_count} elements", "node sets:"]
    lines += [f"  {name}: {idx.size} nodes" for name, idx in model.node_sets.items()]
    lines.append("element sets:")
    lines += [f"  {name}: {idx.size} elements" for name, idx in model.element_sets.items()]
    lines.append(f"layup bottom-first: {[p.angle_deg for p in model.section.plies]}, ply thickness {from_si(model.section.plies[0].thickness_m, 'length', units):g}")
    lines.append(f"material {model.material.name}: {model.material.source}; rights {model.material.rights}")
    lines += [f"  {c}" for c in model.material.citation_lines]
    lines.append("boundary conditions:")
    lines += [f"  {b.target}: dofs {b.dof_first}..{b.dof_last} = {from_si(b.value, 'length', units):g}" for b in model.boundaries]
    if model.loads:
        lines.append(f"loads: {len(model.loads)} nodal loads summing to {from_si(sum(l.value for l in model.loads), 'force', units):g} N")
    lines += [f"reference point {p.set_name} at ({from_si(p.xy[0], 'length', units):g}, {from_si(p.xy[1], 'length', units):g})" for p in model.reference_points]
    lines += [f"coupling {c.name}: {c.reference_set} drives {c.node_set}" for c in model.couplings]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-solve", action="store_true")
    args = parser.parse_args()
    try:
        spec = load_spec(args.spec)
        model = build_model(spec)
    except SpecError as exc:
        raise SystemExit(f"spec refused: {exc}") from None
    units = spec.units
    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.spec.stem
    deck_path = args.out / f"{stem}-abaqus.inp"
    text = write_abaqus(model)
    deck_path.write_text(text, encoding="utf-8", newline="\n")
    print("written", deck_path)
    print("written", plot_model(model, args.out / f"{stem}-model.png"))
    report = summary(model, text, units)
    if not args.no_solve:
        from export_vtk import write_vtu  # noqa: E402
        from plot_deck import plot_solution  # noqa: E402

        deck = read_deck(deck_path, units)
        try:
            solution = solve_membrane(deck)
        except KernelError as exc:
            raise SystemExit(f"the kernel refused the generated deck: {exc}") from None
        print("written", plot_solution(deck, solution, units, args.out / f"{stem}-solved.png"))
        print("written", write_vtu(deck, solution, units, args.out / f"{stem}.vtu"))
        reaction_set = "RF-Top" if model.couplings else "Grip-Top"
        rf = solution.reaction_of(deck.nsets[reaction_set])
        report += f"\nkernel solve: reaction at {reaction_set} = [{from_si(rf[0], 'force', units):.6g}, {from_si(rf[1], 'force', units):.6g}] N; " \
                  f"equilibrium residual {max(abs(solution.total_reaction)):.3g} N; largest free-dof residual {solution.free_residual:.3g} N\n"
        field = element_ply_states(solution)
        for criterion in spec.output.fpf_criteria:
            try:
                failure = strength_ratios(solution, criterion, deck_f12_star(deck), field)
                report += (f"first-ply failure, {criterion}: factor {failure.factor:.6g} on the applied loading, element {failure.element[0]}.{failure.element[1]}, "
                           f"ply {failure.ply}, {failure.governing_mode}\n")
            except KernelError as exc:
                report += f"first-ply failure, {criterion}: not available ({exc})\n"
    (args.out / "summary.txt").write_text(report, encoding="utf-8", newline="\n")
    print("written", args.out / "summary.txt")
    print(report)


if __name__ == "__main__":
    main()
