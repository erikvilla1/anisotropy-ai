"""Draw a generated model before any solve: mesh, element sets, node sets, reference points and boundary conditions.

    uv run python examples/plot_model.py ../.local/fea/<coupon>/ours/<coupon>.toml --out ../.local/fea/<coupon>/ours/runs/attempt-NN_<date>/run/kernel

One PNG named after the spec. Element sets are filled in distinct muted colours, node sets drawn as markers,
fixed grips as filled triangles, the moving grip or load as an arrow with its signed value beside it, midside nodes as
small dots at order 2. Probes are named in a column right of the coupon, each joined to its point by a thin line, so
names never sit on each other or on the mesh; the legend is under the drawing.
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

from anisotropy_fea.femodel import FEModel, build_model  # noqa: E402
from anisotropy_fea.spec import load_spec  # noqa: E402
from anisotropy_fea.units import from_si  # noqa: E402

INK, MUTED, GRID = "#1C1F22", "#5D636A", "#D9DCE0"
# categorical fills for element sets, fixed order, muted so the mesh lines stay readable
SET_COLOURS = ["#DCE6F2", "#F2E6D8", "#E3EFD9", "#EEE0F0", "#F6F0D2", "#E0EEF0"]
NODE_COLOURS = {"Grip-Bottom": "#9A5A00", "Grip-Top": "#9A5A00", "Edge-Left": "#5D636A", "Edge-Right": "#5D636A"}
TEXT, TICKS = 11, 10  # font sizes: the figure prints at about 0.7 of its size


def label_column(ax, points: list[tuple[float, float, str]], x_text: float, gap: float) -> None:
    """Names in a column at x_text, in the order of their points' y, at least `gap` apart, each joined to its point by a thin line."""
    placed: list[float] = []
    for x, y, text in sorted(points, key=lambda p: p[1]):
        y_text = max(y, placed[-1] + gap) if placed else y
        placed.append(y_text)
        ax.annotate(text, (x, y), xytext=(x_text, y_text), textcoords="data", fontsize=TEXT, color=INK, va="center", annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6, shrinkA=0, shrinkB=2))


def plot_model(model: FEModel, path: Path, units: str | None = None) -> Path:
    units = units or model.spec.units
    mesh = model.mesh
    xy = np.vectorize(lambda v: from_si(v, "length", units))(mesh.xy)
    polys = [xy[nodes] for nodes in mesh.corners]
    unit = "mm" if units == "mm-MPa" else "m"
    fig, ax = plt.subplots(figsize=(7, 10), constrained_layout=True)
    fig.patch.set_facecolor("white")
    ax.add_collection(PolyCollection(polys, facecolors="#F6F7F5", edgecolors=GRID, linewidths=0.4))
    handles = []
    for colour, (name, indices) in zip(SET_COLOURS, model.element_sets.items()):
        if name.startswith("Probe-"):
            continue
        ax.add_collection(PolyCollection([polys[e] for e in indices], facecolors=colour, edgecolors=GRID, linewidths=0.4))
        handles.append(plt.Rectangle((0, 0), 1, 1, facecolor=colour, edgecolor=GRID, label=f"{name} ({indices.size} elements)"))
    probes: list[tuple[float, float, str]] = []
    for name, indices in model.node_sets.items():
        if name in ("Edge-Left", "Edge-Right"):
            continue
        if name.startswith("Probe-"):
            ax.plot(*xy[indices].T, marker="o", linestyle="none", markersize=7, markerfacecolor="white", markeredgecolor=INK)
            probes += [(float(xy[i, 0]), float(xy[i, 1]), f"node probe {name[6:]}") for i in indices]
            continue
        colour = NODE_COLOURS.get(name, "#2F6B3F")
        if name.startswith("Grip"):  # every node of a gripped tab: its markers would hide the tab's element set, so it is named, not drawn
            ax.plot([], [], linestyle="none", label=f"{name}: {indices.size} nodes, every node of its tab")
            continue
        ax.plot(*xy[indices].T, marker="v", linestyle="none", markersize=2.2, color=colour, label=f"{name} ({indices.size} nodes)")
    for name, index in model.probe_elements.items():
        centre = polys[index].mean(axis=0)
        ax.plot(*centre, marker="x", markersize=7, color=INK, markeredgewidth=1.2)
        probes.append((float(centre[0]), float(centre[1]), f"element probe {name}"))
    if probes:
        ax.plot([], [], marker="o", linestyle="none", markersize=7, markerfacecolor="white", markeredgecolor=INK, label="node probe")
        ax.plot([], [], marker="x", linestyle="none", markersize=7, color=INK, label="element probe")
    if mesh.midside is not None:
        mids = np.unique(mesh.midside)
        ax.plot(*xy[mids].T, marker=".", linestyle="none", markersize=1.5, color=MUTED, label=f"midside nodes ({mids.size})")
    for point in model.reference_points:
        p = np.array([from_si(point.xy[0], "length", units), from_si(point.xy[1], "length", units)])
        ax.plot(*p, marker="o", markersize=9, color=INK)
        probes.append((float(p[0]), float(p[1]), f"reference point {point.set_name}"))
    # loading arrow at the moving grip, its signed value beside it, clear of the mesh
    width = float(np.ptp(xy[:, 0])) or 1.0
    height = float(np.ptp(xy[:, 1])) or 1.0
    grip = model.mesh.node_sets.get("Grip-Top")
    top = np.array([xy[grip, 0].mean(), xy[grip, 1].max()]) if grip is not None else None  # the coupon's top edge, not the middle of the tab
    if top is not None and model.spec.loading is not None:  # a plate lists its loads; no single arrow stands for them
        value = model.spec.loading.value
        outside = top[1] + 0.06 * height  # the arrow stands above the coupon: away from the edge for a pull, onto it for a push
        start, end = ((top[1], outside) if value > 0 else (outside, top[1]))
        ax.annotate("", xy=(top[0], end), xytext=(top[0], start), arrowprops=dict(arrowstyle="-|>", color="#9A5A00", lw=2), annotation_clip=False)
        if model.spec.loading.control == "displacement":
            label = f"displacement {from_si(value, 'length', units):g} {unit} ({'pull' if value > 0 else 'shortening'})"
        else:
            label = f"force {from_si(value, 'force', units):g} N ({'tension' if value > 0 else 'compression'})"
        probes.append((float(top[0]), float(outside), label))
    ax.autoscale()
    ax.margins(0.05, 0.08)
    ax.set_aspect("equal")
    if probes:
        label_column(ax, probes, float(xy[:, 0].max()) + 0.35 * width, 0.03 * height)
    title = textwrap.fill(model.spec.title, 70)
    ax.set_title(f"{title}\n{mesh.mesher} mesh, {mesh.element_count} elements of order {mesh.order}, {mesh.node_count} nodes, "
                 f"grips {model.spec.grips.kind if model.spec.grips else 'none'}", fontsize=TEXT, color=INK, loc="left")
    ax.set_xlabel(f"x ({unit})", color=INK, fontsize=TEXT)
    ax.set_ylabel(f"y ({unit})", color=INK, fontsize=TEXT)
    ax.tick_params(labelsize=TICKS, colors=MUTED)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    legend_handles, legend_labels = ax.get_legend_handles_labels()
    ax.legend(handles + legend_handles, [h.get_label() for h in handles] + legend_labels, fontsize=TICKS, loc="upper center",
              bbox_to_anchor=(0.5, -0.06), ncol=2, frameon=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    spec = load_spec(args.spec)
    model = build_model(spec)
    path = plot_model(model, args.out / f"{args.spec.stem}-model.png")
    print("written", path)


if __name__ == "__main__":
    main()
