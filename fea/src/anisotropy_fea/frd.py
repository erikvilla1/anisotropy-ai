"""CalculiX's .frd result file, read for what a viewer shows of it (ADR-0030 amendment 6).

PrePoMax and ParaView read the .frd; our comparison records read the .dat. The two say different things about the same run: the
.dat holds the integration-point values of the probe elements we asked for, in the axes we asked for; the .frd holds every node of
the expanded model (one twenty-node brick per element and ply, so a composite shell of eight plies is eight unconnected layers of
bricks), its stresses in the GLOBAL axes and extrapolated from the integration points to the nodes, then averaged between the
bricks of one ply that share a node. A viewer's "S11" is therefore the global sigma_xx, across the width of a coupon whose length
runs along y, not a ply's fibre stress; its von Mises is the three-dimensional invariant of that nodal state. This module parses the
file's node and result blocks and finds the extremes a viewer would show, so the page can print the very numbers PrePoMax prints,
with the node they sit at. No physics beyond the invariant; the kernel's own fields stay the result (ADR-0001).

The format (CalculiX's cgx manual, "frd file format"): `    2C` opens the node block, `    3C` the element block; a result block
opens with ` -4  NAME` followed by ` -5` component lines; every data line starts with ` -1`, then the node number in 10 columns and
the values in 12 columns each; ` -3` closes a block.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from anisotropy_engine.rotation import stress_transformation

STRESS_COMPONENTS = ("SXX", "SYY", "SZZ", "SXY", "SYZ", "SZX")  # the order CalculiX writes the STRESS block
AXES = "global"
LAYERS = "one brick per element and ply, values extrapolated to the nodes and averaged within a ply"


class FrdError(ValueError):
    """The file is not a CalculiX .frd this module can read."""


@dataclass(frozen=True)
class Frd:
    """The nodes and the nodal results of one step of a .frd, in the deck's units."""

    nodes: dict[int, tuple[float, float, float]]
    stress: dict[int, tuple[float, ...]]  # node -> (SXX, SYY, SZZ, SXY, SYZ, SZX)
    displacement: dict[int, tuple[float, ...]]  # node -> (D1, D2, D3)
    elements: dict[int, tuple[int, ...]] = field(default_factory=dict)  # brick -> its nodes, as the `3C` block lists them (ADR-0066)

    @property
    def node_count(self) -> int:
        return len(self.nodes)


@dataclass(frozen=True)
class FrdPly:
    """One ply as the `.frd`'s bricks are assigned to it: the stated angle (for the label), the fibre angle from global x (the rotation,
    ADR-0065) and the thickness in the file's units, listed from the bottom face up (ADR-0004)."""

    angle_deg: float
    fibre_deg: float
    thickness: float


def read_frd(path: Path | str) -> Frd:
    """The file's node block and its DISP and STRESS blocks; the last step's values when there are several."""
    nodes: dict[int, tuple[float, float, float]] = {}
    stress: dict[int, tuple[float, ...]] = {}
    displacement: dict[int, tuple[float, ...]] = {}
    elements: dict[int, tuple[int, ...]] = {}
    block: str | None = None
    with Path(path).open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("    2C"):
                block = "nodes"
                continue
            if line.startswith("    3C"):
                block = "elements"
                continue
            if line.startswith(" -4  "):
                block = line[5:13].strip()
                continue
            if line.startswith(" -3"):
                block = None
                continue
            if block == "elements":  # ` -1` opens a brick (its number in 10 columns), the ` -2` lines list its nodes, 10 columns each
                try:
                    if line.startswith(" -1"):
                        element = int(line[3:13])
                        elements[element] = ()
                    elif line.startswith(" -2"):
                        text = line.rstrip("\n")
                        elements[element] += tuple(int(text[3 + 10 * i:13 + 10 * i]) for i in range((len(text) - 3) // 10))
                except (ValueError, NameError) as exc:
                    raise FrdError(f"{Path(path).name}: cannot read the element line {line.rstrip()!r}") from None
                continue
            if not line.startswith(" -1") or block is None:
                continue
            try:
                node = int(line[3:13])
                if block == "nodes":
                    nodes[node] = (float(line[13:25]), float(line[25:37]), float(line[37:49]))
                elif block == "STRESS":
                    stress[node] = tuple(float(line[13 + 12 * i:25 + 12 * i]) for i in range(6))
                elif block == "DISP":
                    displacement[node] = tuple(float(line[13 + 12 * i:25 + 12 * i]) for i in range(3))
            except ValueError as exc:
                raise FrdError(f"{Path(path).name}: cannot read the {block} line {line.rstrip()!r}") from None
    if not nodes:
        raise FrdError(f"{Path(path).name}: no node block (`    2C`); is this a CalculiX .frd?")
    if not stress:
        raise FrdError(f"{Path(path).name}: no STRESS block; the deck asked for no *EL FILE S")
    return Frd(nodes=nodes, stress=stress, displacement=displacement, elements=elements)


def von_mises(s: tuple[float, ...]) -> float:
    """The three-dimensional von Mises invariant of (SXX, SYY, SZZ, SXY, SYZ, SZX), as a viewer computes it from the nodal state."""
    sxx, syy, szz, sxy, syz, szx = s
    return math.sqrt(0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2) + 3.0 * (sxy ** 2 + syz ** 2 + szx ** 2))


def _place(frd: Frd, node: int) -> list[float]:
    return [round(v, 4) for v in frd.nodes.get(node, (math.nan, math.nan, math.nan))]


def frd_peaks(frd: Frd, gauge: tuple[float, float] | None = None, digits: int = 5) -> dict:
    """What a viewer shows of the stress block: the largest nodal von Mises and where it sits, the extremes of SXX and SYY and the
    largest |SXY|, each with its node and position; and, with `gauge` = (y_from, y_to) in the file's units, the same extremes over
    the nodes between those rows, where the field is uniform and the two solvers agree. Flat keys, so the record's TOML writer
    takes them as they are."""

    def rounded(v: float) -> float:
        return float(f"{v:.{digits}g}")

    def at(node: int, value: float, name: str) -> dict:
        return {name: rounded(value), f"{name}_node": node, f"{name}_xyz": _place(frd, node)}

    out: dict = {"nodes": frd.node_count, "axes": AXES, "layers": LAYERS}
    mises = {node: von_mises(s) for node, s in frd.stress.items()}
    node = max(mises, key=mises.get)
    out.update(at(node, mises[node], "mises_max"))
    for index, name in ((0, "sxx"), (1, "syy")):
        hi = max(frd.stress, key=lambda n: frd.stress[n][index])
        lo = min(frd.stress, key=lambda n: frd.stress[n][index])
        out.update(at(hi, frd.stress[hi][index], f"{name}_max"))
        out.update(at(lo, frd.stress[lo][index], f"{name}_min"))
    shear = max(frd.stress, key=lambda n: abs(frd.stress[n][3]))
    out.update(at(shear, frd.stress[shear][3], "sxy_max_abs"))
    if gauge is not None:
        y_from, y_to = gauge
        inside = [n for n in frd.stress if n in frd.nodes and y_from < frd.nodes[n][1] < y_to]
        out["gauge_from"], out["gauge_to"], out["gauge_nodes"] = rounded(y_from), rounded(y_to), len(inside)
        if inside:
            node = max(inside, key=mises.get)
            out.update(at(node, mises[node], "gauge_mises_max"))
            node = max(inside, key=lambda n: frd.stress[n][1])
            out.update(at(node, frd.stress[node][1], "gauge_syy_max"))
            node = max(inside, key=lambda n: abs(frd.stress[n][0]))
            out.update(at(node, frd.stress[node][0], "gauge_sxx_max_abs"))
    return out


def ply_of_nodes(frd: Frd, plies: Sequence[FrdPly]) -> dict[int, int]:
    """Which ply each node belongs to, 0 for the bottom ply. The expanded model is one brick per element and ply, the plies unconnected,
    so a node sits in the bricks of one ply only; the ply is read from the mean z of the brick's nodes against the laminate's ply
    interfaces, the laminate's middle at z = 0 (CalculiX puts the shell's reference surface there). A file without an element block
    gives an empty map (ADR-0066)."""
    thickness = sum(p.thickness for p in plies)
    tops = []
    z = -thickness / 2.0
    for p in plies:
        z += p.thickness
        tops.append(z)
    out: dict[int, int] = {}
    for nodes in frd.elements.values():
        known = [frd.nodes[n][2] for n in nodes if n in frd.nodes]
        if not known:
            continue
        mid = sum(known) / len(known)
        ply = next((k for k, top in enumerate(tops) if mid < top), len(plies) - 1)
        for n in nodes:
            out.setdefault(n, ply)
    return out


def frd_ply_peaks(frd: Frd, plies: Sequence[FrdPly], gauge: tuple[float, float] | None = None, digits: int = 5) -> list[dict]:
    """Each ply's peaks in its own fibre axes, the quantity the page's Summary reads (ADR-0066): the nodal global state of the ply's
    bricks rotated by the ply's fibre angle, then the largest sigma_1 and sigma_2 and the largest |tau_12|, each with its node and
    position, and with `gauge` = (y_from, y_to) the largest sigma_1 over the ply's nodes between those rows. Beside them, `s1_max_abs`
    and `s2_max_abs`: sigma_1 and sigma_2 at their largest magnitude, signed, the definition our own per-ply peaks use (fields.ply_peaks),
    so a table that sets the two side by side compares one quantity (a 90-degree ply's largest sigma_1 in tension and its largest in
    magnitude, in compression, are different numbers). A nodal value is extrapolated from the integration points, so a peak here sits
    above the same ply's centroid value; the gauge values match."""

    def rounded(v: float) -> float:
        return float(f"{v:.{digits}g}")

    ply_of = ply_of_nodes(frd, plies)
    out = []
    for k, ply in enumerate(plies):
        rotation = stress_transformation(ply.fibre_deg)
        local: dict[int, tuple[float, float, float]] = {}
        for node, s in frd.stress.items():
            if ply_of.get(node) != k:
                continue
            s1, s2, t12 = rotation @ (s[0], s[1], s[3])
            local[node] = (float(s1), float(s2), float(t12))
        entry: dict = {"ply": k + 1, "angle": ply.angle_deg, "fibre": ply.fibre_deg, "nodes": len(local)}
        if not local:
            out.append(entry)
            continue
        for name, pick in (("s1_max", lambda n: local[n][0]), ("s2_max", lambda n: local[n][1]), ("t12_max_abs", lambda n: abs(local[n][2])),
                           ("s1_max_abs", lambda n: abs(local[n][0])), ("s2_max_abs", lambda n: abs(local[n][1]))):
            node = max(local, key=pick)
            index = {"s1_max": 0, "s2_max": 1, "t12_max_abs": 2, "s1_max_abs": 0, "s2_max_abs": 1}[name]
            entry[name], entry[f"{name}_node"], entry[f"{name}_xyz"] = rounded(local[node][index]), node, _place(frd, node)
        if gauge is not None:
            inside = [n for n in local if n in frd.nodes and gauge[0] < frd.nodes[n][1] < gauge[1]]
            if inside:
                node = max(inside, key=lambda n: local[n][0])
                entry["gauge_s1_max"], entry["gauge_s1_max_node"] = rounded(local[node][0]), node
        out.append(entry)
    return out
