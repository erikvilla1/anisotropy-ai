"""Draw what the membrane kernel computed for a deck: mesh and deformed shape, strain fields, section forces, first-ply failure.

    uv run python examples/plot_deck.py checks/decks/coupon-2x8-grips-im7-8552.inp --units mm-MPa --out ../.local/fea/checks/plots
    uv run python examples/plot_deck.py ../.local/fea/<coupon>/from-team/<date>/<team deck>.inp --units mm-MPa --out ../.local/fea/checks/plots

One PNG per deck. Lengths print in the deck's units; strains are dimensionless; section forces in force per length.
A field that changes sign uses a two-hue scale with a neutral middle at zero; a field of one sign uses one hue from
light to dark, so the whole scale carries information. Needs matplotlib (a development dependency: `uv sync` installs it).
Nothing about the material is printed except the first-ply-failure map, which needs strengths; a deck without them gets
the message in that panel instead. `plot_solution` is importable by other examples.
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402

from anisotropy_fea.abaqus_reader import read_deck  # noqa: E402
from anisotropy_fea.membrane import solve_membrane  # noqa: E402
from anisotropy_fea.mesh import KernelError  # noqa: E402
from anisotropy_fea.model import Deck, node_name, reference_node  # noqa: E402
from anisotropy_fea.recovery import deck_f12_star, element_ply_states, strength_ratios  # noqa: E402
from anisotropy_fea.results import MembraneSolution  # noqa: E402
from anisotropy_fea.units import from_si  # noqa: E402

INK, MUTED, GRID = "#1C1F22", "#5D636A", "#D9DCE0"
SEQUENTIAL = "Blues"  # one hue, light to dark: magnitudes
DIVERGING = "RdBu_r"  # two hues, neutral middle: signed fields, centred on zero


def polygons(xy: np.ndarray, connectivity: np.ndarray, scale: float) -> list[np.ndarray]:
    return [xy[nodes] * scale for nodes in connectivity]


def field_panel(ax, polys, values, title, label, diverging: bool, deformed=None):
    values = np.asarray(values, dtype=float)
    span = float(np.max(np.abs(values))) or 1.0
    changes_sign = float(values.min()) < -1e-6 * span and float(values.max()) > 1e-6 * span  # roundoff is not a sign change
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


def plot_solution(deck: Deck, solution: MembraneSolution, units: str, path: Path, magnify: float | None = None, title: str | None = None) -> Path:
    """The six-panel figure for a solved deck, written to `path`."""
    mesh = solution.mesh
    length = lambda v: from_si(v, "length", units)  # noqa: E731
    xy = np.vectorize(length)(mesh.xy)
    u = np.vectorize(length)(solution.displacement)
    width = float(np.ptp(xy[:, 0])) or 1.0
    magnify = magnify or (0.05 * width / (float(np.max(np.abs(u))) or 1.0))
    corners = mesh.connectivity[:, :4]
    base = polygons(xy, corners, 1.0)
    deformed = polygons(xy + magnify * u, corners, 1.0)
    N = np.vectorize(lambda v: from_si(v, "force_per_length", units))(solution.section_force)

    # a long coupon (length more than three times the width) gets its six panels in one row, so each stays readable
    aspect = float(np.ptp(xy[:, 1])) / width
    fig, axes = plt.subplots(1, 6, figsize=(16, 9), constrained_layout=True) if aspect > 3 else plt.subplots(2, 3, figsize=(15, 9), constrained_layout=True)
    fig.patch.set_facecolor("white")
    panels = list(axes.flat)
    wrap = (lambda text: textwrap.fill(text, 30)) if aspect > 3 else (lambda text: text)  # narrow panels get wrapped titles
    ax = panels[0]
    ax.add_collection(PolyCollection(base, facecolors="#EEF2F6", edgecolors=GRID, linewidths=0.5))
    ax.add_collection(PolyCollection(deformed, facecolors="none", edgecolors="#9A5A00", linewidths=0.8))
    for coupling in deck.couplings:
        key = reference_node(deck, coupling)
        point = xy[mesh.node(key)]
        ax.plot(*point, marker="o", markersize=6, color=INK)
        rf = solution.reaction_of([key])
        ax.annotate(f"{node_name(key)}\nRF = ({from_si(rf[0], 'force', units):.4g}, {from_si(rf[1], 'force', units):.4g}) N",
                    point, textcoords="offset points", xytext=(8, 0), fontsize=7, color=INK)
    if not deck.couplings:
        for name in ("Grip-Top", "Grip-Bottom", "Top", "Bottom"):
            if name in deck.nsets:
                rf = solution.reaction_of(deck.nsets[name])
                if np.any(rf != 0):
                    point = xy[[mesh.node(k) for k in deck.nsets[name]]].mean(axis=0)
                    ax.annotate(f"{name}\nRF = ({from_si(rf[0], 'force', units):.4g}, {from_si(rf[1], 'force', units):.4g}) N",
                                point, textcoords="offset points", xytext=(8, 0), fontsize=7, color=INK)
    ax.autoscale()
    ax.set_aspect("equal")
    ax.set_title(wrap(f"Mesh ({mesh.element_count} elements) and deformed shape, displacements x{magnify:.3g}"), color=INK, fontsize=10, loc="left")
    style(ax)
    field_panel(panels[1], base, solution.strain[:, 1], wrap("Axial strain eps_y at element centroids"), "eps_y", diverging=True)
    field_panel(panels[2], base, solution.strain[:, 2], wrap("Shear strain gamma_xy"), "gamma_xy", diverging=True)
    field_panel(panels[3], base, solution.strain[:, 0], wrap("Transverse strain eps_x"), "eps_x", diverging=True)
    field_panel(panels[4], base, N[:, 1], wrap("Axial section force N_y"), f"N_y (force per length, {units})", diverging=False)
    ax = panels[5]
    try:
        failure = strength_ratios(solution, "max_stress", deck_f12_star(deck), element_ply_states(solution))
        index = np.array([1.0 / r.min() for r in failure.ratio])  # 1/R: the fraction of a ply's strength used by the applied loading
        field_panel(ax, base, index, wrap("Maximum-stress failure index 1/R, worst ply per element"), "1/R (1 = first-ply failure)", diverging=False)
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
    fig.suptitle(title or f"{Path(deck.source_path or 'deck').name}: {mesh.node_count} nodes, {mesh.element_count} elements, units {units}",
                 color=INK, fontsize=12, x=0.01, ha="left")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("deck", type=Path)
    parser.add_argument("--units", required=True, help="the unit system the deck is written in: mm-MPa or m-Pa")
    parser.add_argument("--out", type=Path, required=True, help="folder for the PNG")
    parser.add_argument("--magnify", type=float, default=None, help="deformation magnification; default makes the largest displacement 5 %% of the width")
    args = parser.parse_args()
    deck = read_deck(args.deck, args.units)
    solution = solve_membrane(deck)
    print("written", plot_solution(deck, solution, args.units, args.out / f"{args.deck.stem}.png", args.magnify))


if __name__ == "__main__":
    main()
