"""Closed-form answers for the constructed validation cases, written without the engine (ADR-0007, ADR-0042).

Each case below is symmetric and loaded in its plane, so B = 0, the curvatures vanish and the mid-plane strain is
eps0 = A^-1 (N + N_T). Everything is computed from the textbook formulas the cases' source lines name (Daniel and Ishai
2006: Q, Eq. 4.47; the transformation of Q and of the strains, Eqs. 4.62 and 4.50; thermal resultants, Eqs. 8.16-8.18;
fixed and variable loading, Section 9.8). engine/tests/test_constructed_references.py checks that every number under a
case's [expected] is the one computed here. This file imports nothing from anisotropy_engine.
"""

from __future__ import annotations

import math

import numpy as np

# Case units to SI and back: modulus, stress, length, line load (N per width), temperature step
SI = {"modulus": 1e9, "stress": 1e6, "length": 1e-3, "line_load": 1.0, "A": 1e6}  # GPa, MPa, mm, N/m, MN/m
PSI = {"modulus": 1.0, "stress": 1.0, "length": 1.0, "line_load": 1.0, "A": 1.0}  # psi, psi, in, lb/in, lb/in: consistent
UNITS = {"SI": SI, "psi": PSI}


def q_on_axis(E1: float, E2: float, G12: float, nu12: float) -> np.ndarray:
    """Reduced stiffness in fiber axes, Eq. 4.47."""
    nu21 = nu12 * E2 / E1
    d = 1.0 - nu12 * nu21
    return np.array([[E1 / d, nu12 * E2 / d, 0.0], [nu12 * E2 / d, E2 / d, 0.0], [0.0, 0.0, G12]])


def q_bar(q: np.ndarray, angle_deg: float) -> np.ndarray:
    """Q in laminate axes, Eq. 4.62, written out term by term with m = cos, n = sin of the fiber angle."""
    m, n = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    q11, q12, q22, q66 = q[0, 0], q[0, 1], q[1, 1], q[2, 2]
    b11 = q11 * m**4 + 2 * (q12 + 2 * q66) * m**2 * n**2 + q22 * n**4
    b22 = q11 * n**4 + 2 * (q12 + 2 * q66) * m**2 * n**2 + q22 * m**4
    b12 = (q11 + q22 - 4 * q66) * m**2 * n**2 + q12 * (m**4 + n**4)
    b66 = (q11 + q22 - 2 * q12 - 2 * q66) * m**2 * n**2 + q66 * (m**4 + n**4)
    b16 = (q11 - q12 - 2 * q66) * m**3 * n + (q12 - q22 + 2 * q66) * m * n**3
    b26 = (q11 - q12 - 2 * q66) * m * n**3 + (q12 - q22 + 2 * q66) * m**3 * n
    return np.array([[b11, b12, b16], [b12, b22, b26], [b16, b26, b66]])


def to_fiber_axes(strain_xy: np.ndarray, angle_deg: float) -> np.ndarray:
    """Engineering strain (eps_x, eps_y, gamma_xy) in fiber axes, Eq. 4.50."""
    m, n = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    ex, ey, gxy = strain_xy
    return np.array([ex * m**2 + ey * n**2 + gxy * m * n,
                     ex * n**2 + ey * m**2 - gxy * m * n,
                     2 * (ey - ex) * m * n + gxy * (m**2 - n**2)])


def alpha_xy(alpha1: float, alpha2: float, angle_deg: float) -> np.ndarray:
    """Free thermal expansion in laminate axes, engineering shear."""
    m, n = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    return np.array([alpha1 * m**2 + alpha2 * n**2, alpha1 * n**2 + alpha2 * m**2, 2 * (alpha1 - alpha2) * m * n])


def plies_of(case: dict) -> list[dict]:
    """Each ply bottom first, in SI: its Q, alphas, angle and thickness."""
    u = UNITS[case["units"]]

    def material(values):
        q = q_on_axis(*(values[k] * u["modulus"] for k in ("E1", "E2", "G12")), values["nu12"])
        return q, values.get("alpha1", 0.0), values.get("alpha2", 0.0), values

    if "material" in case:
        q, a1, a2, values = material(case["material"])
        t = case["laminate"]["ply_thickness"] * u["length"]
        return [{"q": q, "alpha1": a1, "alpha2": a2, "angle": a, "t": t, "values": values} for a in case["laminate"]["layup"]]
    out = []
    for ply in case["laminate"]["plies"]:
        q, a1, a2, values = material(case["materials"][ply["material"]])
        out.append({"q": q, "alpha1": a1, "alpha2": a2, "angle": ply["angle"], "t": ply["thickness"] * u["length"], "values": values})
    return out


def membrane(plies: list[dict], loads_si: np.ndarray, delta_t: float) -> dict:
    """A, the thermal resultants and the mid-plane strain of a symmetric laminate under in-plane loads; then each ply's
    strain and stress in fiber axes, the stress from the mechanical strain (total strain minus free thermal strain)."""
    a = sum(p["t"] * q_bar(p["q"], p["angle"]) for p in plies)
    n_t = sum(p["t"] * q_bar(p["q"], p["angle"]) @ alpha_xy(p["alpha1"], p["alpha2"], p["angle"]) * delta_t for p in plies)
    eps0 = np.linalg.solve(a, loads_si + n_t)
    strains, stresses = [], []
    for p in plies:
        local = to_fiber_axes(eps0, p["angle"])
        strains.append(local)
        stresses.append(p["q"] @ (local - np.array([p["alpha1"], p["alpha2"], 0.0]) * delta_t))
    return {"A": a, "N_T": n_t, "eps0": eps0, "strain_local": strains, "stress_local": stresses}


def max_stress_ratio(s: np.ndarray, v: np.ndarray, values: dict) -> float:
    """Section 9.8: R per component from sigma_s + R sigma_v reaching its limit; the smallest governs."""
    limits = [(values["F1t"], values["F1c"]), (values["F2t"], values["F2c"]), (values["F6"], values["F6"])]
    ratios = []
    for (tension, compression), fixed, variable in zip(limits, s, v):
        if variable > 0:
            ratios.append((tension - fixed) / variable)
        elif variable < 0:
            ratios.append((-compression - fixed) / variable)
    return min(ratios)


def tsai_wu_ratio(s: np.ndarray, v: np.ndarray, values: dict, f12_star: float) -> float:
    """Tsai-Wu with sigma_s + R sigma_v, Eqs. 9.26-9.27: the positive root of a R^2 + b R + c = 0."""
    f1 = 1 / values["F1t"] - 1 / values["F1c"]
    f2 = 1 / values["F2t"] - 1 / values["F2c"]
    f11, f22, f66 = 1 / (values["F1t"] * values["F1c"]), 1 / (values["F2t"] * values["F2c"]), 1 / values["F6"] ** 2
    f12 = f12_star * math.sqrt(f11 * f22)

    def q(x, y):
        return f11 * x[0] * y[0] + f22 * x[1] * y[1] + f66 * x[2] * y[2] + f12 * (x[0] * y[1] + x[1] * y[0])

    a, b, c = q(v, v), f1 * v[0] + f2 * v[1] + 2 * q(s, v), f1 * s[0] + f2 * s[1] + q(s, s) - 1
    return (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)


# --------------------------------------------------------------------------------------------- the cases

def cross_ply_cooling_first_ply_failure(case: dict) -> dict:
    """Symmetric cross-ply, cooled, with a fixed Ny and a variable Nx: response under [applied], then first-ply failure."""
    u = UNITS[case["units"]]
    plies, dt = plies_of(case), case["applied"]["delta_T"]
    response = membrane(plies, np.array(case["applied"]["loads"][:3], float) * u["line_load"], dt)
    fixed = membrane(plies, np.array(case["failure"]["fixed"][:3], float) * u["line_load"], dt)  # the temperature change stays fixed
    variable = membrane(plies, np.array(case["failure"]["variable"][:3], float) * u["line_load"], 0.0)
    pairs = [(fixed["stress_local"][k] / u["stress"], variable["stress_local"][k] / u["stress"], plies[k]["values"]) for k in range(len(plies))]
    return {
        "N_T": response["N_T"] / u["line_load"],
        "strain_global": response["eps0"],
        "ply_stress_local": {str(k + 1): response["stress_local"][k] / u["stress"] for k in range(len(plies))},
        "fpf_ratio_max_stress": min(max_stress_ratio(s, v, values) for s, v, values in pairs),
        "fpf_ratio_tsai_wu": min(tsai_wu_ratio(s, v, values, case["f12_star"]) for s, v, values in pairs),
    }


def cross_ply_cooling_alone_first_ply_failure(case: dict) -> dict:
    """The same cross-ply cooled with no load at all: every ply's stress is the residual stress of the temperature change, which scales
    with it, so the strength ratio of that stress is the factor on the temperature change at which the first ply fails."""
    u = UNITS[case["units"]]
    plies, dt = plies_of(case), case["applied"]["delta_T"]
    response = membrane(plies, np.zeros(3), dt)
    zero = np.zeros(3)
    pairs = [(zero, response["stress_local"][k] / u["stress"], plies[k]["values"]) for k in range(len(plies))]
    ratio_ms = min(max_stress_ratio(s, v, values) for s, v, values in pairs)
    ratio_tw = min(tsai_wu_ratio(s, v, values, case["f12_star"]) for s, v, values in pairs)
    return {
        "N_T": response["N_T"] / u["line_load"],
        "strain_global": response["eps0"],
        "ply_stress_local": {str(k + 1): response["stress_local"][k] / u["stress"] for k in range(len(plies))},
        "fpf_ratio_max_stress": ratio_ms, "fpf_ratio_tsai_wu": ratio_tw,
        "fpf_delta_T_max_stress": ratio_ms * dt, "fpf_delta_T_tsai_wu": ratio_tw * dt,
    }


def mixed_angle_lamina(case: dict) -> dict:
    """One lamina off axis with sigma_x, eps_y and tau_xy known: rows 1 and 3 of sigma = Q-bar eps give eps_x and gamma_xy,
    row 2 then gives sigma_y."""
    u = UNITS[case["units"]]
    (ply,) = plies_of(case)
    qb = q_bar(ply["q"], ply["angle"])
    known = case["applied"]["mixed"]
    sigma_x, eps_y = known["sigma_x"] * u["stress"], known["eps_y"]
    # sigma_x = Qb11 eps_x + Qb12 eps_y + Qb16 gamma;  0 = Qb16 eps_x + Qb26 eps_y + Qb66 gamma  (tau_xy = 0)
    eps_x, gamma = np.linalg.solve([[qb[0, 0], qb[0, 2]], [qb[0, 2], qb[2, 2]]], [sigma_x - qb[0, 1] * eps_y, -qb[1, 2] * eps_y])
    sigma_y = qb[0, 1] * eps_x + qb[1, 1] * eps_y + qb[1, 2] * gamma
    return {"eps_x": eps_x, "gamma_xy": gamma, "sigma_y": sigma_y / u["stress"],
            "Qbar11": qb[0, 0] / u["modulus"], "Qbar16": qb[0, 2] / u["modulus"], "Qbar66": qb[2, 2] / u["modulus"]}


def two_material_laminate_cooling(case: dict) -> dict:
    """Symmetric 0/90 stack of two materials under Nx, Nxy and cooling."""
    u = UNITS[case["units"]]
    plies = plies_of(case)
    r = membrane(plies, np.array(case["applied"]["loads"][:3], float) * u["line_load"], case["applied"]["delta_T"])
    a = r["A"] / u["A"]
    return {
        "A11": a[0, 0], "A12": a[0, 1], "A22": a[1, 1], "A66": a[2, 2],
        "N_T": r["N_T"] / u["line_load"],
        "strain_global": r["eps0"],
        "ply_strain_local": {str(k + 1): r["strain_local"][k] for k in range(len(plies))},
        "ply_stress_local": {str(k + 1): r["stress_local"][k] / u["stress"] for k in range(len(plies))},
    }


CASES = {
    "constructed-cross-ply-cooling-first-ply-failure": cross_ply_cooling_first_ply_failure,
    "constructed-cross-ply-cooling-alone-first-ply-failure": cross_ply_cooling_alone_first_ply_failure,
    "constructed-mixed-angle-lamina": mixed_angle_lamina,
    "constructed-two-material-laminate-cooling": two_material_laminate_cooling,
}


# ----------------------------------------------------------------------------------------- the wing cases

def straight_sandwich_wing(case: dict) -> dict:
    """A straight two-spar wing with a symmetric NACA airfoil, by hand (ADR-0115): the box between the spars as four
    rectangles, thin-walled beam theory, Schrenk's lift and its exact integrals at the root, and the plies of the skins
    and webs at the root by the maximum stress criterion. SI wing file units: m, mm of ply and core, N, GPa, MPa, kg/m^3,
    speeds in m/s; the answers in the report's units (N, N*m, N/m, N*m^2, kg, GPa, mm of deflection, degrees of twist).

    The NACA thickness formula, the standard atmosphere's constants and the first root of the cantilever's frequency
    equation are written out here again, so nothing is shared with the engine.
    """
    g, m, env = case["geometry"], case["material"], case["envelope"]
    assert case["units"] == "SI" and env["speed_unit"] == "m/s" and env["criterion"] == "max_stress"
    assert g["airfoil"].startswith("naca-00"), "the closed form is for a symmetric airfoil: the centroid is on the chord line"
    L, c, thickness = g["half_span"], g["chord"], int(g["airfoil"][-2:]) / 100

    def height(x):  # the airfoil's full height at chord fraction x
        return 2 * 5 * thickness * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1015 * x**4) * c

    x_f, x_r = g["front_spar"] * c, g["rear_spar"] * c
    h_f, h_r, b = height(g["front_spar"]), height(g["rear_spar"]), x_r - x_f
    q = q_on_axis(m["E1"] * 1e9, m["E2"] * 1e9, m["G12"] * 1e9, m["nu12"])
    strengths = {name: m[name] * 1e6 for name in ("F1t", "F1c", "F2t", "F2c", "F6")}
    t_ply = m["ply_thickness"] * 1e-3

    def laminate(half):  # membrane stiffness, thickness, Ex and Gxy of half + mirrored half
        A = 2 * t_ply * sum(q_bar(q, angle) for angle in half)
        t = 2 * len(half) * t_ply
        a = np.linalg.inv(A)
        return A, t, 1 / (a[0, 0] * t), 1 / (a[2, 2] * t)

    skin_half, web_half = case["skin"]["half_stack"], case["spar"]["half_stack"]
    A_s, t_s, E_s, G_s = laminate(skin_half)
    A_w, t_w, E_w, G_w = laminate(web_half)

    # Skin bending stiffness: each ply of a face by its own z, outside ply first, twice for the two faces.
    core = case["skin"]["core_thickness"] * 1e-3
    outside = core / 2 + len(skin_half) * t_ply
    D = sum(2 * q_bar(q, angle) * ((outside - i * t_ply) ** 3 - (outside - (i + 1) * t_ply) ** 3) / 3 for i, angle in enumerate(skin_half))
    N_cr = 2 * math.pi**2 * (math.sqrt(D[0, 0] * D[1, 1]) + D[0, 1] + 2 * D[2, 2]) / b**2

    z_s = (h_f + h_r) / 4  # the skins sit at the mean of the spar half heights, above and below the chord line
    EI = 2 * E_s * (b * t_s**3 / 12 + b * t_s * z_s**2) + E_w * t_w * (h_f**3 + h_r**3) / 12
    area = b * (h_f + h_r) / 2
    GJ = 4 * area**2 / (2 * b / (G_s * t_s) + (h_f + h_r) / (G_w * t_w))
    share_f, share_r = h_f**2 / (h_f**2 + h_r**2), h_r**2 / (h_f**2 + h_r**2)
    x_sc = share_f * x_f + share_r * x_r
    mass = m["density"] * L * (2 * b * t_s + t_w * (h_f + h_r)) + case["skin"]["core_density"] * 2 * b * core * L
    f1 = 1.8751040687119611**2 / (2 * math.pi) * math.sqrt(EI / (mass / L * L**4))

    # Standard atmosphere and dynamic pressure at the one altitude, for true or equivalent airspeeds.
    (altitude,) = env["altitudes"]
    rho_0 = 101325.0 / (287.05287 * 288.15)
    sigma = (1 - 0.0065 * altitude / 288.15) ** (9.80665 / (287.05287 * 0.0065) - 1)
    true_speed = env["airspeed"] == "true"

    def pressure(speed):
        return 0.5 * rho_0 * (sigma if true_speed else 1.0) * speed**2

    W, cm = env["gross_weight"], case["aerodynamics"]["pitching_moment_coefficient"]
    arm = x_sc - case["aerodynamics"]["aerodynamic_center"] * c
    centroid_arm = L * (1 / 4 + 2 / (3 * math.pi))  # the lift of one side acts here: mean of L/2 (uniform) and 4L/(3 pi) (elliptical)

    def weakest(Nx, Nxy, A, half):  # smallest maximum-stress ratio over the ply angles of a laminate under Nx and Nxy
        eps0 = np.linalg.solve(A, np.array([Nx, 0.0, Nxy]))
        return min(max_stress_ratio(np.zeros(3), q @ to_fiber_axes(eps0, angle), strengths) for angle in half)

    def root(n, speed, delta_cl=0.0, delta_cm=0.0):
        """Loads and checks at the root for a load factor, a speed and an aileron change over its span."""
        qd, side = pressure(speed), n * W / 2
        y1, y2 = (env["aileron"]["span_start"], env["aileron"]["span_end"]) if delta_cl or delta_cm else (0.0, 0.0)
        extra = qd * c * delta_cl
        shear = side + extra * (y2 - y1)
        moment = side * centroid_arm + extra * (y2**2 - y1**2) / 2
        torque = arm * shear + qd * c**2 * cm * L + qd * c**2 * delta_cm * (y2 - y1)
        kappa, flow = moment / EI, torque / (2 * area)
        skins = min(weakest(-kappa * z * E_s * t_s, flow, A_s, skin_half) for z in (z_s, -z_s))
        webs = min(weakest(-kappa * z * E_w * t_w, share * abs(shear) / h + abs(flow), A_w, web_half)
                   for share, h in ((share_f, h_f), (share_r, h_r)) for z in (h / 2, -h / 2))
        return {"dynamic_pressure": qd, "root_shear": shear, "root_moment": moment, "root_torque": torque,
                "skin_plies": skins, "spar_plies": webs, "skin_buckling": N_cr / abs(kappa * z_s * E_s * t_s)}

    speeds, n_pos = env["speeds"], env["positive_load_factor"]
    maneuver = root(n_pos, speeds["positive_maneuver"])
    side = n_pos * W / 2
    peak = 4 * side / (math.pi * L)
    maneuver["load_factor"] = n_pos
    # Tip deflection = (1/EI) * integral of w(s) (L s^2/2 - s^3/6): the elliptical part gives peak L^4 (pi/32 - 1/45),
    # the uniform part (side/L) L^4/8, and Schrenk takes half of each. Tip twist = (1/GJ) * integral of the torque.
    maneuver["tip_deflection"] = 0.5 * (peak * L**4 * (math.pi / 32 - 1 / 45) + side * L**3 / 8) / EI * 1e3
    qd = maneuver["dynamic_pressure"]
    maneuver["tip_twist"] = math.degrees((arm * maneuver["root_moment"] + qd * c**2 * cm * L**2 / 2) / GJ)

    # Gust at cruise, up: n = 1 + K_g rho_0 U_de V_e a / (2 W/S), K_g = 0.88 mu / (5.3 + mu), mu = 2 (W/S) / (rho c a g).
    gust = env["gust"]
    loading, slope = W / gust["wing_area"], gust["lift_curve_slope_per_rad"]
    mu = 2 * loading / (rho_0 * sigma * c * slope * 9.80665)
    equivalent = speeds["cruise"] * (math.sqrt(sigma) if true_speed else 1.0)
    n_gust = 1 + 0.88 * mu / (5.3 + mu) * rho_0 * gust["cruise_gust_speed"] * equivalent * slope / (2 * loading)
    gust_case = root(n_gust, speeds["cruise"])

    aileron = env["aileron"]
    n_roll = aileron["roll_pull_up_fraction"] * n_pos
    roll = root(n_roll, speeds["positive_maneuver"], aileron["down_delta_cl"], aileron["down_delta_cm"])

    return {
        "design": {"bending_stiffness": EI, "torsion_stiffness": GJ, "shear_center": x_sc, "skin_buckling_load": N_cr, "mass": mass,
                   "first_bending_frequency": f1, "skin_modulus": E_s / 1e9, "spar_modulus": E_w / 1e9},
        "cases": {
            "6": maneuver,
            "10": {"load_factor": n_gust, "root_moment": gust_case["root_moment"], "skin_plies": gust_case["skin_plies"]},
            "16": {"load_factor": n_roll, "root_shear": roll["root_shear"], "root_moment": roll["root_moment"],
                   "root_torque": roll["root_torque"], "spar_plies": roll["spar_plies"]},
        },
    }


WING_CASES = {
    "constructed-straight-sandwich-wing": straight_sandwich_wing,
}
