"""The wing's cross-section as a thin-walled two-spar box: stiffness, shear flow, shear center, buckling loads and mass.

The box is the part of the section between the two spars, drawn as the shell model draws it (ADR-0116): each skin is the
airfoil's surface moved inward by half the skin's whole thickness, so it follows the airfoil's curve at its mid-thickness, and
each spar web is a straight wall at its chord position from the lower skin's mid-surface to the upper's. The walls are cut
into straight pieces and worked as one closed thin-walled cell (Megson, Aircraft Structures for Engineering Students,
4th ed., 2007, Chapters 16 to 18): the modulus-weighted centroid, unsymmetric bending, the shear flow of a vertical shear
shared by skins and webs and closed by the condition that a shear at the shear center twists nothing, and Bredt-Batho
torsion. The skin ahead of the front spar and behind the rear spar is not counted, in the stiffness or in the mass.

Spar caps (ADR-0124): a cap is a strip of each skin centred on its web, with a layup of its own. Its half inside the box is part of
the cell's skin wall; its half outside is an open flange that leaves the cell at the corner, whose shear flow is nothing at its
free edge and joins the cell's at the corner. Every stretch of skin, cap or plain skin, sits at its own mid-thickness under the
airfoil's surface, so a solid cap beside a cored skin lies nearer the surface than the skin does, and the web runs between the
caps' mid-surfaces. A section is of one stretch of the span (description.span_segments); a wing whose layups change along the
span has one section per stretch.
"""

import math
from dataclasses import dataclass

import numpy as np

from ..buckling import navier_buckling, ritz_buckling
from ..engineering import engineering_constants
from ..laminate import abd_matrices
from ..rotation import stress_transformation, transformed_reduced_stiffness
from ..sandwich import sandwich_abd
from .description import Layup, SpanSegment, Wing, span_segments

FIRST_CANTILEVER_ROOT = 1.8751040687119611  # first root of 1 + cos(x) cosh(x) = 0
WEB_PANEL_ASPECT = 5.0  # a web bay longer than this many heights buckles as one this long (an isotropic plate's load is then within 3 % of the infinite one's)
WEB_RITZ_TERMS = 14  # sine terms per direction: k_s of an isotropic plate settles to 0.1 % at aspect 5
SYMMETRY_TOLERANCE = 1e-9
SKIN_PIECES = 32  # straight pieces per skin between the spars: the section's stiffness settles to 0.01 % (theory.md)
WEB_PIECES = 8  # per web; a web is straight, so this sets only where its plies are checked
FLANGE_PIECES = 4  # per half of a spar cap outside the box
SURFACE_SAMPLES = 81  # points of the airfoil's surface from which the skin's mid-surface is drawn
WALLS = ("upper skin", "front spar", "lower skin", "rear spar")  # in the order the wall axis runs round the cell


@dataclass(frozen=True)
class MemberLaminate:
    """What the calculation needs of a skin or web laminate, SI units."""

    layup: Layup
    thickness_m: float  # of the plies alone
    Ex: float  # membrane modulus along the span, Pa
    Gxy: float  # membrane shear modulus, Pa
    D: np.ndarray  # bending stiffness with the core between the halves, N*m
    angles_deg: tuple[float, ...]  # the distinct ply angles, in the order they first appear from the outside
    stress_per_load: np.ndarray  # (angles, 3, 3): [sigma1, sigma2, tau12] of a ply = this @ [Nx, Ny, Nxy]
    stress_per_curvature: np.ndarray  # (angles, 3): of the outer face of the outermost ply of each angle, per unit spanwise
    # curvature of the wall itself (1/m), its other moments free; the inner face of the same ply on the other side has the negative


def member_laminate(layup: Layup) -> MemberLaminate:
    """Membrane and bending properties of a symmetric layup. Its plies all strain alike under in-plane load,
    so one stress state per distinct ply angle is enough for the ply checks."""
    plies = layup.plies()
    A, B, _ = abd_matrices(plies)
    if np.abs(B).max() > SYMMETRY_TOLERANCE * np.abs(A).max() * layup.fiber_thickness_m:
        raise ValueError("A wing layup must be symmetric about its mid-plane")
    constants = engineering_constants(plies)
    face = layup.face()
    _, _, D = sandwich_abd(face, layup.core_thickness_m, face[::-1])
    compliance = np.linalg.inv(A)  # mid-plane strain per unit in-plane load; here the inverse is the quantity itself
    bending = np.linalg.inv(D)
    curvatures = bending[:, 0] / bending[0, 0]  # the wall's three curvatures when only its spanwise moment acts, per unit spanwise one
    angles = tuple(dict.fromkeys(layup.half_stack_deg))
    lamina = layup.material.lamina
    t, outside = layup.material.ply_thickness_m, layup.core_thickness_m / 2 + layup.fiber_thickness_m / 2
    to_ply = [stress_transformation(angle) @ transformed_reduced_stiffness(lamina, angle) for angle in angles]
    stress_per_load = np.array([m @ compliance for m in to_ply])
    stress_per_curvature = np.array([m @ curvatures * (outside - layup.half_stack_deg.index(angle) * t) for angle, m in zip(angles, to_ply)])
    return MemberLaminate(layup=layup, thickness_m=layup.fiber_thickness_m, Ex=constants.Ex, Gxy=constants.Gxy, D=D,
                          angles_deg=angles, stress_per_load=stress_per_load, stress_per_curvature=stress_per_curvature)


def web_shear_buckling_load(D: np.ndarray, length_m: float, height_m: float) -> float:
    """The shear flow at which a web bay buckles, simply supported on all four edges, the lower of the two directions of the
    shear: a web's +45 and -45 plies are not alike in bending (D16, D26), so one direction buckles it sooner, by up to about
    two on a [45/-45/0]s web. Ritz double sine series (buckling.ritz_buckling; Whitney 1987, Sections 6.5 and 6.6). The skins
    hold a real web's edges harder than simple supports, which raises its buckle; its own bending stress, left out here,
    lowers it (theory.md)."""
    length = min(length_m, WEB_PANEL_ASPECT * height_m)
    return min(ritz_buckling(D, length, height_m, [0.0, 0.0, sign], WEB_RITZ_TERMS).load_factor for sign in (1.0, -1.0))


def long_plate_buckling_load(D: np.ndarray, width_m: float) -> float:
    """Compression per unit width at which a long, simply supported, specially orthotropic plate buckles:
    2 pi^2 [sqrt(D11 D22) + D12 + 2 D66] / b^2, the lowest value of the closed form of buckling.navier_buckling over the
    length of a half-wave (Whitney 1987, Eq. 5.80; Jones, Mechanics of Composite Materials, 2nd ed., Section 5.4)."""
    return float(2 * math.pi**2 * (math.sqrt(D[0, 0] * D[1, 1]) + D[0, 1] + 2 * D[2, 2]) / width_m**2)


def skin_buckling_load(wing: Wing, D: np.ndarray, width_m: float) -> float:
    """Compression per unit width at which a skin panel `width_m` wide buckles: a long plate without ribs, the closed form of
    buckling.navier_buckling with the rib spacing as the panel's length with them. D16 and D26 are dropped (theory.md)."""
    spacing = wing.geometry.rib_spacing_m
    if spacing is None:
        return long_plate_buckling_load(D, width_m)
    orthotropic = D * np.array([[1, 1, 0], [1, 1, 0], [0, 0, 1]])
    half_waves = max(10, math.ceil(2 * spacing / width_m * (D[1, 1] / D[0, 0]) ** 0.25) + 2)
    return float(navier_buckling(orthotropic, spacing, width_m, [-1.0, 0.0, 0.0], max_half_waves=(half_waves, 1)).load_factor)


def mid_surface_heights(wing: Wing, x_m: np.ndarray, thickness_m: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Heights of the upper and lower skin's mid-surface at chord positions `x_m` (metres from the leading edge): the airfoil's
    surface moved inward along its normal by half the skin's whole thickness, plies and core, as the shape draws it (ADR-0116).
    `thickness_m` is that whole thickness, the wing's skin's when it is not given; a spar cap's is its own (ADR-0124)."""
    g = wing.geometry
    c = g.chord_m
    half = (wing.skin.fiber_thickness_m + wing.skin.core_thickness_m if thickness_m is None else thickness_m) / 2
    margin = 2 * half / c + 0.01  # the normal moves a point along the chord by less than `half`
    xs = np.linspace(max(0.0, x_m.min() / c - margin), min(1.0, x_m.max() / c + margin), SURFACE_SAMPLES)
    surfaces = np.array([g.airfoil.surface_heights(float(v)) for v in xs]).T * c
    heights = []
    for side, z in zip((1.0, -1.0), surfaces):
        slope = np.gradient(z, xs * c)
        length = np.hypot(1.0, slope)
        # The outward normal is (-z', 1) / |.| on the upper surface and (z', -1) / |.| on the lower; the mid-surface is inward.
        heights.append(np.interp(x_m, xs * c + side * half * slope / length, z - side * half / length))
    return heights[0], heights[1]


@dataclass(frozen=True)
class WallPoints:
    """The points of two walls of one kind, the two skins (upper, lower) or the two webs (front, rear), where the plies are
    checked, with what one unit of each load puts there; arrays (2, points). The wall's axis runs round the cell: forward
    along the upper skin, down the front web, aft along the lower skin, up the rear web, which is the second axis of a
    laminate whose first axis is the span and whose third is the wall's outward normal. Shear flow is along that axis. Where a
    spar cap's edge meets the skin a point is listed twice, once for each, in the order of the axis (ADR-0124)."""

    x_m: np.ndarray
    z_m: np.ndarray  # up from the chord line
    load_per_moment: np.ndarray  # spanwise Nx per N*m of bending moment, 1/m, tension positive
    curvature_per_moment: np.ndarray  # the wall's own spanwise curvature per N*m: how fast the strain grows outward through it
    flow_per_shear: np.ndarray  # shear flow per N of vertical shear acting at the shear center, 1/m
    mean_load_per_moment: np.ndarray  # (2,): the mean Nx per N*m of the wall; of a skin's panel between its caps when it has them
    mean_flow_per_shear: np.ndarray  # (2,): the wall's mean shear flow per N
    lengths_m: np.ndarray  # (2,): each wall's length in the section


@dataclass(frozen=True)
class PointSet:
    """The points of one stretch of one wall, all of one laminate: a skin's panel between its caps, a cap's half inside the box or
    outside it, or a web; arrays (points,) of the quantities of WallPoints. A cap's half outside the box carries none of the
    torque's flow (`in_cell` False)."""

    wall: int  # 0 upper skin, 1 lower skin, 2 front web, 3 rear web: the wall it belongs to, for the checks
    label: str  # "upper skin", "upper front spar cap", "front spar"
    member: MemberLaminate
    x_m: np.ndarray
    z_m: np.ndarray
    load_per_moment: np.ndarray
    curvature_per_moment: np.ndarray
    flow_per_shear: np.ndarray
    in_cell: bool


@dataclass(frozen=True)
class BoxSection:
    """The two-spar box of a wing over one stretch of its span, SI units. x is from the leading edge along the chord, z up from the
    chord line."""

    skin: MemberLaminate
    spar: MemberLaminate
    cap: MemberLaminate | None  # the spar caps', when the wing has them
    spar_x_m: tuple[float, float]  # front, rear, from the leading edge
    spar_heights_m: tuple[float, float]  # of each web, between the skins' mid-surfaces (the caps' when it has them)
    skin_widths_m: tuple[float, float]  # the upper and lower skin's length round its curve between the spars, caps included
    skin_panel_widths_m: tuple[float, float]  # the same between the caps' inner edges: the panel that buckles; all of it without caps
    enclosed_area_m2: float  # inside the walls' mid-surfaces
    centroid_m: float  # height of the modulus-weighted centroid
    centroid_x_m: float
    EI: float  # bending stiffness to the lift's moment, N*m^2: EI_zz - EI_xz^2 / EI_xx (theory.md)
    EI_chordwise: float  # EI_xx, about the vertical axis through the centroid
    EI_product: float  # EI_xz
    GJ: float  # torsion stiffness, N*m^2
    shear_shares: tuple[float, float]  # the part of a vertical shear each web carries; the skins carry the rest
    shear_center_m: float  # from the leading edge: a vertical shear here twists nothing
    flow_per_torque: float  # the shear flow of 1 N*m of torque about the span, nose up, along the walls' axis: -1 / (2 A)
    skins: WallPoints
    webs: WallPoints
    point_sets: tuple[PointSet, ...]  # every stretch of every wall, the caps' outer halves included: where the plies are checked
    skin_buckling_loads: tuple[float, float]  # N/m of compression along the span at which each skin panel buckles
    web_buckling_loads: tuple[float, float]  # N/m of shear flow at which each web's bay buckles
    mass_skins_kg_m: float  # per metre of span: the skins' plies between the spars, the caps' left out
    mass_caps_kg_m: float  # the caps' plies, both halves of each
    mass_spars_kg_m: float
    mass_core_kg_m: float
    first_bending_frequency_Hz: float  # of a uniform cantilever of this section from root to tip

    @property
    def mass_per_length_kg_m(self) -> float:
        return self.mass_skins_kg_m + self.mass_caps_kg_m + self.mass_spars_kg_m + self.mass_core_kg_m

    @property
    def skin_buckling_load(self) -> float:
        """The lower of the two skins' buckling loads."""
        return min(self.skin_buckling_loads)


@dataclass(frozen=True)
class _Run:
    """A stretch of one wall, all of one laminate, as its points in the order of its wall's axis."""

    wall: int
    label: str
    member: MemberLaminate
    points: np.ndarray  # (k + 1, 2) x, z
    in_cell: bool
    corner: int = -1  # a flange: the corner of the cell it leaves from, 0 to 3 (box_section)
    free_at_start: bool = False  # a flange: its free edge is its first point
    step: bool = False  # where a cap's mid-surface steps to the skin's: it passes the shear flow on and carries no spanwise load


def _skin_runs(wing: Wing, segment: SpanSegment, skin: MemberLaminate, cap: MemberLaminate | None, spar_x: tuple[float, float]):
    """The stretches of the skins between the spars, fore to aft, each as (name, laminate, x, upper z, lower z) at its own
    mid-surface; and the caps' halves outside the box, front and rear, the same way (none without caps)."""
    skin_thickness = segment.skin.fiber_thickness_m + segment.skin.core_thickness_m
    if cap is None:
        x = np.linspace(spar_x[0], spar_x[1], SKIN_PIECES + 1)
        return [("skin", skin, x, *mid_surface_heights(wing, x, skin_thickness))], []
    edges = wing.cap_edges_m
    cap_thickness = segment.cap.fiber_thickness_m
    total = spar_x[1] - spar_x[0]
    runs = []
    for name, member, x0, x1 in (("front spar cap", cap, spar_x[0], edges[1]), ("skin", skin, edges[1], edges[2]),
                                 ("rear spar cap", cap, edges[2], spar_x[1])):
        x = np.linspace(x0, x1, max(2, round(SKIN_PIECES * (x1 - x0) / total)) + 1)
        runs.append((name, member, x, *mid_surface_heights(wing, x, skin_thickness if name == "skin" else cap_thickness)))
    flanges = []
    for name, x0, x1 in (("front spar cap", edges[0], spar_x[0]), ("rear spar cap", spar_x[1], edges[3])):
        x = np.linspace(x0, x1, FLANGE_PIECES + 1)
        upper, lower = mid_surface_heights(wing, x, cap_thickness)
        if np.any(upper <= lower):
            raise ValueError(f"The {name} reaches where the airfoil is thinner than the cap: make it narrower")
        flanges.append((name, cap, x, upper, lower))
    return runs, flanges


def box_section(wing: Wing, segment: SpanSegment | None = None) -> BoxSection:
    """Section properties of the wing's box over one stretch of its span (description.span_segments), the root's when none is
    given: a wing without zones has one."""
    g = wing.geometry
    segment = span_segments(wing)[0] if segment is None else segment
    skin, spar = member_laminate(segment.skin), member_laminate(segment.spar)
    cap = None if segment.cap is None else member_laminate(segment.cap)
    spar_x = (g.front_spar * g.chord_m, g.rear_spar * g.chord_m)
    inside, outside = _skin_runs(wing, segment, skin, cap, spar_x)
    tops = (float(inside[0][3][0]), float(inside[-1][3][-1]))
    bottoms = (float(inside[0][4][0]), float(inside[-1][4][-1]))
    heights = tuple(top - bottom for top, bottom in zip(tops, bottoms))
    if min(heights) <= 0:
        raise ValueError("A spar web has no height between the skins' mid-surfaces: the skin is thicker than the airfoil there")

    # The cell's walls in the order of their axis, each as its runs: upper skin aft to fore, front web down, lower skin fore to aft,
    # rear web up. The cell's corners are numbered in that order from where the rear web meets the upper skin: 0 there, 1 upper
    # front, 2 lower front, 3 lower rear. A cap's outer half is a flange that runs the way its skin's axis runs, from its corner.
    runs: list[_Run] = []

    def skin_wall(wall: int, side: str, stretches) -> None:
        """A skin's runs in the order of its axis; where a cap's mid-surface and the skin's differ, a straight step joins them, as
        the skin's faces close onto the cap: the shear flow goes on through it and it carries no spanwise load."""
        for name, member, points in stretches:
            if runs and runs[-1].wall == wall and np.any(runs[-1].points[-1] != points[0]):
                runs.append(_Run(wall, f"{side} skin", skin, np.vstack([runs[-1].points[-1], points[0]]), True, step=True))
            runs.append(_Run(wall, f"{side} {name}", member, points, True))

    skin_wall(0, "upper", [(name, member, np.c_[x[::-1], upper[::-1]]) for name, member, x, upper, _ in reversed(inside)])
    runs.append(_Run(2, "front spar", spar, np.c_[np.full(WEB_PIECES + 1, spar_x[0]), np.linspace(tops[0], bottoms[0], WEB_PIECES + 1)], True))
    skin_wall(1, "lower", [(name, member, np.c_[x, lower]) for name, member, x, _, lower in inside])
    runs.append(_Run(3, "rear spar", spar, np.c_[np.full(WEB_PIECES + 1, spar_x[1]), np.linspace(bottoms[1], tops[1], WEB_PIECES + 1)], True))
    cell = len(runs)
    if outside:
        (front, _, xf, uf, lf), (rear, _, xr, ur, lr) = outside
        uf[-1], lf[-1], ur[0], lr[0] = tops[0], bottoms[0], tops[1], bottoms[1]  # each flange leaves from its corner exactly
        runs += [_Run(0, f"upper {rear}", cap, np.c_[xr[::-1], ur[::-1]], False, corner=0, free_at_start=True),
                 _Run(0, f"upper {front}", cap, np.c_[xf[::-1], uf[::-1]], False, corner=1),
                 _Run(1, f"lower {front}", cap, np.c_[xf, lf], False, corner=2, free_at_start=True),
                 _Run(1, f"lower {rear}", cap, np.c_[xr, lr], False, corner=3)]

    start = np.vstack([r.points[:-1] for r in runs])
    end = np.vstack([r.points[1:] for r in runs])
    run_of = np.concatenate([np.full(len(r.points) - 1, k) for k, r in enumerate(runs)])
    in_cell = run_of < cell
    Et = np.array([0.0 if r.step else r.member.Ex * r.member.thickness_m for r in runs])[run_of]  # axial stiffness per unit length of wall
    Gt = np.array([r.member.Gxy * r.member.thickness_m for r in runs])[run_of]
    step = end - start
    length = np.hypot(step[:, 0], step[:, 1])
    direction = step / length[:, None]

    # Modulus-weighted centroid and second moments; each piece is straight, so these integrals are exact.
    weight = Et * length
    centroid = (weight @ (start + end) / 2) / weight.sum()
    a, b = start - centroid, end - centroid  # (x, z) from the centroid
    EI_zz = float(weight @ ((a[:, 1] ** 2 + a[:, 1] * b[:, 1] + b[:, 1] ** 2) / 3))
    EI_xx = float(weight @ ((a[:, 0] ** 2 + a[:, 0] * b[:, 0] + b[:, 0] ** 2) / 3))
    EI_xz = float(weight @ ((2 * a[:, 0] * a[:, 1] + a[:, 0] * b[:, 1] + b[:, 0] * a[:, 1] + 2 * b[:, 0] * b[:, 1]) / 6))
    ratio = EI_xz / EI_xx
    EI = EI_zz - EI_xz * ratio  # the lift's moment with no chordwise moment: the section bends about an inclined axis

    # Strain per unit curvature: the lift's moment M strains a point by -(M / EI) * (z - ratio * x), from the centroid.
    shape_start, shape_end = a[:, 1] - ratio * a[:, 0], b[:, 1] - ratio * b[:, 0]

    # Shear flow of a unit vertical shear in the cell cut open where the rear web meets the upper skin: dq/ds = -(Et / EI) * shape
    # (spanwise equilibrium of the wall with dM/dy = -V). Over a piece it is quadratic: Simpson's rule integrates it exactly. A
    # flange's flow is nothing at its free edge; all it gathers on the way, its rise, joins the cell's flow at its corner, so the
    # cell's open flow comes back to nothing at the cut: the whole section's first moment about the centroid is nothing.
    rise = -Et * length * (shape_start + shape_end) / 2 / EI
    q_start = np.zeros_like(rise)
    joins = np.zeros(4)
    for k in range(cell, len(runs)):
        rows = np.nonzero(run_of == k)[0]
        gathered = np.cumsum(rise[rows])
        q_start[rows] = np.concatenate([[0.0], gathered[:-1]]) - (0.0 if runs[k].free_at_start else gathered[-1])
        joins[runs[k].corner] = gathered[-1]
    cell_rows = np.nonzero(in_cell)[0]
    inject = np.zeros(cell_rows.size)
    first = 0
    for corner, wall in enumerate((0, 2, 1, 3)):  # each wall starts at a corner
        first = next(i for i, row in enumerate(cell_rows) if runs[int(run_of[row])].wall == wall)
        inject[first] += joins[corner]
    q_start[cell_rows] = np.cumsum(inject) + np.concatenate([[0.0], np.cumsum(rise[cell_rows])[:-1]])
    q_mid = q_start - Et * length / 2 * (3 * shape_start + shape_end) / 4 / EI
    q_end = q_start + rise
    open_integral = length / 6 * (q_start + 4 * q_mid + q_end)
    # Close the cell with the constant flow that leaves no twist: the shear then acts at the shear center.
    closing = -float((open_integral[in_cell] / Gt[in_cell]).sum() / (length[in_cell] / Gt[in_cell]).sum())
    integral = open_integral + np.where(in_cell, closing * length, 0.0)  # of the flow along each piece
    q_start, q_end = q_start + np.where(in_cell, closing, 0.0), q_end + np.where(in_cell, closing, 0.0)
    normal = np.c_[direction[:, 1], -direction[:, 0]]  # outward: the wall's axis is the normal crossed with the span
    lever = start[:, 1] * direction[:, 0] - start[:, 0] * direction[:, 1]  # z e_x - x e_z: the same all along a straight piece
    shear_center = -float(lever @ integral)  # a unit upward force at x_sc has the flow's moment about the leading edge

    # The area inside the cell's walls, by the shoelace formula on their points: where a cap's edge steps from its mid-surface to the
    # skin's, the outline steps straight up or down. The axis runs counterclockwise.
    outline = np.vstack([r.points for r in runs[:cell]])
    enclosed = float(np.sum(outline[:, 0] * np.roll(outline[:, 1], -1) - np.roll(outline[:, 0], -1) * outline[:, 1]) / 2)
    GJ = 4 * enclosed**2 / float((length[in_cell] / Gt[in_cell]).sum())

    # The points of each run with the load and flow there; a step's plies are its neighbours', checked there.
    sets = []
    for k, r in enumerate(runs):
        if r.step:
            continue
        rows = run_of == k
        stiffness = r.member.Ex * r.member.thickness_m
        # The normal at a point: of its piece at the run's ends, the mean of the two pieces' between them.
        pieces = normal[rows]
        at = np.vstack([pieces[:1], (pieces[1:] + pieces[:-1]) / 2, pieces[-1:]])
        at /= np.hypot(at[:, 0], at[:, 1])[:, None]
        sets.append(PointSet(wall=r.wall, label=r.label, member=r.member, x_m=r.points[:, 0], z_m=r.points[:, 1],
                             load_per_moment=-stiffness * np.append(shape_start[rows], shape_end[rows][-1]) / EI,
                             curvature_per_moment=-(at[:, 1] - ratio * at[:, 0]) / EI,
                             flow_per_shear=np.append(q_start[rows], q_end[rows][-1]), in_cell=r.in_cell))

    def rows_of(wall: int, plain_skin: bool = False, steps: bool = False) -> np.ndarray:
        """The pieces of a wall in the cell, without its steps unless asked; with `plain_skin`, of its skin between the caps only."""
        chosen = [k for k in range(cell) if runs[k].wall == wall and (steps or not runs[k].step)
                  and (not plain_skin or runs[k].label.endswith(" skin"))]
        return np.isin(run_of, chosen)

    def mean_load(rows: np.ndarray) -> float:
        stiffness = Et[rows]
        return -float((stiffness * length[rows]) @ (shape_start[rows] + shape_end[rows]) / 2) / float(length[rows].sum()) / EI

    def wall_points(walls: tuple[int, int], means: list[float]) -> WallPoints:
        groups = [[s for s in sets[:cell] if s.wall == w] for w in walls]
        stack = {name: np.array([np.concatenate([getattr(s, name) for s in group]) for group in groups])
                 for name in ("x_m", "z_m", "load_per_moment", "curvature_per_moment", "flow_per_shear")}
        lengths = np.array([float(length[rows_of(w)].sum()) for w in walls])
        flows = np.array([float(integral[rows_of(w)].sum()) for w in walls])
        return WallPoints(**stack, mean_load_per_moment=np.array(means), mean_flow_per_shear=flows / lengths, lengths_m=lengths)

    skins = wall_points((0, 1), [mean_load(rows_of(w, plain_skin=True)) for w in (0, 1)])
    webs = wall_points((2, 3), [mean_load(rows_of(w)) for w in (2, 3)])
    shares = tuple(float(integral[rows_of(w)] @ direction[rows_of(w), 1]) for w in (2, 3))

    widths = tuple(float(v) for v in skins.lengths_m)
    panel_widths = tuple(float(length[rows_of(w, plain_skin=True)].sum()) for w in (0, 1))
    skin_buckling = tuple(skin_buckling_load(wing, skin.D, width) for width in panel_widths)
    bay = g.rib_spacing_m if g.rib_spacing_m is not None else g.half_span_m
    web_buckling = tuple(web_shear_buckling_load(spar.D, bay, h) for h in heights)

    mass_skins = sum(panel_widths) * skin.thickness_m * segment.skin.material.density_kg_m3
    mass_caps = 0.0
    if cap is not None:
        cap_rows = np.isin(run_of, [k for k, r in enumerate(runs) if r.member is cap])
        mass_caps = float(length[cap_rows].sum()) * cap.thickness_m * segment.cap.material.density_kg_m3
    mass_spars = sum(heights) * spar.thickness_m * segment.spar.material.density_kg_m3
    mass_core = sum(panel_widths) * segment.skin.core_thickness_m * (segment.skin.core_density_kg_m3 or 0.0)
    mass_core += sum(heights) * segment.spar.core_thickness_m * (segment.spar.core_density_kg_m3 or 0.0)
    mass_per_length = mass_skins + mass_caps + mass_spars + mass_core
    frequency = FIRST_CANTILEVER_ROOT**2 / (2 * math.pi) * math.sqrt(EI / (mass_per_length * g.half_span_m**4))

    return BoxSection(
        skin=skin, spar=spar, cap=cap, spar_x_m=spar_x, spar_heights_m=heights, skin_widths_m=widths, skin_panel_widths_m=panel_widths,
        enclosed_area_m2=enclosed, centroid_m=float(centroid[1]), centroid_x_m=float(centroid[0]), EI=EI, EI_chordwise=EI_xx,
        EI_product=EI_xz, GJ=GJ, shear_shares=shares, shear_center_m=shear_center, flow_per_torque=-1 / (2 * enclosed), skins=skins,
        webs=webs, point_sets=tuple(sets), skin_buckling_loads=skin_buckling, web_buckling_loads=web_buckling,
        mass_skins_kg_m=mass_skins, mass_caps_kg_m=mass_caps, mass_spars_kg_m=mass_spars, mass_core_kg_m=mass_core,
        first_bending_frequency_Hz=frequency)
