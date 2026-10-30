"""Draw what the kernel computed for a deck: mesh and deformed shape, strain fields, section forces, first-ply failure.

    uv run python examples/plot_deck.py checks/decks/coupon-2x8-grips-im7-8552.inp --units mm-MPa --out ../.local/fea/checks/plots
    uv run python examples/plot_deck.py ../.local/fea/<coupon>/team/<date>/<team deck>.inp --units mm-MPa --out ../.local/fea/checks/plots

One PNG per deck, six panels in two rows of three, lettered large enough to read at page width. Lengths print in the
deck's units; strains are dimensionless; section forces in force per length. A signed field that changes sign uses a
two-hue scale with a neutral middle at zero; a field of one sign (roundoff of the other sign aside) uses one hue from
light (zero) to dark (its largest magnitude), so the whole scale carries information whichever the sign. Needs matplotlib
(a development dependency: `uv sync` installs it).
A deck the flat shell solves (ADR-0053) shows the deflection w, the moment and the curvature along the coupon and the transverse
shear force instead of the membrane strains, since those are what bending is.
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
from matplotlib.collections import LineCollection, PolyCollection  # noqa: E402

from anisotropy_fea.abaqus_reader import read_deck  # noqa: E402
from anisotropy_fea.kernel import solve_deck  # noqa: E402
from anisotropy_fea.mesh import KernelError  # noqa: E402
from anisotropy_fea.model import Deck, node_name, reference_node  # noqa: E402
from anisotropy_fea.recovery import deck_f12_star, element_ply_states, ply_ratio_per_ply, strength_ratios  # noqa: E402
from anisotropy_fea.results import ShellSolution, Solution  # noqa: E402
from anisotropy_fea.units import from_si  # noqa: E402

INK, MUTED, GRID = "#1C1F22", "#5D636A", "#D9DCE0"
LENGTH_UNIT = {"mm-MPa": "mm", "m-Pa": "m"}
FORCE_PER_LENGTH_UNIT = {"mm-MPa": "N/mm", "m-Pa": "N/m"}
MOMENT_UNIT = {"mm-MPa": "N·mm/mm", "m-Pa": "N·m/m"}
TITLE, LABEL, TICKS = 13, 11, 10  # font sizes: the figure prints at about 0.6 of its size on a letter page
SEQUENTIAL = "Blues"  # one hue, light to dark: magnitudes
DIVERGING = "RdBu_r"  # two hues, neutral middle: signed fields, centred on zero


def polygons(xy: np.ndarray, connectivity: np.ndarray, scale: float) -> list[np.ndarray]:
    return [xy[nodes] * scale for nodes in connectivity]


def field_panel(ax, polys, values, title, label, diverging: bool, unit: str, deformed=None) -> PolyCollection:
    values = np.asarray(values, dtype=float)
    span = float(np.max(np.abs(values))) or 1.0
    changes_sign = float(values.min()) < -1e-6 * span and float(values.max()) > 1e-6 * span  # roundoff is not a sign change
    if diverging and changes_sign:
        norm = plt.Normalize(-span, span)
        cmap = DIVERGING
    else:
        # one sign only: one hue from light (zero) to dark (largest magnitude). The sign is the one of the largest magnitude, so a
        # field negative everywhere but for roundoff above zero is drawn on the negative scale, not clipped white
        negative = abs(float(values.min())) > abs(float(values.max()))
        norm = plt.Normalize(-span, 0.0) if negative else plt.Normalize(0.0, span)
        cmap = SEQUENTIAL + "_r" if negative else SEQUENTIAL
    collection = PolyCollection(polys, array=values, cmap=cmap, norm=norm, edgecolors="white", linewidths=0.3)
    ax.add_collection(collection)
    if deformed is not None:
        ax.add_collection(PolyCollection(deformed, facecolors="none", edgecolors=INK, linewidths=0.5, alpha=0.6))
    ax.autoscale()
    ax.set_aspect("equal")
    ax.set_title(title, color=INK, fontsize=TITLE, loc="left")
    # the colour bar sits right beside the panel's data, whatever the coupon's proportions
    bar = ax.figure.colorbar(collection, cax=ax.inset_axes([1.06, 0.2, 0.07, 0.6]))
    bar.set_label(label, color=INK, fontsize=LABEL)
    bar.ax.tick_params(labelsize=TICKS, colors=MUTED)
    style(ax, unit)
    return collection


def style(ax, unit: str):
    ax.tick_params(labelsize=TICKS, colors=MUTED)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.set_xlabel(f"x ({unit})", color=INK, fontsize=LABEL)
    ax.set_ylabel(f"y ({unit})", color=INK, fontsize=LABEL)


def plot_solution(deck: Deck, solution: Solution, units: str, path: Path, magnify: float | None = None, title: str | None = None) -> Path:
    """The six-panel figure for a solved deck, written to `path`."""
    mesh = solution.mesh
    shell = isinstance(solution, ShellSolution)
    length = lambda v: from_si(v, "length", units)  # noqa: E731
    xy = np.vectorize(length)(mesh.xy)
    u = np.vectorize(length)(solution.displacement[:, :2])
    width = float(np.ptp(xy[:, 0])) or 1.0
    magnify = magnify or (0.05 * width / (float(np.max(np.abs(u))) or 1.0))
    corners = mesh.connectivity[:, :4]
    base = polygons(xy, corners, 1.0)
    N = np.vectorize(lambda v: from_si(v, "force_per_length", units))(solution.section_force)

    # two rows of three panels; a long coupon (length more than three times the width) gets tall panels and wrapped titles
    aspect = float(np.ptp(xy[:, 1])) / width
    unit = LENGTH_UNIT[units]
    fig, axes = plt.subplots(2, 3, figsize=(11, 15) if aspect > 3 else (15, 9), constrained_layout=True)
    fig.patch.set_facecolor("white")
    panels = list(axes.flat)
    wrap = (lambda text: textwrap.fill(text, 24)) if aspect > 3 else (lambda text: textwrap.fill(text, 40))
    force = lambda f: from_si(f, "force", units)  # noqa: E731
    reaction_text = lambda rf: ", ".join(f"{force(v) if abs(v) > 1e-9 * np.max(np.abs(rf)) else 0.0:.4g}" for v in rf[:3])  # noqa: E731  roundoff as 0
    ax = panels[0]
    ax.add_collection(PolyCollection(base, facecolors="#EEF2F6", edgecolors=GRID, linewidths=0.5))
    # the coupon's outline before and after loading: an outline shows the shape where every deformed edge would hide the mesh
    corners_xy = np.stack([corners, np.roll(corners, -1, axis=1)], axis=2).reshape(-1, 2)
    edges, count = np.unique(np.sort(corners_xy, axis=1), axis=0, return_counts=True)
    boundary = edges[count == 1]
    ax.add_collection(LineCollection(xy[boundary], colors=MUTED, linewidths=1.0, linestyles="dashed"))
    if not shell:
        ax.add_collection(LineCollection((xy + magnify * u)[boundary], colors="#9A5A00", linewidths=1.6))
    # the reactions go in the title, under the names the rest of the document uses, so no label sits on the mesh or the title
    reactions = []
    for coupling in deck.couplings:
        key = reference_node(deck, coupling)
        ax.plot(*xy[mesh.node(key)], marker="o", markersize=6, color=INK)
        name = next((n for n, keys in deck.nsets.items() if tuple(keys) == (key,)), node_name(key))
        reactions.append(f"{name} ({reaction_text(solution.reaction_of([key]))}) N")
    if not deck.couplings:
        for name in ("Grip-Top", "Grip-Bottom", "Top", "Bottom", "Support-Left", "Support-Right", "Nose", "Nose-1", "Nose-2"):
            if name in deck.nsets:
                rf = solution.reaction_of(deck.nsets[name])
                if np.any(rf != 0):
                    reactions.append(f"{name} ({reaction_text(rf)}) N")
    ax.autoscale()
    ax.set_aspect("equal")
    if shell:
        w = np.vectorize(length)(solution.displacement[:, 2])
        at = int(np.argmax(np.abs(w)))
        ax.set_title(wrap(f"Mesh ({mesh.element_count} elements); the flat shell kernel. Largest deflection w = {w[at]:.4g} {unit} at node "
                          f"{node_name(mesh.node_keys[at]).rsplit('.', 1)[-1]}. Reactions (x, y, z): {'; '.join(reactions)}"), color=INK, fontsize=TITLE, loc="left")
    else:
        ax.set_title(wrap(f"Mesh ({mesh.element_count} elements); outline before (dashed) and after loading, displacements x{magnify:.3g}. "
                          f"Reactions: {'; '.join(reactions)}"), color=INK, fontsize=TITLE, loc="left")
    style(ax, unit)
    if shell:
        w_element = w[corners].mean(axis=1)
        kappa = np.vectorize(lambda v: from_si(v, "per_length", units))(solution.curvature)
        Q = np.vectorize(lambda v: from_si(v, "force_per_length", units))(solution.shear_force)
        field_panel(panels[1], base, w_element, wrap("Deflection w (element mean of the nodal values)"), f"w ({unit})", True, unit)
        field_panel(panels[2], base, solution.moment[:, 1], wrap("Bending moment along the coupon at element centroids"), rf"$M_y$ ({MOMENT_UNIT[units]})", True, unit)
        field_panel(panels[3], base, kappa[:, 1], wrap("Curvature along the coupon"), rf"$\kappa_y$ (1/{unit})", True, unit)
        field_panel(panels[4], base, Q[:, 1], wrap("Transverse shear force"), rf"$Q_y$ ({FORCE_PER_LENGTH_UNIT[units]})", True, unit)
    else:
        field_panel(panels[1], base, solution.strain[:, 1], wrap("Axial strain at element centroids"), r"$\varepsilon_y$", True, unit)
        field_panel(panels[2], base, solution.strain[:, 2], wrap("Shear strain"), r"$\gamma_{xy}$", True, unit)
        field_panel(panels[3], base, solution.strain[:, 0], wrap("Transverse strain"), r"$\varepsilon_x$", True, unit)
        field_panel(panels[4], base, N[:, 1], wrap("Axial section force"), rf"$N_y$ ({FORCE_PER_LENGTH_UNIT[units]})", True, unit)
    ax = panels[5]
    try:
        failure = strength_ratios(solution, "max_stress", deck_f12_star(deck), element_ply_states(solution))
        index = np.array([1.0 / ply_ratio_per_ply(r).min() for r in failure.ratio])  # 1/R: the fraction of a ply's strength used by the applied loading
        # the first ply to fail is named in the title and marked on the map, so no text covers the map
        face = f" ({failure.face} face)" if failure.face else ""
        field_panel(ax, base, index, wrap(f"Maximum-stress failure index 1/R, worst ply per element. First ply to fail by maximum stress (x): element "
                                          f"{failure.element[1]}, ply {failure.ply}{face}, {failure.governing_mode}, at {failure.factor:.3g} of the "
                                          "applied loading"), "1/R (1 = first-ply failure)", False, unit)
        e = mesh.element_keys.index(failure.element)
        centre = np.mean(base[e], axis=0)
        ax.plot(*centre, marker="x", markersize=12, color=INK, markeredgewidth=2)
    except KernelError as exc:
        ax.text(0.02, 0.5, "First-ply failure not available:\n" + str(exc).split(": ", 1)[-1].replace("; ", ";\n"), fontsize=LABEL, color=MUTED,
                wrap=True, transform=ax.transAxes, va="center")
        ax.set_title("First-ply failure", color=INK, fontsize=TITLE, loc="left")
        ax.set_axis_off()
    # the field panels show the free length, where the strain is: rigidly gripped tabs carry none and would take most of a long coupon's panel
    activity = solution.curvature if shell else solution.strain
    strained = np.any(np.abs(activity) > 1e-9 * float(np.max(np.abs(activity))), axis=1)
    if strained.any() and not strained.all():
        ys = np.concatenate([p[:, 1] for p, s in zip(base, strained) if s])
        margin = max(0.08 * float(np.ptp(ys)), 0.5 * width)
        for ax in panels[1:]:
            if ax.axison:
                ax.set_ylim(float(ys.min()) - margin, float(ys.max()) + margin)
    fig.suptitle(title or f"{Path(deck.source_path or 'deck').name}: {mesh.node_count} nodes, {mesh.element_count} elements, units {units}",
                 color=INK, fontsize=TITLE + 2, x=0.01, ha="left")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130, bbox_inches="tight")  # every title and colour bar inside the picture
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
    solution = solve_deck(deck)
    print("written", plot_solution(deck, solution, args.units, args.out / f"{args.deck.stem}.png", args.magnify))


if __name__ == "__main__":
    main()
