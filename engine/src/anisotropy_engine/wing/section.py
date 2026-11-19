"""The wing's cross-section as a two-spar box: stiffness, shear split, skin and web buckling loads and mass.

The box is the part of the section between the two spars. Each skin is a flat panel between the
spar tops (or bottoms) at their mean height; each spar web is a rectangle of the airfoil's height
at its chord position. The skin ahead of the front spar and behind the rear spar is not counted,
in the stiffness or in the mass. Thin-walled beam theory (Megson, Aircraft Structures for
Engineering Students, 4th ed., 2007, Chapters 16 to 18; Bruhn, Analysis and Design of Flight
Vehicle Structures, 1973, Chapter A15).
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
    angles = tuple(dict.fromkeys(layup.half_stack_deg))
    lamina = layup.material.lamina
    stress_per_load = np.array([stress_transformation(angle) @ transformed_reduced_stiffness(lamina, angle) @ compliance
                                for angle in angles])
    return MemberLaminate(layup=layup, thickness_m=layup.fiber_thickness_m, Ex=constants.Ex, Gxy=constants.Gxy, D=D,
                          angles_deg=angles, stress_per_load=stress_per_load)


def web_shear_buckling_load(D: np.ndarray, length_m: float, height_m: float) -> float:
    """The shear flow at which a web bay buckles, simply supported on all four edges, the lower of the two directions of the
    shear: a web's +45 and -45 plies are not alike in bending (D16, D26), so one direction buckles it sooner, by up to about
    two on a [45/-45/0]s web, and the hand calculation does not follow the shear's sign. Ritz double sine series
    (buckling.ritz_buckling; Whitney 1987, Sections 6.5 and 6.6). The skins hold a real web's edges harder than simple supports,
    so this is the lower bound."""
    length = min(length_m, WEB_PANEL_ASPECT * height_m)
    return min(ritz_buckling(D, length, height_m, [0.0, 0.0, sign], WEB_RITZ_TERMS).load_factor for sign in (1.0, -1.0))


def long_plate_buckling_load(D: np.ndarray, width_m: float) -> float:
    """Compression per unit width at which a long, simply supported, specially orthotropic plate buckles:
    2 pi^2 [sqrt(D11 D22) + D12 + 2 D66] / b^2, the lowest value of the closed form of buckling.navier_buckling over the
    length of a half-wave (Whitney 1987, Eq. 5.80; Jones, Mechanics of Composite Materials, 2nd ed., Section 5.4)."""
    return float(2 * math.pi**2 * (math.sqrt(D[0, 0] * D[1, 1]) + D[0, 1] + 2 * D[2, 2]) / width_m**2)


@dataclass(frozen=True)
class BoxSection:
    """The two-spar box of a wing, SI units. Heights are measured up from the chord line unless said otherwise."""

    skin: MemberLaminate
    spar: MemberLaminate
    spar_x_m: tuple[float, float]  # front, rear, from the leading edge
    spar_heights_m: tuple[float, float]
    skin_width_m: float  # between the spars
    enclosed_area_m2: float
    centroid_m: float  # of the modulus-weighted section
    skin_z_m: tuple[float, float]  # upper, lower skin from the centroid
    spar_top_z_m: tuple[float, float]  # front, rear web top from the centroid
    spar_bottom_z_m: tuple[float, float]
    EI: float  # bending stiffness, N*m^2
    GJ: float  # torsion stiffness, N*m^2
    shear_shares: tuple[float, float]  # the part of the vertical shear each web carries
    shear_center_m: float  # from the leading edge
    skin_buckling_load: float  # N/m of compression along the span
    web_buckling_loads: tuple[float, float]  # N/m of shear flow at which each web's bay buckles
    mass_skins_kg: float
    mass_spars_kg: float
    mass_core_kg: float
    first_bending_frequency_Hz: float

    @property
    def mass_kg(self) -> float:
        return self.mass_skins_kg + self.mass_spars_kg + self.mass_core_kg


def box_section(wing: Wing) -> BoxSection:
    """Section properties of the wing's box, one side of the wing for the mass."""
    g = wing.geometry
    skin, spar = member_laminate(wing.skin), member_laminate(wing.spar)
    spar_x = (g.front_spar * g.chord_m, g.rear_spar * g.chord_m)
    surfaces = [g.airfoil.surface_heights(position) for position in (g.front_spar, g.rear_spar)]
    tops = [upper * g.chord_m for upper, _ in surfaces]
    bottoms = [lower * g.chord_m for _, lower in surfaces]
    heights = [top - bottom for top, bottom in zip(tops, bottoms)]
    spar_mid = [(top + bottom) / 2 for top, bottom in zip(tops, bottoms)]
    width = spar_x[1] - spar_x[0]
    skin_heights = (sum(tops) / 2, sum(bottoms) / 2)

    # Modulus-weighted centroid and bending stiffness by the parallel axis theorem: four rectangles.
    parts = [(skin.Ex, width * skin.thickness_m, width * skin.thickness_m**3 / 12, z) for z in skin_heights]
    parts += [(spar.Ex, spar.thickness_m * h, spar.thickness_m * h**3 / 12, z) for h, z in zip(heights, spar_mid)]
    centroid = sum(E * area * z for E, area, _, z in parts) / sum(E * area for E, area, _, _ in parts)
    EI = sum(E * (own + area * (z - centroid) ** 2) for E, area, own, z in parts)

    # Bredt-Batho torsion of the single cell: GJ = 4 A^2 / (sum of s / (G t) around the wall).
    enclosed = width * sum(heights) / 2
    wall = 2 * width / (skin.Gxy * skin.thickness_m) + sum(h / (spar.Gxy * spar.thickness_m) for h in heights)
    GJ = 4 * enclosed**2 / wall

    # Each web takes vertical shear in proportion to t h^2; the shear center sits at the same weighted chord position.
    weights = [spar.thickness_m * h**2 for h in heights]
    shares = tuple(weight / sum(weights) for weight in weights)
    shear_center = sum(share * x for share, x in zip(shares, spar_x))

    if g.rib_spacing_m is None:
        buckling_load = long_plate_buckling_load(skin.D, width)
    else:
        orthotropic = skin.D * np.array([[1, 1, 0], [1, 1, 0], [0, 0, 1]])  # D16 and D26 are dropped (see theory.md)
        half_waves = max(10, math.ceil(2 * g.rib_spacing_m / width * (skin.D[1, 1] / skin.D[0, 0]) ** 0.25) + 2)
        buckling_load = navier_buckling(orthotropic, g.rib_spacing_m, width, [-1.0, 0.0, 0.0], max_half_waves=(half_waves, 1)).load_factor
        buckling_load = float(buckling_load)

    bay = g.rib_spacing_m if g.rib_spacing_m is not None else g.half_span_m
    web_buckling = tuple(web_shear_buckling_load(spar.D, bay, h) for h in heights)

    density = wing.skin.material.density_kg_m3
    mass_skins = 2 * width * skin.thickness_m * g.half_span_m * density
    mass_spars = sum(spar.thickness_m * h for h in heights) * g.half_span_m * wing.spar.material.density_kg_m3
    mass_core = 2 * width * wing.skin.core_thickness_m * g.half_span_m * (wing.skin.core_density_kg_m3 or 0.0)
    mass_core += sum(heights) * wing.spar.core_thickness_m * g.half_span_m * (wing.spar.core_density_kg_m3 or 0.0)
    mass_per_length = (mass_skins + mass_spars + mass_core) / g.half_span_m
    frequency = FIRST_CANTILEVER_ROOT**2 / (2 * math.pi) * math.sqrt(EI / (mass_per_length * g.half_span_m**4))

    return BoxSection(
        skin=skin, spar=spar, spar_x_m=spar_x, spar_heights_m=tuple(heights), skin_width_m=width, enclosed_area_m2=enclosed,
        centroid_m=centroid, skin_z_m=(skin_heights[0] - centroid, skin_heights[1] - centroid),
        spar_top_z_m=tuple(top - centroid for top in tops), spar_bottom_z_m=tuple(bottom - centroid for bottom in bottoms),
        EI=float(EI), GJ=float(GJ), shear_shares=shares, shear_center_m=shear_center, skin_buckling_load=buckling_load,
        web_buckling_loads=web_buckling,
        mass_skins_kg=mass_skins, mass_spars_kg=mass_spars, mass_core_kg=mass_core, first_bending_frequency_Hz=frequency)
