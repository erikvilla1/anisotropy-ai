"""Write what the kernel computed for a deck as a VTK unstructured grid (.vtu), for ParaView or any VTK viewer.

    uv run python examples/export_vtk.py checks/decks/coupon-2x8-grips-im7-8552.inp --units mm-MPa --out ../.local/fea/checks/vtk
    uv run python examples/export_vtk.py ../.local/fea/<coupon>/team/<date>/<team deck>.inp --units mm-MPa --out ../.local/fea/checks/vtk

Points carry the displacement (deck length units) and the reaction (N); cells carry the three strains, the three
section forces (force per length) and, when the deck has strengths, each criterion's failure index 1/R for the worst
ply of the element and the index of that ply. A deck the flat shell solves (ADR-0053) adds the deflection to the displacement,
the rotations at the points, and the curvatures, moments and transverse shear forces at the cells; its ply stresses are written per
face. Open the file in ParaView (free, https://www.paraview.org): apply, colour by a field, use Warp By Vector on Displacement to see
the deformed shape. No extra dependency: the XML is written by hand. Material values are not written. `write_vtu` is importable by
other examples.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.mesh import KernelError
from anisotropy_fea.model import Deck
from anisotropy_fea.recovery import deck_f12_star, element_ply_states, ply_ratio_per_ply, strength_ratios
from anisotropy_fea.results import ShellSolution, Solution
from anisotropy_fea.units import from_si

VTK_QUAD = 9


def array(name: str, values: np.ndarray, kind: str = "Float64") -> str:
    values = np.asarray(values)
    components = values.shape[1] if values.ndim == 2 else 1
    flat = values.reshape(-1)
    text = " ".join(f"{v:.17g}" if kind == "Float64" else str(int(v)) for v in flat)
    return f'<DataArray type="{kind}" Name="{name}" NumberOfComponents="{components}" format="ascii">\n{text}\n</DataArray>'


def write_vtu(deck: Deck, solution: Solution, units: str, path: Path) -> Path:
    """The solved deck as a .vtu file at `path`; returns the path."""
    mesh = solution.mesh
    shell = isinstance(solution, ShellSolution)
    n, ne = mesh.node_count, mesh.element_count
    length = np.vectorize(lambda v: from_si(v, "length", units))
    per_length = np.vectorize(lambda v: from_si(v, "force_per_length", units))
    points = np.column_stack([length(mesh.xy), np.zeros(n)])
    if shell:
        displacement = length(solution.displacement[:, :3])
        reaction = solution.reaction[:, :3]
        point_arrays = [array("Displacement", displacement), array("Reaction", reaction),
                        array("Rotation", np.column_stack([solution.displacement[:, 3:5], np.zeros(n)])),
                        array("Moment_reaction", np.column_stack([solution.reaction[:, 3:5], np.zeros(n)]))]
    else:
        displacement = np.column_stack([length(solution.displacement), np.zeros(n)])
        reaction = np.column_stack([solution.reaction, np.zeros(n)])
        point_arrays = [array("Displacement", displacement), array("Reaction", reaction)]
    cell_arrays = [
        array("Strain_x", solution.strain[:, 0]), array("Strain_y", solution.strain[:, 1]), array("Shear_strain_xy", solution.strain[:, 2]),
        array("N_x", per_length(solution.section_force[:, 0])), array("N_y", per_length(solution.section_force[:, 1])),
        array("N_xy", per_length(solution.section_force[:, 2])),
        array("Element_label", np.array([label for _, label in mesh.element_keys]), "Int32"),
    ]
    if shell:
        per_metre = np.vectorize(lambda v: from_si(v, "per_length", units))
        cell_arrays += [
            array("Curvature_x", per_metre(solution.curvature[:, 0])), array("Curvature_y", per_metre(solution.curvature[:, 1])),
            array("Curvature_xy", per_metre(solution.curvature[:, 2])),
            array("M_x", solution.moment[:, 0]), array("M_y", solution.moment[:, 1]), array("M_xy", solution.moment[:, 2]),
            array("Q_x", per_length(solution.shear_force[:, 0])), array("Q_y", per_length(solution.shear_force[:, 1])),
            array("Shear_strain_xz", solution.shear_strain[:, 0]), array("Shear_strain_yz", solution.shear_strain[:, 1]),
        ]
    field = element_ply_states(solution)
    f12_star = deck_f12_star(deck)
    for criterion in ("max_stress", "tsai_hill", "tsai_wu"):
        try:
            failure = strength_ratios(solution, criterion, f12_star, field)
        except KernelError:
            continue
        per_ply = [ply_ratio_per_ply(r) for r in failure.ratio]
        cell_arrays.append(array(f"Failure_index_{criterion}", np.array([1.0 / r.min() for r in per_ply])))
        cell_arrays.append(array(f"Worst_ply_{criterion}", np.array([int(np.argmin(r)) + 1 for r in per_ply]), "Int32"))
    plies = field.stress_12[0].shape[0]
    if all(s.shape[0] == plies for s in field.stress_12):
        stress = np.vectorize(lambda v: from_si(v, "stress", units))
        for k in range(plies):
            if field.faces is None:
                for i, name in enumerate(("sigma1", "sigma2", "tau12")):
                    cell_arrays.append(array(f"Ply{k + 1}_{name}", stress(np.array([s[k, i] for s in field.stress_12]))))
            else:
                for f, face in enumerate(field.faces):
                    for i, name in enumerate(("sigma1", "sigma2", "tau12")):
                        cell_arrays.append(array(f"Ply{k + 1}_{face}_{name}", stress(np.array([s[k, f, i] for s in field.stress_12]))))
    corners = mesh.connectivity[:, :4]
    xml = "\n".join([
        '<?xml version="1.0"?>',
        '<VTKFile type="UnstructuredGrid" version="0.1" byte_order="LittleEndian">',
        "<UnstructuredGrid>",
        f'<Piece NumberOfPoints="{n}" NumberOfCells="{ne}">',
        "<Points>", array("Points", points), "</Points>",
        "<Cells>", array("connectivity", corners.reshape(-1), "Int32"), array("offsets", np.arange(1, ne + 1) * 4, "Int32"),
        array("types", np.full(ne, VTK_QUAD), "UInt8"), "</Cells>",
        "<PointData>", *point_arrays, "</PointData>",
        "<CellData>", *cell_arrays, "</CellData>",
        "</Piece>", "</UnstructuredGrid>", "</VTKFile>",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(xml, encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("deck", type=Path)
    parser.add_argument("--units", required=True, help="the unit system the deck is written in: mm-MPa or m-Pa")
    parser.add_argument("--out", type=Path, required=True, help="folder for the .vtu")
    args = parser.parse_args()
    deck = read_deck(args.deck, args.units)
    solution = solve_deck(deck)
    print("written", write_vtu(deck, solution, args.units, args.out / f"{args.deck.stem}.vtu"))


if __name__ == "__main__":
    main()
