"""Laminate calculator for checking hand or homework answers:

    cd engine
    uv run python examples/laminate_calculator.py
    uv run python examples/laminate_calculator.py validation/cases/as4-zero-degree-axial-check.toml
    uv run python examples/laminate_calculator.py path/to/course-input.xlsx

Reads a TOML case or a course Excel input file. Prints Q, Q-bar, ply positions, A, B, D,
mid-plane strains and curvatures, ply strains and stresses in laminate and fiber axes,
laminate engineering constants and, when strengths are given, strength ratios and
first-ply failure. When the case gives a temperature change delta_T (with alpha1 and
alpha2), it also prints the thermal force and moment resultants and the free thermal
strains, and ply stresses include the residual thermal stress. When the case has
[expected] answers, it ends by comparing them with the engine.
"""

import argparse
from pathlib import Path

import numpy as np

from anisotropy_engine.cases import compare, load_case, solve_case
from anisotropy_engine.engineering import engineering_constants
from anisotropy_engine.failure import first_ply_failure, max_stress_ratio, tsai_wu_ratio
from anisotropy_engine.lamina import reduced_stiffness
from anisotropy_engine.laminate import abd_matrices, ply_interfaces
from anisotropy_engine.rotation import transformed_reduced_stiffness
from anisotropy_engine.thermal import thermal_expansion_xy
from anisotropy_engine.units import UNIT_SYSTEMS

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("case", nargs="?", type=Path,
                    default=Path(__file__).parents[1] / "validation/cases/daniel-ishai-problem-7-11.toml")
parser.add_argument("--allow-unusual-moduli", action="store_true",
                    help="Continue after explicitly reviewing moduli outside the calculator's plausibility screen")
args = parser.parse_args()
try:
    case = load_case(args.case)
except (ValueError, OSError) as error:
    parser.error(str(error))
UNITS = case["units"]
U = UNIT_SYSTEMS[UNITS]
ONE_MATERIAL = "material" in case
TABLES = {"material": case["material"]} if ONE_MATERIAL else case["materials"]
F12_STAR = case.get("f12_star")  # No unrecorded assumption for Tsai-Wu.


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


def named(text, name):
    """Add the material name to a heading only when the laminate has several materials."""
    return text if ONE_MATERIAL else f"{text}, material {name}"


for name, table in TABLES.items():
    for key in ("E1", "E2", "G12"):
        value = table[key] * U["modulus"][0]
        # This is an input-error screen inherited from the example, not a material validity criterion.
        if not 0.5e9 <= value <= 1000e9:
            message = (f"{named(key, name)} = {value / 1e9:.4g} GPa is outside the calculator's 0.5-1000 GPa "
                       f'plausibility screen. Check units = "{UNITS}": enter moduli in {U["modulus"][1]}.')
            if not args.allow_unusual_moduli:
                parser.error(message + " Use --allow-unusual-moduli only after reviewing the input.")
            print("WARNING: " + message)

try:
    solution = solve_case(case)
except (ValueError, np.linalg.LinAlgError) as error:
    parser.error(str(error))
plies = solution.plies
used = list(dict.fromkeys(solution.ply_materials))
dT = solution.delta_T

print(f"Case: {args.case.name}")
if case.get("title"):
    print(f"Title: {case['title']}")
print(f"Units: {UNITS}. Moduli: {U['modulus'][1]}; stress: {U['stress'][1]}; thickness: {U['length'][1]}.")
if ONE_MATERIAL:
    print(f"Layup (bottom face first): {case['laminate']['layup']}")
else:
    print(f"Plies, bottom face first: angle, material, thickness [{U['length'][1]}]")
    for number, ply in enumerate(case["laminate"]["plies"], 1):
        print(f"   ply {number:2d} {ply['angle']:6g} deg   material {ply['material']:<8} {ply['thickness']:g}")
for name in used:
    material = solution.materials[name]
    prefix = "" if ONE_MATERIAL else f"Material {name}: "
    print(f"{prefix}nu21 = {material.nu21:.6g}")
    if "alpha1" in TABLES[name]:
        print(f"{prefix}alpha1 = {TABLES[name]['alpha1']:.6g}, alpha2 = {TABLES[name]['alpha2']:.6g}  [{U['alpha'][1]}]")
if dT is None:
    print("Temperature change: none given, so this is a mechanical-load analysis without thermal stresses.")
else:
    print(f"Temperature change delta_T = {case['applied']['delta_T']:g} {U['delta_T'][1]}")
for name in used:
    print_matrix(named("Q, fiber axes", name), reduced_stiffness(solution.materials[name]), "modulus")
combinations = list(dict.fromkeys((ply.angle_deg, name) for ply, name in zip(plies, solution.ply_materials)))
for angle, name in combinations:
    print_matrix(named(f"Q-bar at {angle:g} deg", name),
                 transformed_reduced_stiffness(solution.materials[name], angle), "modulus")

z = ply_interfaces(plies)
print(f"\nPly interfaces z, bottom to top  [{U['length'][1]}]")
print("   " + "".join(f"{v:12.6g}" for v in show(z, "length")))

A, B, D = abd_matrices(plies)
print_matrix("A", A, "A")
print_matrix("B", B, "B")
print_matrix("D", D, "D")
h = z[-1] - z[0]

if dT is not None:
    print(f"\nThermal expansion of each ply angle [{U['alpha'][1]}]: alpha_x, alpha_y, alpha_xy"
          "  |  free thermal strain alpha * delta_T")
    for angle, name in combinations:
        alpha_xy = thermal_expansion_xy(solution.materials[name], angle)
        label = f"{angle:6g} deg" + ("" if ONE_MATERIAL else f" ({name})")
        print(f"   {label}  " + "".join(f"{v:12.4e}" for v in tidy(show(alpha_xy, "alpha")))
              + "  |" + "".join(f"{v:12.4e}" for v in tidy(alpha_xy * dT)))
    print(f"Thermal forces N_T  [{U['N'][1]}]:   " + "".join(f"{v:14.6g}" for v in show(solution.N_T, "N")))
    print(f"Thermal moments M_T  [{U['M'][1]}]: " + "".join(f"{v:14.6g}" for v in show(solution.M_T, "M")))

if solution.constrained is not None:
    print("\nPrescribed curvature: required applied moments calculated; forward verification passed.")
    print(f"Recovered curvature [{U['kappa'][1]}]: {show(solution.constrained.verification.recovered_curvature, 'kappa')}")

loads = solution.loads
eps0, kappa = solution.eps0, solution.kappa
print(f"\nMechanical loads N  [{U['N'][1]}]:      " + "".join(f"{v:14.6g}" for v in show(loads.as_vector()[:3], "N")))
print(f"Average stress N/h  [{U['stress'][1]}]: " + "".join(f"{v:14.6g}" for v in show(loads.as_vector()[:3] / h, "stress")))
print(f"Moments M  [{U['M'][1]}]:  " + "".join(f"{v:14.6g}" for v in show(loads.as_vector()[3:], "M")))
print("Mid-plane strains eps0:   " + "".join(f"{v:14.6e}" for v in tidy(eps0)))
print(f"Curvatures kappa  [{U['kappa'][1]}]: " + "".join(f"{v:14.6e}" for v in show(kappa, "kappa")))

surfaces = solution.surfaces
print("\nPly strains (total)   global x-y: eps_x, eps_y, gamma_xy   |   local 1-2: eps_1, eps_2, gamma_12")
for s in surfaces:
    face = "bottom" if s.z_m == z[s.ply_index] else "top"
    print(f"   ply {s.ply_index + 1:2d} {s.angle_deg:6g} deg {face:>6}  "
          + "".join(f"{v:12.4e}" for v in tidy(s.strain_xy)) + "  |" + "".join(f"{v:12.4e}" for v in tidy(s.strain_12)))
if dT is not None:
    print("\nPly stresses come from mechanical strain: total strain minus the ply's free thermal strain.")
print(f"\nPly stresses  global x-y: sigma_x, sigma_y, tau_xy   |   local 1-2: sigma_1, sigma_2, tau_12  [{U['stress'][1]}]")
for s in surfaces:
    face = "bottom" if s.z_m == z[s.ply_index] else "top"
    print(f"   ply {s.ply_index + 1:2d} {s.angle_deg:6g} deg {face:>6}  "
          + "".join(f"{v:12.5g}" for v in show(s.stress_xy, "stress")) + "  |"
          + "".join(f"{v:12.5g}" for v in show(s.stress_12, "stress")))

c = engineering_constants(plies)
print(f"\nLaminate engineering constants  [{U['modulus'][1]}]")
print(f"   Ex = {show(c.Ex, 'modulus'):.6g}   Ey = {show(c.Ey, 'modulus'):.6g}   Gxy = {show(c.Gxy, 'modulus'):.6g}")
eta_xs, eta_ys = (0.0 if abs(v) < 1e-12 else v for v in (c.eta_xs, c.eta_ys))
print(f"   nu_xy = {c.nu_xy:.6g}   nu_yx = {c.nu_yx:.6g}   eta_xs = {eta_xs:.6g}   eta_ys = {eta_ys:.6g}")

with_strengths = [ply.material.strengths is not None for ply in plies]
if not any(with_strengths):
    print("\nNo strengths given, so failure checks are skipped.")
elif not all(with_strengths):
    print("\nNot every material has strengths, so failure checks are skipped.")
elif dT is not None:
    print("\nFailure checks are skipped: strength ratios with residual thermal stresses are not implemented yet.")
elif not np.any(loads.as_vector()):
    print("\nNothing is applied, so failure checks are skipped.")
else:
    if solution.constrained is not None:
        print("\nFailure ratios below scale solved N and M together; they do not hold a nonzero curvature fixed.")
    print("\nMaximum-stress strength ratios on each ply face")
    if F12_STAR is None:
        print("Tsai-Wu skipped: the case does not supply f12_star.")
    else:
        print(f"Tsai-Wu also evaluated with explicit f12* = {F12_STAR:g}.")
    for s in surfaces:
        face = "bottom" if s.z_m == z[s.ply_index] else "top"
        strengths = plies[s.ply_index].material.strengths
        assert strengths is not None  # every ply has strengths in this branch
        ratio, mode = max_stress_ratio(s.stress_12, strengths)
        tw = f"   Tsai-Wu {tsai_wu_ratio(s.stress_12, strengths, F12_STAR):9.4g}" if F12_STAR is not None else ""
        print(f"   ply {s.ply_index + 1:2d} {s.angle_deg:6g} deg {face:>6}   max stress {ratio:9.4g} ({mode})" + tw)
    for criterion in (("max_stress", "tsai_wu") if F12_STAR is not None else ("max_stress",)):
        fpf = first_ply_failure(plies, loads, criterion, F12_STAR)
        g = fpf.governing
        print(f"\nFirst-ply failure, {criterion}: R = {fpf.strength_ratio:.6g}, ply {g.ply_index + 1} "
              f"({g.angle_deg:g} deg), {g.mode}")
        print(f"   Loads at failure N [{U['N'][1]}]: " + "".join(f"{v:14.6g}" for v in show(fpf.failure_loads.as_vector()[:3], "N")))
        print(f"   Moments at failure M [{U['M'][1]}]: " + "".join(f"{v:14.6g}" for v in show(fpf.failure_loads.as_vector()[3:], "M")))

if "expected" in case:
    comparisons, problems = compare(case)
    tolerance = case["expected"]["tolerance"]
    print(f"\nAnswer key vs engine, in the case's units (relative tolerance {100 * tolerance:g}%)")
    print(f"   {'result':<30}{'answer key':>14}{'engine':>14}{'difference':>12}")
    for comparison in comparisons:
        difference = abs(comparison.engine - comparison.expected)
        shown_difference = (f"{100 * difference / abs(comparison.expected):.3f}%" if comparison.expected
                            else f"{difference:.2g}")
        verdict = "agrees" if comparison.agrees else "DIFFERS"
        print(f"   {comparison.key:<30}{comparison.expected:>14.6g}{comparison.engine:>14.6g}"
              f"{shown_difference:>12}  {verdict}")
    for problem in problems:
        print(f"   CANNOT CHECK {problem}")
    agreeing = sum(comparison.agrees for comparison in comparisons)
    print(f"   {agreeing} of {len(comparisons)} values agree with the answer key"
          + (f"; {len(problems)} expected entries could not be checked." if problems else "."))
