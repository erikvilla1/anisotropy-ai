"""Laminate calculator for checking hand or homework answers. Edit the inputs, then run:

    cd engine
    uv run python examples/laminate_calculator.py

Prints Q, Q-bar, ply positions, A, B, D, mid-plane strains and curvatures, ply strains
and stresses in laminate and fiber axes, laminate engineering constants and, when
strengths are given, strength ratios and first-ply failure.
"""

import numpy as np

from anisotropy_engine.engineering import engineering_constants
from anisotropy_engine.failure import first_ply_failure, max_stress_ratio, tsai_wu_ratio
from anisotropy_engine.lamina import Lamina, Strengths, reduced_stiffness
from anisotropy_engine.laminate import Ply, abd_matrices, ply_interfaces
from anisotropy_engine.response import Loads, abd_matrix, midplane_response, ply_surfaces
from anisotropy_engine.rotation import strain_transformation, stress_transformation, transformed_reduced_stiffness
from anisotropy_engine.units import UNIT_SYSTEMS

# ------------------------------------------------------------------ inputs
UNITS = "SI"  # "SI": GPa, MPa, mm, N/m, N*m/m   "US": Msi, ksi, in, lb/in, lb*in/in   "psi": psi, in, lb/in, lb*in/in

# Ply material. Default: Daniel & Ishai Problem 7.11 (printed A11 = 60.24 MN/m).
E1, E2, G12, NU12 = 145.0, 10.5, 7.0, 0.28
STRENGTHS = None  # (F1t, F1c, F2t, F2c, F6), compressive as positive, e.g. (2280, 1725, 57, 228, 76)

# Layup listed from the bottom face up, angles in degrees, counterclockwise from x to the fibers.
LAYUP = [0, 45, -45]
PLY_THICKNESS = 0.25  # mm (SI) or in (US, psi), the same for every ply

# Choose what the problem gives you, then fill in the matching line below.
#   "loads"         N and M (force and moment per width)
#   "stress"        global stresses sigma_x, sigma_y, tau_xy, averaged through the thickness
#   "strains"       global mid-plane strains EPS0 and curvatures KAPPA
#   "local stress"  sigma_1, sigma_2, tau_12 in the fiber axes (layup must use a single angle)
#   "local strain"  eps_1, eps_2, gamma_12 in the fiber axes (layup must use a single angle)
APPLIED = "loads"
N = (100e3, 0.0, 0.0)  # Nx, Ny, Nxy: N/m (SI) or lb/in (US)
M = (0.0, 0.0, 0.0)  # Mx, My, Mxy: N*m/m (SI) or lb*in/in (US)
EPS0 = (1e-3, 0.0, 0.0)  # eps_x, eps_y, gamma_xy (engineering shear), when APPLIED = "strains"
KAPPA = (0.0, 0.0, 0.0)  # kappa_x, kappa_y, kappa_xy: 1/m (SI) or 1/in (US)
STRESS = (0.0, 0.0, 0.0)  # sigma_x, sigma_y, tau_xy averaged through the thickness, when APPLIED = "stress"
LOCAL_STRESS = (0.0, 0.0, 0.0)  # sigma_1, sigma_2, tau_12, when APPLIED = "local stress"
LOCAL_STRAIN = (0.0, 0.0, 0.0)  # eps_1, eps_2, gamma_12 (engineering shear), when APPLIED = "local strain"

F12_STAR = -0.5  # Tsai-Wu interaction term, used only when strengths are given
# --------------------------------------------------------------------------

UNIT_SETS = UNIT_SYSTEMS
APPLIED_OPTIONS = ("loads", "stress", "strains", "local stress", "local strain")
if UNITS not in UNIT_SETS or APPLIED not in APPLIED_OPTIONS:
    raise SystemExit(f'Set UNITS to "SI", "US" or "psi", and APPLIED to one of {APPLIED_OPTIONS}.')
if APPLIED.startswith("local") and len(set(LAYUP)) != 1:
    raise SystemExit("Local 1-2 values belong to one fiber direction. Use a layup with a single angle, "
                     "or give global values instead.")
U = UNIT_SETS[UNITS]


def to_si(value, kind):
    return np.asarray(value, dtype=float) * U[kind][0]


def tidy(values):
    """Print rounding noise such as 1e-17 as 0. Display only; calculations are unchanged."""
    values = np.array(values, dtype=float)
    scale = np.abs(values).max(initial=0.0)
    values[np.abs(values) <= 1e-9 * scale] = 0.0
    return values + 0.0  # turns -0.0 into 0.0


def show(value_si, kind):
    return tidy(np.asarray(value_si) / U[kind][0])


def print_matrix(title, matrix_si, kind):
    print(f"\n{title}  [{U[kind][1]}]")
    for row in show(matrix_si, kind):
        print("   " + "".join(f"{v:14.6g}" for v in row))


strengths = None
if STRENGTHS is not None:
    f1t, f1c, f2t, f2c, f6 = to_si(STRENGTHS, "stress")
    strengths = Strengths(F1t=f1t, F1c=f1c, F2t=f2t, F2c=f2c, F6=f6)
e1, e2, g12 = to_si((E1, E2, G12), "modulus")
material = Lamina(E1=e1, E2=e2, G12=g12, nu12=NU12, strengths=strengths)
for name, value in (("E1", e1), ("E2", e2), ("G12", g12)):
    # Real fiber composites and their resins sit between about 0.5 and 1000 GPa.
    if not 0.5e9 <= value <= 1000e9:
        print(f"WARNING: {name} = {value / 1e9:.4g} GPa is outside the range of real materials. "
              f'Check that UNITS = "{UNITS}" matches the numbers you typed.')
plies = [Ply(material=material, angle_deg=a, thickness_m=float(to_si(PLY_THICKNESS, "length"))) for a in LAYUP]

print(f"Units: {UNITS}.  Layup (bottom face first): {LAYUP}")
print(f"nu21 = {material.nu21:.6g}")
print_matrix("Q, fiber axes", reduced_stiffness(material), "modulus")
for angle in dict.fromkeys(LAYUP):
    print_matrix(f"Q-bar at {angle:g} deg", transformed_reduced_stiffness(material, angle), "modulus")

z = ply_interfaces(plies)
print(f"\nPly interfaces z, bottom to top  [{U['length'][1]}]")
print("   " + "".join(f"{v:12.6g}" for v in show(z, "length")))

A, B, D = abd_matrices(plies)
print_matrix("A", A, "A")
print_matrix("B", B, "B")
print_matrix("D", D, "D")

h = z[-1] - z[0]
LOAD_NAMES = ["Nx", "Ny", "Nxy", "Mx", "My", "Mxy"]
if APPLIED in ("loads", "stress", "local stress"):
    if APPLIED == "loads":
        n, m = to_si(N, "N"), to_si(M, "M")
    else:
        stress = to_si(STRESS if APPLIED == "stress" else LOCAL_STRESS, "stress")
        if APPLIED == "local stress":
            stress = stress_transformation(-LAYUP[0]) @ stress  # rotating back by -theta: local to global
        n, m = stress * h, np.zeros(3)  # an average stress over h is a force per width N = sigma * h
    loads = Loads(**dict(zip(LOAD_NAMES, np.concatenate([n, m]))))
    eps0, kappa = midplane_response(plies, loads)
else:
    if APPLIED == "strains":
        eps0, kappa = np.asarray(EPS0, dtype=float), to_si(KAPPA, "kappa")
    else:
        eps0 = strain_transformation(-LAYUP[0]) @ np.asarray(LOCAL_STRAIN, dtype=float)  # local to global
        kappa = np.zeros(3)
    loads = Loads(**dict(zip(LOAD_NAMES, abd_matrix(plies) @ np.concatenate([eps0, kappa]))))

print(f"\nLoads N  [{U['N'][1]}]:      " + "".join(f"{v:14.6g}" for v in show(loads.as_vector()[:3], "N")))
print(f"Average stress N/h  [{U['stress'][1]}]: " + "".join(f"{v:14.6g}" for v in show(loads.as_vector()[:3] / h, "stress")))
print(f"Moments M  [{U['M'][1]}]:  " + "".join(f"{v:14.6g}" for v in show(loads.as_vector()[3:], "M")))
print("Mid-plane strains eps0:   " + "".join(f"{v:14.6e}" for v in tidy(eps0)))
print(f"Curvatures kappa  [{U['kappa'][1]}]: " + "".join(f"{v:14.6e}" for v in show(kappa, "kappa")))

surfaces = ply_surfaces(plies, eps0, kappa)
print("\nPly strains   global x-y: eps_x, eps_y, gamma_xy   |   local 1-2: eps_1, eps_2, gamma_12")
for s in surfaces:
    face = "bottom" if s.z_m == z[s.ply_index] else "top"
    print(f"   ply {s.ply_index + 1:2d} {s.angle_deg:6g} deg {face:>6}  "
          + "".join(f"{v:12.4e}" for v in tidy(s.strain_xy)) + "  |" + "".join(f"{v:12.4e}" for v in tidy(s.strain_12)))
print(f"\nPly stresses  global x-y: sigma_x, sigma_y, tau_xy   |   local 1-2: sigma_1, sigma_2, tau_12  [{U['stress'][1]}]")
for s in surfaces:
    face = "bottom" if s.z_m == z[s.ply_index] else "top"
    print(f"   ply {s.ply_index + 1:2d} {s.angle_deg:6g} deg {face:>6}  "
          + "".join(f"{v:11.5g}" for v in show(s.stress_xy, "stress")) + "  |"
          + "".join(f"{v:11.5g}" for v in show(s.stress_12, "stress")))

c = engineering_constants(plies)
print(f"\nLaminate engineering constants  [{U['modulus'][1]}]")
print(f"   Ex = {show(c.Ex, 'modulus'):.6g}   Ey = {show(c.Ey, 'modulus'):.6g}   Gxy = {show(c.Gxy, 'modulus'):.6g}")
eta_xs, eta_ys = (0.0 if abs(v) < 1e-12 else v for v in (c.eta_xs, c.eta_ys))
print(f"   nu_xy = {c.nu_xy:.6g}   nu_yx = {c.nu_yx:.6g}   eta_xs = {eta_xs:.6g}   eta_ys = {eta_ys:.6g}")

if strengths is None:
    print("\nNo strengths given, so failure checks are skipped.")
elif not np.any(loads.as_vector()):
    print("\nNothing is applied, so failure checks are skipped.")
else:
    print(f"\nStrength ratios on each ply face (Tsai-Wu with f12* = {F12_STAR:g})")
    for s in surfaces:
        face = "bottom" if s.z_m == z[s.ply_index] else "top"
        ratio, mode = max_stress_ratio(s.stress_12, strengths)
        print(f"   ply {s.ply_index + 1:2d} {s.angle_deg:6g} deg {face:>6}   max stress {ratio:9.4g} ({mode})"
              f"   Tsai-Wu {tsai_wu_ratio(s.stress_12, strengths, F12_STAR):9.4g}")
    for criterion in ("max_stress", "tsai_wu"):
        fpf = first_ply_failure(plies, loads, criterion, F12_STAR)
        g = fpf.governing
        print(f"\nFirst-ply failure, {criterion}: R = {fpf.strength_ratio:.6g}, ply {g.ply_index + 1} "
              f"({g.angle_deg:g} deg), {g.mode}")
        print(f"   Loads at failure N [{U['N'][1]}]: " + "".join(f"{v:14.6g}" for v in show(fpf.failure_loads.as_vector()[:3], "N")))
        print(f"   Moments at failure M [{U['M'][1]}]: " + "".join(f"{v:14.6g}" for v in show(fpf.failure_loads.as_vector()[3:], "M")))
