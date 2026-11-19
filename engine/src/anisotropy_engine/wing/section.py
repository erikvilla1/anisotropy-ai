"""The wing's cross-section as a thin-walled two-spar box: stiffness, shear flow, shear center, buckling loads and mass.

The box is the part of the section between the two spars, drawn as the shell model draws it (ADR-0116): each skin is the
airfoil's surface moved inward by half the skin's whole thickness, so it follows the airfoil's curve at its mid-thickness, and
each spar web is a straight wall at its chord position from the lower skin's mid-surface to the upper's. The walls are cut
into straight pieces and worked as one closed thin-walled cell (Megson, Aircraft Structures for Engineering Students,
4th ed., 2007, Chapters 16 to 18): the modulus-weighted centroid, unsymmetric bending, the shear flow of a vertical shear
shared by skins and webs and closed by the condition that a shear at the shear center twists nothing, and Bredt-Batho
torsion. The skin ahead of the front spar and behind the rear spar is not counted, in the stiffness or in the mass.
"""

import math
from dataclasses import dataclass

import numpy as np

from ..buckling import navier_buckling, ritz_buckling
from ..engineering import engineering_constants
from ..laminate import abd_matrices
from ..rotation import stress_transformation, transformed_reduced_stiffness
from ..sandwich import sandwich_abd
from .description import Layup, Wing

FIRST_CANTILEVER_ROOT = 1.8751040687119611  # first root of 1 + cos(x) cosh(x) = 0
WEB_PANEL_ASPECT = 5.0  # a web bay longer than this many heights buckles as one this long (an isotropic plate's load is then within 3 % of the infinite one's)
WEB_RITZ_TERMS = 14  # sine terms per direction: k_s of an isotropic plate settles to 0.1 % at aspect 5
SYMMETRY_TOLERANCE = 1e-9
SKIN_PIECES = 32  # straight pieces per skin between the spars: the section's stiffness settles to 0.01 % (theory.md)
WEB_PIECES = 8  # per web; a web is straight, so this sets only where its plies are checked
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


def mid_surface_heights(wing: Wing, x_m: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Heights of the upper and lower skin's mid-surface at chord positions `x_m` (metres from the leading edge, between the
    spars): the airfoil's surface moved inward along its normal by half the skin's whole thickness, plies and core, as
    the shape draws it (ADR-0116)."""
    g = wing.geometry
    c = g.chord_m
    half = (wing.skin.fiber_thickness_m + wing.skin.core_thickness_m) / 2
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
    laminate whose first axis is the span and whose third is the wall's outward normal. Shear flow is along that axis."""

    x_m: np.ndarray
    z_m: np.ndarray  # up from the chord line
    load_per_moment: np.ndarray  # spanwise Nx per N*m of bending moment, 1/m, tension positive
    curvature_per_moment: np.ndarray  # the wall's own spanwise curvature per N*m: how fast the strain grows outward through it
    flow_per_shear: np.ndarray  # shear flow per N of vertical shear acting at the shear center, 1/m
    mean_load_per_moment: np.ndarray  # (2,): the wall's mean Nx per N*m along its length
    mean_flow_per_shear: np.ndarray  # (2,): the wall's mean shear flow per N
    lengths_m: np.ndarray  # (2,): each wall's length in the section


@dataclass(frozen=True)
class BoxSection:
    """The two-spar box of a wing, SI units. x is from the leading edge along the chord, z up from the chord line."""

    skin: MemberLaminate
    spar: MemberLaminate
    spar_x_m: tuple[float, float]  # front, rear, from the leading edge
    spar_heights_m: tuple[float, float]  # of each web, between the skins' mid-surfaces
    skin_widths_m: tuple[float, float]  # the upper and lower skin's length round its curve between the spars
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
    skin_buckling_loads: tuple[float, float]  # N/m of compression along the span at which each skin panel buckles
    web_buckling_loads: tuple[float, float]  # N/m of shear flow at which each web's bay buckles
    mass_skins_kg: float
    mass_spars_kg: float
    mass_core_kg: float
    first_bending_frequency_Hz: float

    @property
    def mass_kg(self) -> float:
        return self.mass_skins_kg + self.mass_spars_kg + self.mass_core_kg

    @property
    def skin_buckling_load(self) -> float:
        """The lower of the two skins' buckling loads."""
        return min(self.skin_buckling_loads)


def box_section(wing: Wing) -> BoxSection:
    """Section properties of the wing's box, one side of the wing for the mass."""
    g = wing.geometry
    skin, spar = member_laminate(wing.skin), member_laminate(wing.spar)
    spar_x = (g.front_spar * g.chord_m, g.rear_spar * g.chord_m)
    x = np.linspace(spar_x[0], spar_x[1], SKIN_PIECES + 1)
    upper, lower = mid_surface_heights(wing, x)
    tops, bottoms = (upper[0], upper[-1]), (lower[0], lower[-1])
    heights = tuple(float(top - bottom) for top, bottom in zip(tops, bottoms))
    if min(heights) <= 0:
        raise ValueError("A spar web has no height between the skins' mid-surfaces: the skin is thicker than the airfoil there")

    # The cell's walls in the order of their axis, each as its points: upper skin aft to fore, front web down, lower skin
    # fore to aft, rear web up. Consecutive walls share their corner point.
    walls = [
        np.c_[x[::-1], upper[::-1]],
        np.c_[np.full(WEB_PIECES + 1, spar_x[0]), np.linspace(tops[0], bottoms[0], WEB_PIECES + 1)],
        np.c_[x, lower],
        np.c_[np.full(WEB_PIECES + 1, spar_x[1]), np.linspace(bottoms[1], tops[1], WEB_PIECES + 1)],
    ]
    members = (skin, spar, skin, spar)
    start = np.vstack([w[:-1] for w in walls])
    end = np.vstack([w[1:] for w in walls])
    wall_of = np.concatenate([np.full(len(w) - 1, k) for k, w in enumerate(walls)])
    Et = np.array([m.Ex * m.thickness_m for m in members])[wall_of]  # axial stiffness per unit length of wall
    Gt = np.array([m.Gxy * m.thickness_m for m in members])[wall_of]
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

    # Shear flow of a unit vertical shear in the cell cut open where the upper skin meets the rear web: dq/ds = -(Et / EI) * shape
    # (spanwise equilibrium of the wall with dM/dy = -V). Over a piece it is quadratic: Simpson's rule integrates it exactly.
    rise = -Et * length * (shape_start + shape_end) / 2 / EI
    q_start = np.concatenate([[0.0], np.cumsum(rise)[:-1]])
    q_mid = q_start - Et * length / 2 * (3 * shape_start + shape_end) / 4 / EI
    q_end = q_start + rise
    open_integral = length / 6 * (q_start + 4 * q_mid + q_end)
    # Close the cell with the constant flow that leaves no twist: the shear then acts at the shear center.
    closing = -float((open_integral / Gt).sum() / (length / Gt).sum())
    integral = open_integral + closing * length  # of the flow along each piece
    q_start, q_end = q_start + closing, q_end + closing
    normal = np.c_[direction[:, 1], -direction[:, 0]]  # outward: the wall's axis is the normal crossed with the span
    lever = start[:, 1] * direction[:, 0] - start[:, 0] * direction[:, 1]  # z e_x - x e_z: the same all along a straight piece
    shear_center = -float(lever @ integral)  # a unit upward force at x_sc has the flow's moment about the leading edge

    enclosed = float(np.sum(start[:, 0] * end[:, 1] - end[:, 0] * start[:, 1]) / 2)  # the axis runs counterclockwise
    GJ = 4 * enclosed**2 / float((length / Gt).sum())

    # The points of each wall with the load and flow there; a corner point belongs to both walls that meet at it.
    per_wall = []
    for k, member in enumerate(members):
        rows = wall_of == k
        stiffness, wall_length = member.Ex * member.thickness_m, float(length[rows].sum())
        mean_shape = float(length[rows] @ (shape_start[rows] + shape_end[rows]) / 2) / wall_length
        # The normal at a point: of its piece at the wall's ends, the mean of the two pieces' between them.
        pieces = normal[rows]
        at = np.vstack([pieces[:1], (pieces[1:] + pieces[:-1]) / 2, pieces[-1:]])
        at /= np.hypot(at[:, 0], at[:, 1])[:, None]
        per_wall.append((walls[k], -stiffness * np.append(shape_start[rows], shape_end[rows][-1]) / EI, -(at[:, 1] - ratio * at[:, 0]) / EI,
                         np.append(q_start[rows], q_end[rows][-1]), -stiffness * mean_shape / EI,
                         float(integral[rows].sum()) / wall_length, wall_length))

    def pair(first: int, second: int) -> WallPoints:
        a, b = per_wall[first], per_wall[second]
        return WallPoints(x_m=np.array([a[0][:, 0], b[0][:, 0]]), z_m=np.array([a[0][:, 1], b[0][:, 1]]),
                          **{name: np.array([a[i], b[i]]) for i, name in enumerate(
                              ("load_per_moment", "curvature_per_moment", "flow_per_shear", "mean_load_per_moment", "mean_flow_per_shear",
                               "lengths_m"), start=1)})

    skins, webs = pair(0, 2), pair(1, 3)
    shares = tuple(float(integral[wall_of == k] @ direction[wall_of == k, 1]) for k in (1, 3))

    widths = tuple(float(v) for v in skins.lengths_m)
    skin_buckling = tuple(skin_buckling_load(wing, skin.D, width) for width in widths)
    bay = g.rib_spacing_m if g.rib_spacing_m is not None else g.half_span_m
    web_buckling = tuple(web_shear_buckling_load(spar.D, bay, h) for h in heights)

    density = wing.skin.material.density_kg_m3
    mass_skins = sum(widths) * skin.thickness_m * g.half_span_m * density
    mass_spars = sum(heights) * spar.thickness_m * g.half_span_m * wing.spar.material.density_kg_m3
    mass_core = sum(widths) * wing.skin.core_thickness_m * g.half_span_m * (wing.skin.core_density_kg_m3 or 0.0)
    mass_core += sum(heights) * wing.spar.core_thickness_m * g.half_span_m * (wing.spar.core_density_kg_m3 or 0.0)
    mass_per_length = (mass_skins + mass_spars + mass_core) / g.half_span_m
    frequency = FIRST_CANTILEVER_ROOT**2 / (2 * math.pi) * math.sqrt(EI / (mass_per_length * g.half_span_m**4))

    return BoxSection(
        skin=skin, spar=spar, spar_x_m=spar_x, spar_heights_m=heights, skin_widths_m=widths, enclosed_area_m2=enclosed,
        centroid_m=float(centroid[1]), centroid_x_m=float(centroid[0]), EI=EI, EI_chordwise=EI_xx, EI_product=EI_xz, GJ=GJ,
        shear_shares=shares, shear_center_m=shear_center, flow_per_torque=-1 / (2 * enclosed), skins=skins, webs=webs,
        skin_buckling_loads=skin_buckling, web_buckling_loads=web_buckling,
        mass_skins_kg=mass_skins, mass_spars_kg=mass_spars, mass_core_kg=mass_core, first_bending_frequency_Hz=frequency)
