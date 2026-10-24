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
    "constructed-mixed-angle-lamina": mixed_angle_lamina,
    "constructed-two-material-laminate-cooling": two_material_laminate_cooling,
}
