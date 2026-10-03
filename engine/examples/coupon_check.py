"""Try the engine on a tension coupon. Change the inputs below, then run:

    cd engine
    uv run python examples/coupon_check.py
"""

from anisotropy_engine.engineering import engineering_constants
from anisotropy_engine.failure import first_ply_failure, margin_of_safety
from anisotropy_engine.lamina import Lamina, Strengths
from anisotropy_engine.laminate import Ply
from anisotropy_engine.response import Loads

# ------------------------------------------------------------------ inputs
# Material: AS4/3501-6, Daniel & Ishai Table A.4 (p. 377). Moduli in GPa, strengths in MPa.
E1, E2, G12, NU12 = 147.0, 10.3, 7.0, 0.27
F1T, F1C, F2T, F2C, F6 = 2280.0, 1725.0, 57.0, 228.0, 76.0

# Layup from the bottom face up, angles in degrees.
HALF = [45, -45, 0, 90] * 2
LAYUP = HALF + HALF[::-1]  # [45/-45/0/90]2s
PLY_THICKNESS_MM = 0.13

# Coupon and test.
WIDTH_MM = 25.0
LOAD_KN = 20.0  # tension along the coupon; negative for compression
FACTOR_OF_SAFETY = 1.5
CRITERION = "max_stress"  # or "tsai_wu"
F12_STAR = -0.5  # Tsai-Wu interaction term, used only with "tsai_wu"
# --------------------------------------------------------------------------

material = Lamina(
    E1=E1 * 1e9, E2=E2 * 1e9, G12=G12 * 1e9, nu12=NU12,
    strengths=Strengths(F1t=F1T * 1e6, F1c=F1C * 1e6, F2t=F2T * 1e6, F2c=F2C * 1e6, F6=F6 * 1e6),
)
plies = [Ply(material=material, angle_deg=angle, thickness_m=PLY_THICKNESS_MM / 1000) for angle in LAYUP]
loads = Loads(Nx=LOAD_KN * 1e3 / (WIDTH_MM / 1000))  # Nx = P / w, in N/m
thickness_mm = PLY_THICKNESS_MM * len(LAYUP)
average_stress_mpa = LOAD_KN * 1e3 / (WIDTH_MM * thickness_mm)

print(f"Layup: {LAYUP}")
print(f"{len(LAYUP)} plies, {thickness_mm:.2f} mm thick, {WIDTH_MM:g} mm wide, loaded to {LOAD_KN:g} kN")

constants = engineering_constants(plies)
print("\nLaminate stiffness (what a D3039 test measures)")
print(f"  Ex  = {constants.Ex / 1e9:7.2f} GPa      Ey = {constants.Ey / 1e9:7.2f} GPa")
print(f"  Gxy = {constants.Gxy / 1e9:7.2f} GPa   nu_xy = {constants.nu_xy:7.3f}")
print(f"  Average stress {average_stress_mpa:.1f} MPa -> predicted axial strain "
      f"{average_stress_mpa * 1e6 / constants.Ex * 1e6:.0f} microstrain")

result = first_ply_failure(plies, loads, CRITERION, F12_STAR if CRITERION == "tsai_wu" else None)
print(f"\nPly stresses at {LOAD_KN:g} kN, fiber axes (worse face of each ply)")
print("  ply  angle   sigma1   sigma2    tau12  (MPa)   strength ratio  limit")
for k in range(len(plies)):
    check = min((c for c in result.checks if c.ply_index == k), key=lambda c: c.strength_ratio)
    s1, s2, t12 = check.stress_12 / 1e6
    print(f"  {k + 1:3d}  {check.angle_deg:5g}  {s1:7.1f}  {s2:7.1f}  {t12:7.1f}          {check.strength_ratio:6.2f}    {check.mode}")

governing = result.governing
failure_load_kn = result.failure_loads.Nx * (WIDTH_MM / 1000) / 1e3
margin = margin_of_safety(result.strength_ratio, FACTOR_OF_SAFETY)
print(f"\nFirst-ply failure ({CRITERION})")
print(f"  Strength ratio R = {result.strength_ratio:.3f}")
print(f"  First ply cracks at {failure_load_kn:.2f} kN: ply {governing.ply_index + 1} "
      f"({governing.angle_deg:g} deg), {governing.mode}")
print(f"  Margin of safety at FS = {FACTOR_OF_SAFETY:g}: {margin:+.3f} -> {'PASS' if margin >= 0 else 'FAIL'}")
print("  This is the onset of ply cracking, not the coupon's ultimate strength.")
