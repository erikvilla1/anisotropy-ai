"""Draw what the membrane kernel computed for a deck: mesh and deformed shape, strain fields, section forces, first-ply failure.

    uv run python examples/plot_deck.py validation/decks/coupon-2x8-grips-im7-8552.inp --units mm-MPa --out ../.local/fea-plots
    uv run python examples/plot_deck.py ../.local/abaqus/Tension-test.inp --units mm-MPa --out ../.local/fea-plots

One PNG per deck. Lengths print in the deck's units; strains are dimensionless; section forces in force per length.
A field that changes sign uses a two-hue scale with a neutral middle at zero; a field of one sign uses one hue from
light to dark, so the whole scale carries information. Needs matplotlib (a development dependency: `uv sync` installs it). Nothing about the material is printed except the first-ply-failure map,
which needs strengths; a deck without them gets the message in that panel instead.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402

from anisotropy_fea.abaqus_reader import read_deck  # noqa: E402
from anisotropy_fea.membrane import solve_membrane  # noqa: E402
from anisotropy_fea.mesh import KernelError  # noqa: E402
from anisotropy_fea.model import node_name, reference_node  # noqa: E402
from anisotropy_fea.recovery import deck_f12_star, element_ply_states, strength_ratios  # noqa: E402
from anisotropy_fea.units import from_si  # noqa: E402

INK, MUTED, GRID = "#1C1F22", "#5D636A", "#D9DCE0"
SEQUENTIAL = "Blues"  # one hue, light to dark: magnitudes
DIVERGING = "RdBu_r"  # two hues, neutral middle: signed fields, centred on zero


def polygons(xy: np.ndarray, connectivity: np.ndarray, scale: float) -> list[np.ndarray]:
    return [xy[nodes] * scale for nodes in connectivity]


def field_panel(ax, polys, values, title, label, diverging: bool, deformed=None):
    values = np.asarray(values, dtype=float)
    changes_sign = float(values.min()) < 0.0 < float(values.max())
    if diverging and changes_sign:
        limit = float(np.max(np.abs(values))) or 1.0
        norm = plt.Normalize(-limit, limit)
        cmap = DIVERGING
    else:
        # one sign only: one hue from light (zero) to dark (largest magnitude), so the whole scale carries information
        magnitude = float(np.max(np.abs(values))) or 1.0
        norm = plt.Normalize(0.0, magnitude) if values.max() > 0 else plt.Normalize(-magnitude, 0.0)
        cmap = SEQUENTIAL if values.max() > 0 else SEQUENTIAL + "_r"
    collection = PolyCollection(polys, array=np.asarray(values), cmap=cmap, norm=norm, edgecolors="white", linewidths=0.3)
    ax.add_collection(collection)
    if deformed is not None:
        ax.add_collection(PolyCollection(deformed, facecolors="none", edgecolors=INK, linewidths=0.5, alpha=0.6))
    ax.autoscale()
    ax.set_aspect("equal")
    ax.set_title(title, color=INK, fontsize=10, loc="left")
    bar = plt.colorbar(collection, ax=ax, fraction=0.046, pad=0.04)
    bar.set_label(label, color=MUTED, fontsize=8)
    bar.ax.tick_params(labelsize=7, colors=MUTED)
    style(ax)


def style(ax):
    ax.tick_params(labelsize=7, colors=MUTED)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.set_xlabel("x", color=MUTED, fontsize=8)
    ax.set_ylabel("y", color=MUTED, fontsize=8)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("deck", type=Path)
    parser.add_argument("--units", required=True)
    parser.add_argument("--out", type=Path, required=True, help="folder for the PNG")
    parser.add_argument("--magnify", type=float, default=None, help="deformation magnification; default makes the largest displacement 5 %% of the width")
    args = parser.parse_args()
    units = args.units
    deck = read_deck(args.deck, units)
    solution = solve_membrane(deck)
    mesh = solution.mesh
    length = lambda v: from_si(v, "length", units)
    xy = np.vectorize(length)(mesh.xy)
    u = np.vectorize(length)(solution.displacement)
    width = float(np.ptp(xy[:, 0])) or 1.0
    magnify = args.magnify or (0.05 * width / (float(np.max(np.abs(u))) or 1.0))
    base = polygons(xy, mesh.connectivity, 1.0)
    deformed = polygons(xy + magnify * u, mesh.connectivity, 1.0)
    N = np.vectorize(lambda v: from_si(v, "force_per_length", units))(solution.section_force)

    fig, axes = plt.subplots(2, 3, figsize=(15, 9), constrained_layout=True)
    fig.patch.set_facecolor("white")
    # 1. mesh and deformed shape
    ax = axes[0, 0]
    ax.add_collection(PolyCollection(base, facecolors="#EEF2F6", edgecolors=GRID, linewidths=0.5))
    ax.add_collection(PolyCollection(deformed, facecolors="none", edgecolors="#9A5A00", linewidths=0.8))
    for coupling in deck.couplings:
        key = reference_node(deck, coupling)
        point = xy[mesh.node(key)]
        ax.plot(*point, marker="o", markersize=6, color=INK)
        rf = solution.reaction_of([key])
        ax.annotate(f"{node_name(key)}\nRF = ({from_si(rf[0], 'force', units):.4g}, {from_si(rf[1], 'force', units):.4g}) N",
                    point, textcoords="offset points", xytext=(8, 0), fontsize=7, color=INK)
    ax.autoscale()
    ax.set_aspect("equal")
    ax.set_title(f"Mesh ({mesh.element_count} elements) and deformed shape, displacements x{magnify:.3g}", color=INK, fontsize=10, loc="left")
    style(ax)
    # 2 to 4. strains
    field_panel(axes[0, 1], base, solution.strain[:, 1], "Axial strain eps_y at element centroids", "eps_y", diverging=True)
    field_panel(axes[0, 2], base, solution.strain[:, 2], "Shear strain gamma_xy", "gamma_xy", diverging=True)
    field_panel(axes[1, 0], base, solution.strain[:, 0], "Transverse strain eps_x", "eps_x", diverging=True)
    # 5. axial section force
    field_panel(axes[1, 1], base, N[:, 1], "Axial section force N_y", f"N_y (force per length, {units})", diverging=False)
    # 6. first-ply failure
    ax = axes[1, 2]
    try:
        failure = strength_ratios(solution, "max_stress", deck_f12_star(deck), element_ply_states(solution))
        index = np.array([1.0 / r.min() for r in failure.ratio])  # 1/R: the fraction of a ply's strength used by the applied loading
        field_panel(ax, base, index, "Maximum-stress failure index 1/R, worst ply per element", "1/R (1 = first-ply failure)", diverging=False)
        e = mesh.element_keys.index(failure.element)
        centre = np.mean(base[e], axis=0)
        ax.plot(*centre, marker="x", markersize=9, color=INK, markeredgewidth=1.5)
        ax.annotate(f"first ply to fail: {failure.element[0]}.{failure.element[1]}, ply {failure.ply}, {failure.governing_mode}\n"
                    f"at {failure.factor:.3g} x the applied loading", centre, textcoords="offset points", xytext=(10, 10), fontsize=7, color=INK)
    except KernelError as exc:
        ax.text(0.02, 0.5, "First-ply failure not available:\n" + str(exc).split(": ", 1)[-1].replace("; ", ";\n"), fontsize=8, color=MUTED,
                wrap=True, transform=ax.transAxes, va="center")
        ax.set_title("First-ply failure", color=INK, fontsize=10, loc="left")
        ax.set_axis_off()
    fig.suptitle(f"{args.deck.name}: {mesh.node_count} nodes, {mesh.element_count} elements, units {units}", color=INK, fontsize=12, x=0.01, ha="left")
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{args.deck.stem}.png"
    fig.savefig(path, dpi=130)
    print("written", path)


if __name__ == "__main__":
    main()
