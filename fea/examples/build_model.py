"""Build a coupon model from a spec: write the deck, draw the model, solve it with our kernel, draw and export the result.

    uv run python examples/build_model.py ../.local/fea/<coupon>/ours/<coupon>.toml --out ../.local/fea/<coupon>/ours/runs/attempt-NN_<date>/run/kernel

Writes into the output folder: <spec>-abaqus.inp (the complete model in our Abaqus dialect), <spec>-model.png (the mesh
and sets before solving), summary.txt (counts, sets, layup, material citation, boundary table, SHA-256 of the deck),
and when --solve is kept (default) <spec>-solved.png, <spec>.vtu, <spec>-fields.json (every field and the summary the
studio's viewer reads, ADR-0051) and <spec>-explanation.json (the template's sentences about the result) from our membrane
kernel. Pass --no-solve to only generate. The deck for CalculiX is written with --target. --drawings without leaves out the two
pictures and the .vtu; --drawings only writes just them, from the deck the earlier run wrote: tools/run_coupon.py reports the
result first and draws afterwards (ADR-0064).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from anisotropy_fea.test_quantities import method_inputs
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.explain import explanation
from anisotropy_fea.femodel import build_model
from anisotropy_fea.fields import field_data
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.mesh import KernelError
from anisotropy_fea.mesher import MeshError
from anisotropy_fea.quality import element_quality
from anisotropy_fea.recovery import deck_f12_star, element_ply_states, strength_ratios
from anisotropy_fea.spec import TEST_CODES, SpecError, layup_text, load_spec
from anisotropy_fea.units import deck_units_of, from_si
from anisotropy_fea.write_abaqus import write_abaqus


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


def solved(deck):
    try:
        return solve_deck(deck)
    except KernelError as exc:
        raise SystemExit(f"the kernel refused the generated deck: {exc}") from None


def draw_model(model, stem: Path) -> None:
    """The model's picture before the solve; matplotlib loads only here (examples share a folder)."""
    from plot_model import plot_model  # noqa: E402

    print("written", plot_model(model, stem.with_name(f"{stem.name}-model.png")))


def draw_solution(deck, solution, units: str, stem: Path) -> None:
    """The solved model's picture and the ParaView file; matplotlib and the VTK writer load only here."""
    from export_vtk import write_vtu  # noqa: E402
    from plot_deck import plot_solution  # noqa: E402

    print("written", plot_solution(deck, solution, units, stem.with_name(f"{stem.name}-solved.png")))
    print("written", write_vtu(deck, solution, units, stem.with_name(f"{stem.name}.vtu")))


def draw(model, deck_path: Path, units: str, stem: Path) -> None:
    """--drawings only: the model's picture, then the deck an earlier run wrote solved again and drawn, so the pictures show the
    deck the result came from."""
    if not deck_path.is_file():
        raise SystemExit(f"no {deck_path.name} in {deck_path.parent}: --drawings only draws the deck an earlier run wrote there")
    draw_model(model, stem)
    deck = read_deck(deck_path, units)
    draw_solution(deck, solved(deck), units, stem)


def main() -> None:
    # the report quotes the library's units (10⁻⁶/°C), which cp1252, Windows's encoding for piped or redirected output, cannot encode
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-solve", action="store_true")
    parser.add_argument("--target", choices=["kernel", "calculix", "both"], default="kernel",
                        help="which decks to write: the Abaqus-dialect deck our kernel reads, the CalculiX deck (S8R; the mesh is promoted to order 2), or both")
    parser.add_argument("--drawings", choices=["with", "without", "only"], default="with",
                        help="the pictures and the ParaView file (<spec>-model.png, <spec>-solved.png, <spec>.vtu): with the rest (default), "
                             "without them, or only them, from the deck an earlier run wrote in --out")
    args = parser.parse_args()
    try:
        spec = load_spec(args.spec)
        model = build_model(spec)
    except (SpecError, MeshError) as exc:
        raise SystemExit(f"spec refused: {exc}") from None
    units = deck_units_of(spec.units)  # the decks, the plots and the summary are in the deck's system; the fields and the explanation in the coupon's (ADR-0061)
    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.spec.stem
    deck_path = args.out / f"{stem}-abaqus.inp"
    if args.drawings == "only":
        draw(model, deck_path, units, args.out / stem)
        return
    text = write_abaqus(model)
    deck_path.write_text(text, encoding="utf-8", newline="\n")
    print("written", deck_path)
    if args.drawings == "with":
        draw_model(model, args.out / stem)
    report = summary(model, text, units)
    if args.target in ("calculix", "both"):
        from anisotropy_fea.write_calculix import CalculixWriterError, write_calculix  # noqa: E402

        spec2 = spec if spec.mesh.element_order == 2 else spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"element_order": 2})})
        try:
            ccx_text = write_calculix(build_model(spec2))
        except CalculixWriterError as exc:
            raise SystemExit(f"CalculiX deck refused: {exc}") from None
        ccx_path = args.out / f"{stem}-ccx.inp"
        ccx_path.write_text(ccx_text, encoding="utf-8", newline="\n")
        print("written", ccx_path, "(S8R; open it in PrePoMax or run examples/run_calculix.py)")
        report += f"calculix deck sha256 {hashlib.sha256(ccx_text.encode('utf-8')).hexdigest()} (mesh promoted to order 2: S8R)\n"
    if not args.no_solve and args.target != "calculix":
        deck = read_deck(deck_path, units)
        solution = solved(deck)
        if args.drawings == "with":
            draw_solution(deck, solution, units, args.out / stem)
        if model.plate:  # first: a plate under pressure or out-of-plane loads is solved as a bending shell too, and has no nose
            components = 3 if model.bending else 2
            parts = []
            for name in model.support_sets:
                rf = solution.reaction_of(deck.nsets[name])[:components]
                parts.append(f"{name} [" + ", ".join(f"{from_si(v, 'force', units):.6g}" for v in rf) + "] N")
            report += (f"\nkernel solve ({'flat shell' if model.bending else 'membrane'}): reactions at the supports {'; '.join(parts)}; "
                       f"sum of reactions {np.round(solution.total_reaction[:components], 6).tolist()} N (balances the applied loads); "
                       f"largest free-dof residual {solution.free_residual:.3g} N\n")
        elif model.bending:
            # the nose carries the force the coupon resists; the supports share it
            reaction_set = model.nose_sets[0]
            rf = solution.reaction_of(deck.nsets[reaction_set])[:3]
            residual = float(max(abs(v) for v in solution.total_reaction[:3]))
            supports = "; ".join(f"{name} {from_si(solution.reaction_of(deck.nsets[name])[2], 'force', units):.6g} N" for name in model.support_sets[:2])
            w = solution.displacement[:, 2]
            at = int(np.argmax(np.abs(w)))
            components = ", ".join(f"{from_si(v, 'force', units):.6g}" for v in rf)
            report += (f"\nkernel solve (flat shell): reaction at {reaction_set} = [{components}] N "
                       f"(x, y, z); supports along z: {supports}; largest deflection w = {from_si(w[at], 'length', units):.6g} at node {at + 1}; "
                       f"equilibrium residual {residual:.3g} N; largest free-dof residual {solution.free_residual:.3g} N\n")
        else:
            # under displacement control the moving grip carries the reaction; under force control the fixed grip does
            moving = spec.loading.control == "displacement"
            reaction_set = ("RF-Top" if moving else "RF-Bottom") if model.couplings else ("Grip-Top" if moving else "Grip-Bottom")
            rf = solution.reaction_of(deck.nsets[reaction_set])
            applied = sum(load.value for load in model.loads)
            residual = max(abs(solution.total_reaction[0]), abs(solution.total_reaction[1] + applied))
            report += f"\nkernel solve: reaction at {reaction_set} = [{from_si(rf[0], 'force', units):.6g}, {from_si(rf[1], 'force', units):.6g}] N; " \
                      f"equilibrium residual {residual:.3g} N; largest free-dof residual {solution.free_residual:.3g} N\n"
        field = element_ply_states(solution)
        available = []
        for criterion in spec.output.fpf_criteria:
            try:
                failure = strength_ratios(solution, criterion, deck_f12_star(deck), field)
                report += (f"first-ply failure, {criterion}: factor {failure.factor:.6g} on the applied loading, element {failure.element[0]}.{failure.element[1]}, "
                           f"ply {failure.ply}{f' ({failure.face} face)' if failure.face else ''}, {failure.governing_mode}\n")
                available.append(criterion)
            except KernelError as exc:
                report += f"first-ply failure, {criterion}: not available ({exc})\n"
        coupon = {"designation": spec.coupon.designation if spec.coupon else None, "title": spec.title, "kind": spec.kind,
                  "test": TEST_CODES[spec.kind][1], "layup": layup_text(spec)}
        data = field_data(deck, solution, spec.units, criteria=tuple(available), quality=element_quality(model.mesh.xy, model.mesh.corners), coupon=coupon,
                          method=method_inputs(spec))  # the test standard's quantities, when the spec names one (ADR-0072)
        fields_path = args.out / f"{stem}-fields.json"
        fields_path.write_text(json.dumps(data), encoding="utf-8")
        print("written", fields_path)
        words = explanation(data["summary"], coupon, spec.units, data["labels"])
        explanation_path = args.out / f"{stem}-explanation.json"
        explanation_path.write_text(json.dumps(words, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("written", explanation_path)
        report += "".join(f"{sentence}\n" for sentence in words["sentences"])
    (args.out / "summary.txt").write_text(report, encoding="utf-8", newline="\n")
    print("written", args.out / "summary.txt")
    print(report)


if __name__ == "__main__":
    main()
