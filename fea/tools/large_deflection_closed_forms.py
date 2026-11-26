"""Exact and published answers for plates that deflect far, and the cases built on them (ADR-0142): the source of
`fea/checks/large_displacement_cases/`.

    uv run python tools/large_deflection_closed_forms.py            # every case's expected numbers, as this tool gives them
    uv run python tools/large_deflection_closed_forms.py --write    # rewrite the cases

Nothing here uses the package's solvers or CalculiX: the numbers are worked from the equations below and from one printed table.

The bent cantilever (the elastica). A strip of length L and bending stiffness EI, clamped at one end, carries a force P at the other
that keeps its direction, across the strip as it lay. With s the distance along the strip over L, theta(s) the angle the strip has
turned and alpha = P L^2 / EI, moment equilibrium of the part beyond s gives theta'' = -alpha cos(theta), with theta(0) = 0 at the clamp
and theta'(1) = 0 at the free end, where no moment acts. The strip does not stretch. `elastica` integrates the equation with the
classical fourth-order Runge-Kutta rule from a guessed curvature at the clamp and halves the bracket on that guess until theta'(1) = 0.
The tip then stands at w / L = integral of sin(theta) across the strip and has come back by 1 - integral of cos(theta) along it. The
equation and its solution by elliptic integrals are in Timoshenko and Gere, Theory of Elastic Stability, 2nd edition, Section 2.7; the
values agree with the tables of Bisshopp and Drucker, Quarterly of Applied Mathematics 3 (1945), and Mattiasson, International Journal
for Numerical Methods in Engineering 17 (1981), to the digits those print (at alpha = 1, 0.30172 and 0.05643). A real strip also
stretches a little. A line of the strip at height z above its middle, which had length ds, has length (1 + e0 - z kappa) ds when the
middle is stretched by e0 and bent to the curvature kappa = theta' / L toward +z, so its Lagrangian strain is
((1 + e0 - z kappa)^2 - 1) / 2. Where the strip has turned by theta, the part of the end force along it is P sin(theta). Under
CalculiX's material law (the stretch rule below) the force a line carries is its stiffness times eps (1 + eps)(1 + eps / 2) with
eps = e0 - z kappa, which is eps + 3 eps^2 / 2 to the second order; summed over the section, P sin(theta) = EA e0 + 3 EI kappa^2 / 2, so
e0 = P sin(theta) / EA - 3 EI kappa^2 / (2 EA). The second term is the law's own: a strip bent under it shortens a little along its
middle. In the cases here e0 is five parts in a hundred thousand at most, which moves the tip by less than a part in ten thousand and
is one to two percent of the strain read.

A laminate's strip, by plain laminate theory worked here by hand (the reduced stiffness of each ply, turned by its angle, summed into
A and D): bent as a beam with its sides free to curl it has EI = b / d, with d the entry of the inverse of D along the strip, and
stretched with its sides free to narrow it has EA = b / a, with a the entry of the inverse of A.

The stretch rule. CalculiX relates the second Piola-Kirchhoff stress S to the Lagrangian strain E by the constants of the small-strain
law (its manual, *ELASTIC). A strip stretched to (1 + e) times its length with its sides free has E = e + e^2 / 2 along it, S = EA E
over its first area, and pulls on its end with the force S times the stretch: F = EA e (1 + e / 2) (1 + e), whatever its Poisson's
ratio. The small-strain law gives EA e, so the rule is the factor (1 + e)(1 + e / 2).

The clamped square plate under pressure. NACA Report 740 (Samuel Levy, Square plate with clamped edges under normal pressure
producing large deflections, 1942; NASA Technical Reports Server 19930091819) solves von Karman's equations by double Fourier series
for a square plate of side a and thickness h with Poisson's ratio 0.316, its edges kept from turning and from moving across
themselves, free to slide along themselves. Table 5 lists the centre deflection over the thickness against p a^4 / (E h^4); the report
estimates the error of its deflections below 2 percent. `LEVY` holds that table, read from the scan of the report.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from anisotropy_fea import paths  # noqa: E402

# NACA Report 740, Table 5: p a^4 / (E h^4) and the centre deflection over the thickness
LEVY = ((17.79, 0.237), (38.3, 0.471), (63.4, 0.695), (95.0, 0.912), (134.9, 1.121), (184.0, 1.323), (245.0, 1.521), (318.0, 1.714), (402.0, 1.902))
LEVY_NU = 0.316

PLY = {"E1": 160000.0, "E2": 9000.0, "G12": 4700.0, "nu12": 0.32, "G13": 4700.0, "G23": 3000.0}  # a round carbon ply of our own, MPa
CROSS_PLY, PLY_THICKNESS = (0.0, 90.0, 90.0, 0.0), 0.2
E_ISOTROPIC = 70000.0
ALPHA = 10.0  # the bent cantilever's largest P L^2 / EI
FRACTIONS = (0.1, 0.2, 0.5, 1.0)
STRIP = {"length": 100.0, "width": 10.0, "nx": 2, "ny": 40}  # the cantilever; one millimetre thick when isotropic
STRETCHED = {"length": 100.0, "width": 20.0, "nx": 4, "ny": 20, "pull": 3.0}


def elastica(alpha: float, n: int = 4000) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """s, theta and theta' (the curvature times L) along the clamped strip under the end force alpha = P L^2 / EI."""
    h = 1.0 / n

    def slope(theta: float, kappa: float) -> tuple[float, float]:
        return kappa, -alpha * math.cos(theta)

    def shoot(kappa0: float) -> tuple[np.ndarray, np.ndarray]:
        theta, kappa = 0.0, kappa0
        thetas, kappas = [theta], [kappa]
        for _ in range(n):
            a1, b1 = slope(theta, kappa)
            a2, b2 = slope(theta + h / 2 * a1, kappa + h / 2 * b1)
            a3, b3 = slope(theta + h / 2 * a2, kappa + h / 2 * b2)
            a4, b4 = slope(theta + h * a3, kappa + h * b3)
            theta += h / 6 * (a1 + 2 * a2 + 2 * a3 + a4)
            kappa += h / 6 * (b1 + 2 * b2 + 2 * b3 + b4)
            thetas.append(theta)
            kappas.append(kappa)
        return np.array(thetas), np.array(kappas)

    low, high = 0.0, alpha  # the curvature at the clamp lies between none and the small-deflection beam's alpha
    for _ in range(80):
        middle = (low + high) / 2
        if shoot(middle)[1][-1] > 0:
            high = middle
        else:
            low = middle
    theta, kappa = shoot((low + high) / 2)
    return np.linspace(0.0, 1.0, n + 1), theta, kappa


def tip(alpha: float) -> tuple[float, float]:
    """The tip of the bent cantilever: its deflection across the strip and how far it has come back along it, both over L."""
    s, theta, _ = elastica(alpha)
    step = s[1] - s[0]

    def integral(y: np.ndarray) -> float:
        return float(((y[1:] + y[:-1]) / 2).sum() * step)

    return integral(np.sin(theta)), 1.0 - integral(np.cos(theta))


def station(alpha: float, at: float) -> tuple[float, float]:
    """theta and theta' at a station s along the strip: the angle turned there, and the curvature there times L."""
    s, theta, kappa = elastica(alpha)
    return float(np.interp(at, s, theta)), float(np.interp(at, s, kappa))


def line_strain(kappa: float, z: float, e0: float = 0.0) -> float:
    """The Lagrangian strain along the strip at height z above its middle, bent to the curvature kappa toward +z, its middle stretched by e0."""
    return ((1 + e0 - z * kappa) ** 2 - 1) / 2


def stretch_rule(e: float) -> float:
    """The force of a stretched strip over the small-strain law's, at the stretch e, under CalculiX's material law."""
    return (1 + e) * (1 + e / 2)


def laminate_strip(angles: tuple[float, ...], ply: float, material: dict) -> tuple[float, float]:
    """A laminate's strip per unit width, along the direction the angles are counted from: its stretching stiffness 1 / a and its
    bending stiffness 1 / d with the sides free (plain laminate theory, by hand)."""
    nu21 = material["nu12"] * material["E2"] / material["E1"]
    q = 1.0 - material["nu12"] * nu21
    Q = np.array([[material["E1"] / q, material["nu12"] * material["E2"] / q, 0.0], [material["nu12"] * material["E2"] / q, material["E2"] / q, 0.0],
                  [0.0, 0.0, material["G12"]]])
    total = ply * len(angles)
    A, D = np.zeros((3, 3)), np.zeros((3, 3))
    for k, angle in enumerate(angles):
        c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        T = np.array([[c * c, s * s, 2 * c * s], [s * s, c * c, -2 * c * s], [-c * s, c * s, c * c - s * s]])  # stress, laminate axes to the ply's
        R = np.diag([1.0, 1.0, 2.0])
        Qbar = np.linalg.inv(T) @ Q @ R @ T @ np.linalg.inv(R)
        z0, z1 = -total / 2 + k * ply, -total / 2 + (k + 1) * ply
        A += Qbar * (z1 - z0)
        D += Qbar * (z1**3 - z0**3) / 3
    return 1.0 / np.linalg.inv(A)[0, 0], 1.0 / np.linalg.inv(D)[0, 0]


def gauss_height(thickness: float, layers: int, layer: int, upper: bool) -> float:
    """The height of one of the two integration points CalculiX places through a layer of its expanded shell (layer 1 is the lowest)."""
    each = thickness / layers
    middle = -thickness / 2 + (layer - 0.5) * each
    return middle + (1 if upper else -1) * each / (2 * math.sqrt(3))


# --- the cases ------------------------------------------------------------------------------------


def number(v: float) -> str:
    return repr(float(f"{v:.10g}"))


def numbers(values) -> str:
    return "[" + ", ".join(number(v) for v in values) + "]"


def plate_table(designation: str, title: str, size_from: str, geometry: dict, layup: tuple[tuple[float, ...], float], material: dict, body: str) -> str:
    angles, ply = layup
    return f'''[plate]
title = "{designation}, plate: {title}"
kind = "plate"
units = "mm-MPa"

[plate.coupon]
designation = "{designation}"
standard = "none"
size_from = "{size_from}"
team_model = "not built yet"
test_data = "none"

[plate.geometry]
length = {geometry["length"]!r}
width = {geometry["width"]!r}

[plate.mesh]
mesher = "structured"
element_order = 2
nx = {geometry["nx"]}
ny = {geometry["ny"]}

[plate.layup]
angles = [{", ".join(f"{a:g}" for a in angles)}]
angles_from = "length"
symmetric = false
ply_thickness = {ply!r}

[plate.material]
E1 = {material["E1"]!r}
E2 = {material["E2"]!r}
G12 = {material["G12"]!r}
nu12 = {material["nu12"]!r}
[plate.material.transverse]
G13 = {material["G13"]!r}
G23 = {material["G23"]!r}
plane_stress = true
transverse_isotropy = true

{body}
[plate.output]
fpf_criteria = []
abaqus = {{ field_preselect = true, node_print = true, el_print = true }}
calculix = {{ node_print = true, el_print = true, frd = false, el_print_global = true }}
'''


def isotropic(E: float, nu: float) -> dict:
    G = E / (2 * (1 + nu))
    return {"E1": E, "E2": E, "G12": G, "nu12": nu, "G13": G, "G23": G}


def reading(name: str, what: str, of: str, component: int, values, tolerance: float, scale: float | None = None, height: float | None = None) -> str:
    lines = ["[[expected]]", f'name = "{name}"', f'what = "{what}"', f'of = "{of}"', f"component = {component}"]
    if height is not None:
        lines.append(f"height = {number(height)}")
    if scale is not None:
        lines.append(f"scale = {number(scale)}")
    return "\n".join(lines + [f"values = {numbers(values)}", f"tolerance = {tolerance!r}"]) + "\n"


def case_text(title: str, source: str, first: float, at, small: str, readings: list[str], plate: str) -> str:
    return (f'title = "{title}"\nsource = "{source}"\n\n[follow]\nfirst = {first!r}\nat = {numbers(at)}\n\n{small}\n' + "\n".join(readings) + "\n" + plate)


def levy_case() -> tuple[str, str]:
    side, h, E = 200.0, 2.0, 70000.0
    top = LEVY[-1][0]
    pressure = top * E * h**4 / side**4
    body = "\n".join(f'[[plate.supports]]\nregion = "{region}"\ndofs = {dofs}' for region, dofs in
                     (("Edge-Left", "[1, 3, 5]"), ("Edge-Right", "[1, 3, 5]"), ("Edge-Bottom", "[2, 3, 4]"), ("Edge-Top", "[2, 3, 4]")))
    body += f'\n\n[[plate.loads]]\nregion = "Face"\npressure = {number(-pressure)}\n\n[plate.probes]\nnodes = {{ centre = [{side / 2!r}, {side / 2!r}] }}\n'
    plate = plate_table("NOM-PLT-L2", "a clamped square isotropic plate under a pressure that deflects it up to 1.9 thicknesses", "NACA Report 740",
                        {"length": side, "width": side, "nx": 16, "ny": 16}, ((0.0,), h), isotropic(E, LEVY_NU), body)
    source = ("NACA Report 740 (Samuel Levy, Square plate with clamped edges under normal pressure producing large deflections, 1942; NASA Technical "
              "Reports Server 19930091819), Table 5: the centre deflection over the thickness against p a^4 / (E h^4) for a square plate of side a "
              "and thickness h with Poisson's ratio 0.316, its edges kept from turning and from moving across themselves and free to slide along "
              "themselves, by a double Fourier series solution of von Karman's equations whose error the report estimates below 2 percent. Here "
              f"a = {side:g} mm, h = {h:g} mm, E = {E:g} MPa, and the pressure rises to {pressure:.4g} MPa, the table's last row; it presses toward "
              "+z. The plate is 16 by 16 eight-node elements: CalculiX's deflection is 0.2 percent below the table at the first row and 2.0 percent "
              "below at the last, and moves by less than 0.05 percent from 16 to 32 elements a side, so the difference is not the mesh's. The "
              "tolerance holds that difference and no more. The report's stresses are not compared: at the centre CalculiX's membrane stress is "
              "about a tenth above the table's and its bending stress about a tenth below, their sum 3 percent below (ADR-0142, open).")
    small = "[small_load]\nfactor = 0.001\ntolerance = 1e-4\nkernel_tolerance = 0.02\n"
    readings = [reading("centre deflection over the thickness", "displacement", "centre", 3, [w for _, w in LEVY], 0.025, scale=1 / h)]
    return "clamped-square-plate-under-pressure-naca-740", case_text(
        "A clamped square plate under pressure, deflected up to 1.9 times its thickness: CalculiX's large-displacement answer follows NACA Report 740",
        source, 0.02, [ratio / top for ratio, _ in LEVY], small, readings, plate)


def cantilever_case(laminate: bool) -> tuple[str, str]:
    L, b = STRIP["length"], STRIP["width"]
    if laminate:
        angles, ply, material = CROSS_PLY, PLY_THICKNESS, PLY
        EA, EI = (b * v for v in laminate_strip(angles, ply, material))
        what, designation, layers = "a [0/90]s laminate's strip", "NOM-PLT-L4", len(angles)
    else:
        angles, ply, material = (0.0,), 1.0, isotropic(E_ISOTROPIC, 0.0)
        EA, EI = E_ISOTROPIC * b * ply, E_ISOTROPIC * b * ply**3 / 12
        what, designation, layers = "an isotropic strip with nu = 0", "NOM-PLT-L3", 1
    thickness = ply * len(angles)
    force = ALPHA * EI / L**2
    station_y = L / 2 - L / STRIP["ny"] / 2  # the centroid of the element below mid-length
    body = (f'[[plate.supports]]\nregion = "Edge-Bottom"\ndofs = [1, 2, 3, 4, 5, 6]\n\n[[plate.loads]]\nregion = "Edge-Top"\ndof = 3\ntotal = {number(force)}\n\n'
            f'[plate.probes]\nnodes = {{ tip = [{b / 2!r}, {L!r}] }}\nelements = {{ mid = [{b / 4!r}, {station_y!r}] }}\n')
    plate = plate_table(designation, f"{what} clamped at one end and bent far by a force at the other", "the elastica",
                        {"length": L, "width": b, "nx": STRIP["nx"], "ny": STRIP["ny"]}, (angles, ply), material, body)
    tips = [tip(ALPHA * f) for f in FRACTIONS]
    low, high = gauss_height(thickness, layers, 1, False), gauss_height(thickness, layers, layers, True)
    stations = [station(ALPHA * f, station_y / L) for f in FRACTIONS]  # the angle turned and the curvature times L, below mid-length
    middle = [force * f * math.sin(theta) / EA - 1.5 * EI * (kappa / L) ** 2 / EA for f, (theta, kappa) in zip(FRACTIONS, stations)]
    strains = {z: [line_strain(kappa / L, z, e0) for e0, (_, kappa) in zip(middle, stations)] for z in (low, high)}
    stiffness = (f"EI = b / d = {EI:.8g} N mm^2, with d the entry along the strip of the inverse of the laminate's D, by plain laminate theory "
                 f"(E1 = {material['E1']:g}, E2 = {material['E2']:g}, G12 = {material['G12']:g} MPa, nu12 = {material['nu12']:g}, plies of {ply:g} mm; a round "
                 "carbon ply of our own)") if laminate else f"EI = E b h^3 / 12 = {EI:.8g} N mm^2 (E = {E_ISOTROPIC:g} MPa, nu = 0 so the strip is a beam)"
    source = (f"The elastica, worked without the package by fea/tools/large_deflection_closed_forms.py: a strip {L:g} mm long, {b:g} mm wide and "
              f"{thickness:g} mm thick, clamped at y = 0, under a force along +z at its free end that keeps its direction and rises to "
              f"P = {ALPHA:g} EI / L^2 = {force:.8g} N; {stiffness}. theta'' = -alpha cos(theta) with alpha = P L^2 / EI, theta(0) = 0 and theta'(1) = 0 "
              "(Timoshenko and Gere, Theory of Elastic Stability, Section 2.7), integrated by Runge-Kutta and shooting; the tip's deflection and how "
              "far it comes back are the integrals of sin(theta) and 1 - cos(theta). The strain is the Lagrangian strain along the strip, "
              f"((1 + e0 - z kappa)^2 - 1) / 2 with e0 = P sin(theta) / EA - 3 EI kappa^2 / (2 EA) the stretch of the middle (EA = {EA:.8g} N), at the centroid of the element "
              f"below mid-length (y = {station_y:g} mm), at the heights of CalculiX's lowest and highest integration points. The strip is {STRIP['nx']} by {STRIP['ny']} eight-node elements; the trial behind ADR-0142 gave the "
              "differences the tolerances hold.")
    small = "[small_load]\nfactor = 0.001\ntolerance = 1e-4\nkernel_tolerance = 0.001\nreadings = [\"tip deflection over the length\"]\n"
    readings = [
        reading("tip deflection over the length", "displacement", "tip", 3, [w for w, _ in tips], 0.003, scale=1 / L),
        reading("tip displacement along the strip over the length", "displacement", "tip", 2, [-u for _, u in tips], 0.005, scale=1 / L),
        reading("strain along the strip at the lowest points, below mid-length", "strain", "mid", 2, strains[low], 0.003, height=low),
        reading("strain along the strip at the highest points, below mid-length", "strain", "mid", 2, strains[high], 0.003, height=high),
    ]
    name = "cantilever-cross-ply-bent-far-elastica" if laminate else "cantilever-isotropic-bent-far-elastica"
    title = (f"{what[0].upper()}{what[1:]}, clamped and bent by an end force until its tip stands at 0.81 of its length: CalculiX's large-displacement "
             "answer follows the elastica")
    return name, case_text(title, source, 0.02, FRACTIONS, small, readings, plate)


def stretched_case(laminate: bool) -> tuple[str, str]:
    L, b, pull = STRETCHED["length"], STRETCHED["width"], STRETCHED["pull"]
    if laminate:
        angles, ply, material = CROSS_PLY, PLY_THICKNESS, PLY
        EA = b * laminate_strip(angles, ply, material)[0]
        what, designation = "a [0/90]s laminate's strip", "NOM-PLT-L6"
        stiffness = (f"EA = b / a = {EA:.8g} N, with a the entry along the strip of the inverse of the laminate's A, by plain laminate theory (the ply of the "
                     "bent cross-ply case)")
    else:
        angles, ply, material = (0.0,), 1.0, isotropic(E_ISOTROPIC, 0.3)
        EA = E_ISOTROPIC * b * ply
        what, designation = "an isotropic strip", "NOM-PLT-L5"
        stiffness = f"EA = E b h = {EA:.8g} N (E = {E_ISOTROPIC:g} MPa, nu = 0.3)"
    body = (f'[[plate.supports]]\nregion = "Edge-Bottom"\ndofs = [2, 3]\n[[plate.supports]]\nregion = "Edge-Top"\ndofs = [3]\n[[plate.supports]]\n'
            f'region = "Edge-Top"\ndofs = [2]\nvalue = {pull!r}\n[[plate.supports]]\nregion = "Corner-Origin"\ndofs = [1]\n\n'
            '[[plate.regions]]\nname = "Corner-Origin"\nx0 = 0.0\nx1 = 0.1\ny0 = 0.0\ny1 = 0.1\n')
    plate = plate_table(designation, f"{what} stretched 3 % with its sides free", "the stretch rule",
                        {"length": L, "width": b, "nx": STRETCHED["nx"], "ny": STRETCHED["ny"]}, (angles, ply), material, body)
    e = pull / L
    forces = [EA * e * f * stretch_rule(e * f) for f in (0.5, 1.0)]
    source = (f"The stretch rule, worked without the package by fea/tools/large_deflection_closed_forms.py: a strip {L:g} mm long and {b:g} mm wide, "
              f"its ends moved {pull:g} mm apart (e = {e:g}), its sides free to narrow; {stiffness}. CalculiX relates the second Piola-Kirchhoff "
              "stress to the Lagrangian strain by the small-strain constants (its manual, *ELASTIC), so the force on an end is "
              f"EA e (1 + e / 2)(1 + e): {stretch_rule(e):.6g} times the small-strain law's {EA * e:.8g} N at the whole pull, exactly and whatever "
              "the Poisson's ratio. The state is uniform, so the mesh does not matter; the tolerance holds what CalculiX's layered bricks add at a "
              "laminate's free sides, 1.5 parts in 100,000 of the force with or without the shape followed. Other programs use other "
              "rules at such strains (ADR-0142): the case holds CalculiX to the rule it documents, and says nothing of which rule a material follows.")
    small = "[small_load]\nfactor = 0.001\ntolerance = 1e-4\nkernel_tolerance = 1e-6\n"
    readings = [reading("force on the moved end", "reaction", "Edge-Top", 2, forces, 1e-4)]
    name = "strip-cross-ply-stretched-3-percent-stretch-rule" if laminate else "strip-isotropic-stretched-3-percent-stretch-rule"
    title = f"{what[0].upper()}{what[1:]} stretched 3 %: CalculiX's force is the small-strain law's times (1 + e)(1 + e / 2)"
    return name, case_text(title, source, 0.25, (0.5, 1.0), small, readings, plate)


def build_cases() -> dict[str, str]:
    return dict([levy_case(), cantilever_case(False), cantilever_case(True), stretched_case(False), stretched_case(True)])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="rewrite the cases")
    args = parser.parse_args()
    for name, text in build_cases().items():
        path = paths.LARGE_CASES / f"{name}.toml"
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        state = "written" if args.write else ("as committed" if path.is_file() and path.read_text(encoding="utf-8") == text else "DIFFERS from the committed file")
        print(f"{name}: {state}")
    for alpha in (1.0, 2.0, 5.0, 10.0):
        w, u = tip(alpha)
        print(f"elastica, alpha = {alpha:g}: tip deflection {w:.5f} L, shortening {u:.5f} L")
    EA, EI = laminate_strip(CROSS_PLY, PLY_THICKNESS, PLY)
    print(f"[0/90]s strip per unit width: 1/a = {EA:.6f} N/mm, 1/d = {EI:.6f} N mm")
    print(f"stretch rule at 3 %: {stretch_rule(0.03):.6f}")


if __name__ == "__main__":
    main()
