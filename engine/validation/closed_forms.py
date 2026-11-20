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
    """A straight two-spar wing whose airfoil is straight-sided between the spars, by hand (ADR-0115 amendment 3): the box
    between the spars as one closed thin-walled cell of four flat walls at their mid-thickness, symmetric about the chord
    line; its shear flow worked wall by wall in closed form, Bredt-Batho torsion, Schrenk's lift and its exact integrals at
    the root, and every face of every ply of the skins and webs at the root by the maximum stress criterion, along each wall.
    SI wing file units: m, mm of ply and core, N, GPa, MPa, kg/m^3, speeds in m/s; the answers in the report's units (N, N*m,
    N/m, N*m^2, kg, GPa, mm of deflection, degrees of twist).

    The standard atmosphere's constants and the first root of the cantilever's frequency equation are written out here
    again, so nothing is shared with the engine.
    """
    g, m, env = case["geometry"], case["material"], case["envelope"]
    assert case["units"] == "SI" and env["speed_unit"] == "m/s" and env["criterion"] == "max_stress"
    upper, lower = g["airfoil"]["upper"], g["airfoil"]["lower"]
    assert lower == [[x, -z] for x, z in upper], "the closed form is for a section symmetric about the chord line"
    L, c = g["half_span"], g["chord"]
    (x0, z0), (x1, z1) = [p for p in upper if p[0] <= g["front_spar"]][-1], [p for p in upper if p[0] >= g["rear_spar"]][0]
    assert not [p for p in upper if x0 < p[0] < x1], "the upper surface is one straight line from before the front spar to past the rear"
    slope = (z1 - z0) / (x1 - x0)

    q = q_on_axis(m["E1"] * 1e9, m["E2"] * 1e9, m["G12"] * 1e9, m["nu12"])
    strengths = {name: m[name] * 1e6 for name in ("F1t", "F1c", "F2t", "F2c", "F6")}
    t_ply = m["ply_thickness"] * 1e-3

    def laminate(half, core):  # A, thickness of the plies, Ex, Gxy, and D with the core between the halves, of half + mirrored half
        A = 2 * t_ply * sum(q_bar(q, angle) for angle in half)
        t = 2 * len(half) * t_ply
        a = np.linalg.inv(A)
        outside = core / 2 + len(half) * t_ply  # each ply of a face by its own z, outside ply first, twice for the two faces
        D = sum(2 * q_bar(q, angle) * ((outside - i * t_ply) ** 3 - (outside - (i + 1) * t_ply) ** 3) / 3 for i, angle in enumerate(half))
        faces = [(outside - (i + 1) * t_ply, outside - i * t_ply, angle) for i, angle in enumerate(half)]
        return A, t, 1 / (a[0, 0] * t), 1 / (a[2, 2] * t), D, faces

    skin_half, web_half = case["skin"]["half_stack"], case["spar"]["half_stack"]
    core = case["skin"]["core_thickness"] * 1e-3
    A_s, t_s, E_s, G_s, D_s, faces_s = laminate(skin_half, core)
    A_w, t_w, E_w, G_w, D_w, faces_w = laminate(web_half, 0.0)

    # The walls at their mid-thickness: the upper surface moved down by half the skin's thickness along its normal, which is
    # a vertical drop of half * sqrt(1 + slope^2) for a straight surface; the lower surface mirrored.
    half = (2 * len(skin_half) * t_ply + core) / 2
    x_f, x_r = g["front_spar"] * c, g["rear_spar"] * c
    a_f = (z0 + slope * (g["front_spar"] - x0)) * c - half * math.sqrt(1 + slope**2)  # half the front web's height
    a_r = (z0 + slope * (g["rear_spar"] - x0)) * c - half * math.sqrt(1 + slope**2)
    b = x_r - x_f
    l = math.hypot(b, a_f - a_r)  # each skin's width round the section
    Et_s, Et_w, Gt_s, Gt_w = E_s * t_s, E_w * t_w, G_s * t_s, G_w * t_w

    # Symmetric about the chord line: the centroid is on it and the product of inertia is zero, so the lift's moment bends
    # the box about the chord line alone. Skins: z runs linearly from a_r to a_f along l. Webs: heights 2 a.
    EI = 2 * Et_s * l * (a_f**2 + a_f * a_r + a_r**2) / 3 + Et_w * ((2 * a_f) ** 3 + (2 * a_r) ** 3) / 12
    area = b * (a_f + a_r)
    GJ = 4 * area**2 / (2 * l / Gt_s + 2 * (a_f + a_r) / Gt_w)

    # Shear flow of a unit upward shear, dq/ds = -(Et / EI) z, with the cell cut where the upper skin meets the rear web and
    # the walls taken in turn: upper skin aft to fore (s from 0 to l), front web down, lower skin fore to aft, rear web up.
    # Each wall's flow at s and its integral along the wall, before the closing flow:
    def upper_flow(s):
        return -Et_s / EI * (a_r * s + (a_f - a_r) * s**2 / (2 * l))
    q1 = upper_flow(l)

    def front_flow(s):
        return q1 - Et_w / EI * (a_f * s - s**2 / 2)

    def lower_flow(s):
        return q1 + Et_s / EI * (a_f * s + (a_r - a_f) * s**2 / (2 * l))

    def rear_flow(s):
        return -Et_w / EI * (-a_r * s + s**2 / 2)

    integrals = [-Et_s / EI * l**2 * (2 * a_r + a_f) / 6, 2 * a_f * q1 - Et_w / EI * 2 * a_f**3 / 3,
                 q1 * l + Et_s / EI * l**2 * (2 * a_f + a_r) / 6, Et_w / EI * 2 * a_r**3 / 3]
    lengths, stiffness = [l, 2 * a_f, l, 2 * a_r], [Gt_s, Gt_w, Gt_s, Gt_w]
    closing = -sum(i / k for i, k in zip(integrals, stiffness)) / sum(n / k for n, k in zip(lengths, stiffness))
    # Moment about the leading edge's chord point of the flow on each straight wall: (z e_x - x e_z) times its integral.
    levers = [(a_r * (x_f - x_r) - x_r * (a_f - a_r)) / l, x_f, (-a_f * b - x_f * (a_f - a_r)) / l, -x_r]
    x_sc = -sum(lever * (i + closing * n) for lever, i, n in zip(levers, integrals, lengths))
    share_f, share_r = -(integrals[1] + closing * lengths[1]), integrals[3] + closing * lengths[3]  # the webs' upward forces

    mass = m["density"] * L * (2 * l * t_s + t_w * 2 * (a_f + a_r)) + case["skin"]["core_density"] * 2 * l * core * L
    f1 = 1.8751040687119611**2 / (2 * math.pi) * math.sqrt(EI / (mass / L * L**4))
    N_cr = 2 * math.pi**2 * (math.sqrt(D_s[0, 0] * D_s[1, 1]) + D_s[0, 1] + 2 * D_s[2, 2]) / l**2  # a long panel l wide

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

    def weakest(Nx, Nxy, kx, A, D, faces):
        """Smallest maximum-stress ratio over every face of every ply of a wall under Nx, Nxy and its own spanwise curvature
        kx with its other moments free: strain eps0 + zeta * k, both halves."""
        eps0 = np.linalg.solve(A, np.array([Nx, 0.0, Nxy]))
        d = np.linalg.inv(D)
        k = d[:, 0] / d[0, 0] * kx
        return min(max_stress_ratio(np.zeros(3), q @ to_fiber_axes(eps0 + zeta * k, angle), strengths)
                   for bottom, top, angle in faces for zeta in (bottom, top, -bottom, -top))

    along = np.linspace(0.0, 1.0, 401)  # where along each wall the plies are checked, as a share of its length
    n_z = b / l  # the upper skin's outward normal points up by this much (the lower skin's down)

    def root(n, speed, delta_cl=0.0, delta_cm=0.0):
        """Loads and checks at the root for a load factor, a speed and an aileron change over its span."""
        qd, side = pressure(speed), n * W / 2
        y1, y2 = (env["aileron"]["span_start"], env["aileron"]["span_end"]) if delta_cl or delta_cm else (0.0, 0.0)
        extra = qd * c * delta_cl
        shear = side + extra * (y2 - y1)
        moment = side * centroid_arm + extra * (y2**2 - y1**2) / 2
        torque = arm * shear + qd * c**2 * cm * L + qd * c**2 * delta_cm * (y2 - y1)
        kappa, flow = moment / EI, -torque / (2 * area)  # the torque's flow along the walls' axis
        skins = min(min(weakest(-kappa * z * Et_s, shear * (wall(s) + closing) + flow, -kappa * sign * n_z, A_s, D_s, faces_s)
                        for z, s in zip(z_of, l * along))
                    for wall, z_of, sign in ((upper_flow, a_r + (a_f - a_r) * along, 1), (lower_flow, -a_f + (a_f - a_r) * along, -1)))
        webs = min(min(weakest(-kappa * z * Et_w, shear * (wall(s) + closing) + flow, 0.0, A_w, D_w, faces_w)
                       for z, s in zip(z_of, h * along))
                   for wall, z_of, h in ((front_flow, a_f - 2 * a_f * along, 2 * a_f), (rear_flow, -a_r + 2 * a_r * along, 2 * a_r)))
        mean_compression = kappa * Et_s * (a_f + a_r) / 2  # of the upper skin across its width
        return {"dynamic_pressure": qd, "root_shear": shear, "root_moment": moment, "root_torque": torque,
                "skin_plies": skins, "spar_plies": webs, "skin_buckling": N_cr / mean_compression}

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
        "design": {"bending_stiffness": EI, "torsion_stiffness": GJ, "shear_center": x_sc, "shear_shares": [float(share_f), float(share_r)],
                   "skin_buckling_load": N_cr, "mass": mass,
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


# ----------------------------------------------------------------------------------------- the stepped lap cases

def _lap_steps(case: dict) -> tuple[list[dict], float, float, float]:
    """Each step with its lambda and P, the adhesive's G / eta and the load, in the case's own units, which are consistent
    (mm, MPa and N/mm; or in, psi and lb/in), so nothing is converted."""
    if case["units"] not in ("mm-MPa", "psi"):
        raise ValueError("a stepped lap case is stated in a consistent system: mm-MPa or psi")
    g, eta, load = case["adhesive"]["shear_modulus"], case["adhesive"]["thickness"], case["applied"]["load"]
    steps = []
    for row in case["steps"]:
        so, si = row["outer_modulus"] * row["outer_thickness"], row["inner_modulus"] * row["inner_thickness"]
        steps.append({**row, "lam": np.sqrt(g / eta * (1 / so + 1 / si)), "shared": load * so / (so + si)})
    return steps, g, eta, load


def stepped_lap(case: dict) -> dict:
    """A stepped lap by the general solution of each step (ADR-0130), a different route from the engine's tridiagonal
    system in the boundary forces: with x from a step's start and L its length, the outer adherend's force is

        N(x) = P + a exp(lam (x - L)) + b exp(-lam x)

    and the 2m constants come from one linear system: N = 0 at the tip, N = the load at the end, and N and dN/dx (the
    adhesive's shear stress) continuous at every boundary between steps. The largest stress of an adherend in a step is
    looked for at the step's ends and, by bisection, where the shear stress changes sign inside it."""
    steps, _, _, load = _lap_steps(case)
    m = len(steps)
    decay = [np.exp(-s["lam"] * s["length"]) for s in steps]
    matrix, right = np.zeros((2 * m, 2 * m)), np.zeros(2 * m)
    matrix[0, 0], matrix[0, 1], right[0] = decay[0], 1.0, -steps[0]["shared"]  # N = 0 at the tip
    for k in range(m - 1):
        n, row = k + 1, 1 + 2 * k
        matrix[row, 2 * k: 2 * k + 4] = [1.0, decay[k], -decay[n], -1.0]  # N continuous
        right[row] = steps[n]["shared"] - steps[k]["shared"]
        matrix[row + 1, 2 * k: 2 * k + 4] = [steps[k]["lam"], -steps[k]["lam"] * decay[k], -steps[n]["lam"] * decay[n], steps[n]["lam"]]  # dN/dx continuous
    matrix[-1, -2], matrix[-1, -1], right[-1] = 1.0, decay[-1], load - steps[-1]["shared"]  # N = the load at the end
    constants = np.linalg.solve(matrix, right).reshape(m, 2)

    def force(k: int, x: float) -> float:
        s, (a, b) = steps[k], constants[k]
        return s["shared"] + a * np.exp(s["lam"] * (x - s["length"])) + b * np.exp(-s["lam"] * x)

    def shear(k: int, x: float) -> float:
        s, (a, b) = steps[k], constants[k]
        return s["lam"] * (a * np.exp(s["lam"] * (x - s["length"])) - b * np.exp(-s["lam"] * x))

    ends = [[shear(k, 0.0), shear(k, s["length"])] for k, s in enumerate(steps)]
    peak = max((value for pair in ends for value in pair), key=abs)
    stresses = []
    for k, s in enumerate(steps):
        places = [0.0, s["length"]]
        if ends[k][0] * ends[k][1] < 0:  # the shear stress changes sign once inside the step: the force turns there
            low, high = 0.0, s["length"]
            for _ in range(200):
                middle = (low + high) / 2
                low, high = (middle, high) if shear(k, low) * shear(k, middle) > 0 else (low, middle)
            places.append((low + high) / 2)
        outer = [force(k, x) for x in places]
        stresses.append([max(outer, key=abs) / s["outer_thickness"], max((load - f for f in outer), key=abs) / s["inner_thickness"]])
    answer = {
        "lambda_length": [float(s["lam"] * s["length"]) for s in steps],
        "shared_forces": [float(s["shared"]) for s in steps],
        "boundary_forces": [0.0] + [float(force(k, 0.0)) for k in range(1, m)] + [float(load)],
        "shear_at_ends": [[float(a), float(b)] for a, b in ends],
        "peak_shear": float(peak),
        "adherend_stresses": [[float(a), float(b)] for a, b in stresses],
    }
    if "shear_strength" in case["adhesive"]:
        answer["elastic_limit_load"] = float(abs(load) * case["adhesive"]["shear_strength"] / abs(peak))
    if "double_lap" in case:
        answer["double_lap_strength"] = ductile_double_lap(case)
    return answer


def ductile_double_lap(case: dict) -> float:
    """The strength of a long double lap with an elastic-perfectly plastic adhesive, worked zone by zone for one bondline
    between half the inner adherend and one outer adherend (ADR-0130). With y the adhesive's shear strain, s the distance
    from an end of the overlap and v = dy/ds: v' = k tau(y), k = (1 / eta)(1 / Sa + 1 / Sb).
    1. Far inside a long overlap the strain dies away, so in the elastic zone y = ye exp(-lam s) and, where that zone
       starts, v = -lam ye, with lam^2 = k G.
    2. Across the plastic zone tau = tau_p, so v^2 rises by 2 k tau_p for each unit of strain: at the end of the overlap,
       where the strain is ye + yp, v^2 = (lam ye)^2 + 2 k tau_p yp.
    3. At the end where adherend a carries the whole load T and adherend b none, v = -T / (eta Sa), which gives T.
    The weaker of the two ends governs, and the joint has two bondlines."""
    g, eta = case["adhesive"]["shear_modulus"], case["adhesive"]["thickness"]
    tau_p, plastic = case["adhesive"]["shear_strength"], case["adhesive"].get("plastic_strain", 0.0)
    lap = case["double_lap"]
    half_inner, outer = lap["inner_modulus"] * lap["inner_thickness"] / 2, lap["outer_modulus"] * lap["outer_thickness"]
    k = (1 / half_inner + 1 / outer) / eta
    elastic = tau_p / g
    slope = np.sqrt(k * g * elastic**2 + 2 * k * tau_p * plastic)
    return float(2 * min(eta * half_inner * slope, eta * outer * slope))


LAP_CASES = {
    "constructed-flush-three-step-repair": stepped_lap,
    "constructed-single-step-lap-and-double-lap": stepped_lap,
}
