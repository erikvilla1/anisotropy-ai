"""Draw a generated model before any solve: mesh, element sets, node sets, reference points and boundary conditions.

    uv run python examples/plot_model.py validation/specs/unnotched-im7-8552-nodal.toml --out ../.local/fea-models

One PNG named after the spec. Element sets are filled in distinct muted colours, node sets drawn as markers,
fixed grips as filled triangles, the moving grip or load as an arrow, midside nodes as small dots at order 2.
"""

from __future__ import annotations

import argparse
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


def plot_model(model: FEModel, path: Path, units: str | None = None) -> Path:
    units = units or model.spec.units
    mesh = model.mesh
    xy = np.vectorize(lambda v: from_si(v, "length", units))(mesh.xy)
    polys = [xy[nodes] for nodes in mesh.corners]
    fig, ax = plt.subplots(figsize=(7, 11), constrained_layout=True)
    fig.patch.set_facecolor("white")
    ax.add_collection(PolyCollection(polys, facecolors="#F6F7F5", edgecolors=GRID, linewidths=0.4))
    handles = []
    for colour, (name, indices) in zip(SET_COLOURS, model.element_sets.items()):
        if name.startswith("Probe-"):
            continue
        ax.add_collection(PolyCollection([polys[e] for e in indices], facecolors=colour, edgecolors=GRID, linewidths=0.4))
        handles.append(plt.Rectangle((0, 0), 1, 1, facecolor=colour, edgecolor=GRID, label=f"{name} ({indices.size} elements)"))
    for name, indices in model.node_sets.items():
        if name in ("Edge-Left", "Edge-Right"):
            continue
        if name.startswith("Probe-"):
            ax.plot(*xy[indices].T, marker="o", linestyle="none", markersize=7, markerfacecolor="white", markeredgecolor=INK, label=name)
            for i in indices:
                ax.annotate(name[6:], xy[i], textcoords="offset points", xytext=(6, 4), fontsize=7, color=INK)
            continue
        colour = NODE_COLOURS.get(name, "#2F6B3F")
        ax.plot(*xy[indices].T, marker="s" if name.startswith("Grip") else "v", linestyle="none", markersize=2.2, color=colour,
                label=f"{name} ({indices.size} nodes)")
    for name, index in model.probe_elements.items():
        centre = polys[index].mean(axis=0)
        ax.plot(*centre, marker="x", markersize=7, color=INK, markeredgewidth=1.2)
        ax.annotate(f"element probe {name}", centre, textcoords="offset points", xytext=(6, -10), fontsize=7, color=INK)
    if mesh.midside is not None:
        mids = np.unique(mesh.midside)
        ax.plot(*xy[mids].T, marker=".", linestyle="none", markersize=1.5, color=MUTED, label=f"midside nodes ({mids.size})")
    for point in model.reference_points:
        p = np.array([from_si(point.xy[0], "length", units), from_si(point.xy[1], "length", units)])
        ax.plot(*p, marker="o", markersize=9, color=INK)
        ax.annotate(point.set_name, p, textcoords="offset points", xytext=(10, -3), fontsize=8, color=INK)
    # loading arrow at the moving grip
    width = float(np.ptp(xy[:, 0])) or 1.0
    top = xy[model.mesh.node_sets["Grip-Top"]].mean(axis=0) if "Grip-Top" in model.mesh.node_sets else None
    if top is not None:
        value = model.spec.loading.value
        direction = 1.0 if value > 0 else -1.0
        ax.annotate("", xy=(top[0], top[1] + direction * 0.12 * width * 2), xytext=(top[0], top[1]),
                    arrowprops=dict(arrowstyle="-|>", color="#9A5A00", lw=2))
        label = (f"{from_si(abs(value), 'length', units):g} {'mm' if units == 'mm-MPa' else 'm'}" if model.spec.loading.control == "displacement"
                 else f"{from_si(abs(value), 'force', units):g} N")
        ax.annotate(f"{model.spec.loading.control}: {label}", (top[0], top[1] + direction * 0.25 * width), fontsize=8, color=INK, ha="center")
    ax.autoscale()
    ax.margins(0.25, 0.05)
    ax.set_aspect("equal")
    ax.set_title(f"{model.spec.title}\n{mesh.mesher} mesh, {mesh.element_count} elements of order {mesh.order}, {mesh.node_count} nodes, "
                 f"grips {model.spec.grips.kind if model.spec.grips else 'none'}", fontsize=9, color=INK, loc="left")
    ax.set_xlabel("x", color=MUTED, fontsize=8)
    ax.set_ylabel("y", color=MUTED, fontsize=8)
    ax.tick_params(labelsize=7, colors=MUTED)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    legend_handles, legend_labels = ax.get_legend_handles_labels()
    ax.legend(handles + legend_handles, [h.get_label() for h in handles] + legend_labels, fontsize=7, loc="upper left",
              bbox_to_anchor=(1.02, 1.0), frameon=False)
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
