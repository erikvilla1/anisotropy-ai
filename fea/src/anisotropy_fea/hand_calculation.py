"""The hand calculation of a coupon (ADR-0112): classical laminate theory for the coupon's laminate under its loading, written out step by
step with the coupon's own numbers. It is what the coupon report prints where it once printed our source code: the physics and the
arithmetic an engineer can repeat with a calculator, and no line of our implementation.

The steps are the ones taken by hand: the ply's stiffness in its fibre axes, each ply angle's stiffness in the coupon's axes, the
laminate's membrane stiffness A, its compliance and engineering constants, the section force and strain the loading gives with free
edges, each ply's strain and stress in its fibre axes, each failure criterion's strength ratio, and the loading at first-ply failure.

Every result written is the engine's own value (ADR-0001): the ply stiffness, the rotated stiffness, A, its inverse, the engineering
constants, the laminate state of `report.laminate_check`, the ply states and the criteria's ratios. This module writes each formula,
puts the values in, and evaluates the formula again from those values; a result whose formula does not give the engine's value to a
relative CLOSES of the step's largest value raises HandCalculationError, so the report never prints working that does not lead to the
result beside it. Values are written to GIVEN_DIGITS significant figures, inputs and results alike, so a step's results are the next
step's inputs as printed; a step repeated from the printed values meets its result to about the last figure. The formulas are LaTeX.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
from anisotropy_engine.engineering import engineering_constants
from anisotropy_engine.failure import (
    max_stress_ratio,
    tsai_hill_index,
    tsai_hill_ratio,
    tsai_wu_ratio,
)
from anisotropy_engine.lamina import Lamina, reduced_stiffness
from anisotropy_engine.laminate import Ply, abd_matrices
from anisotropy_engine.response import abd_compliance
from anisotropy_engine.rotation import transformed_reduced_stiffness

from .report import LaminateCheck
from .units import UNIT_LABEL, from_si, unit_factors
from .working import GIVEN_DIGITS, given, settled, tex

CLOSES = 1e-9  # relative to the step's largest value: the formula gives the engine's value
ZERO = 1e-12  # a direction cosine below this is the cosine of a right angle, written 0
CRITERIA = ("max_stress", "tsai_hill", "tsai_wu")  # the criteria a coupon's spec may name (spec refuses max_strain)
CRITERION_WORDS = {"max_stress": "maximum stress", "tsai_hill": "Tsai-Hill", "tsai_wu": "Tsai-Wu"}


class HandCalculationError(ValueError):
    """A formula of the hand calculation did not give the engine's value: the working would not lead to the result beside it."""


def _f(value: float) -> str:
    """A value put into a formula: GIVEN_DIGITS significant figures, a negative one in brackets."""
    text = tex(given(value), GIVEN_DIGITS)
    return f"({text})" if value < 0 else text


def _eq(lhs: str, formula: str | None, substituted: str | None, value: float, unit: str, note: str | None = None) -> dict[str, Any]:
    """One line of working: the symbol, its formula, the formula with the values in place, and the engine's value; `note` is a few
    words that follow the result ("by Tsai-Hill")."""
    return {"lhs": lhs, "formula": formula, "substituted": substituted, "value": given(value), "shown": tex(given(value), GIVEN_DIGITS),
            "unit": unit, "note": note}


def _closes(name: str, formula_value: float, engine_value: float, scale: float) -> None:
    if not math.isfinite(formula_value) or abs(formula_value - engine_value) > CLOSES * max(abs(scale), abs(engine_value), 1e-300):
        raise HandCalculationError(f"{name}: the formula gives {formula_value!r}, the engine {engine_value!r}")


def _cosines(theta_deg: float) -> tuple[float, float]:
    """m = cos(theta) and n = sin(theta), with the cosine of a right angle written as the zero it is."""
    t = math.radians(theta_deg)
    m, n = math.cos(t), math.sin(t)
    return (0.0 if abs(m) < ZERO else m), (0.0 if abs(n) < ZERO else n)


def _sum(terms: Sequence[tuple]) -> str:
    """Terms written as a sum, `a x + b y - c z`: each term (coefficient, the rest as LaTeX) or (coefficient, the rest, the rest's
    value). A term whose coefficient or value is zero is left out, since it adds nothing."""
    out = ""
    for term in terms:
        value, rest = term[0], term[1]
        if value == 0 or (len(term) > 2 and term[2] == 0):
            continue
        sign = "-" if value < 0 else "+"
        body = tex(given(abs(value)), GIVEN_DIGITS) + (r" \times " + rest if rest else "")
        out += (("-" if sign == "-" else "") + body) if not out else f" {sign} {body}"
    return out or "0"


def angle_label(stated: float) -> str:
    """A ply group's label in a superscript: its stated angle, as the layup is written."""
    return f"{stated:g}" + r"^\circ"


def hand_calculation(plies: Sequence[Ply], stated_deg: Sequence[float], units: str, criteria: Sequence[str] = (), f12_star: float | None = None,
                     check: LaminateCheck | None = None) -> dict[str, Any]:
    """The hand calculation of a laminate, bottom ply first, in the deck's `units`. `stated_deg` are the angles as the layup states
    them, from the coupon's length (ADR-0065); the plies' own angles are the engine's, from x. With `check`, the laminate theory state of
    the coupon under its loading (`report.laminate_check`): then the loading, the ply states, the criteria and first-ply failure follow.
    Without it, the stiffness steps alone."""
    plies = list(plies)
    if len(plies) != len(stated_deg) or not plies:
        raise ValueError("the hand calculation needs every ply's stated angle beside it")
    lab = UNIT_LABEL[units]
    stress = lab["stress"]
    per_length = lab["force_per_length"]
    compliance_unit = f"{lab['length']}/{lab['force']}"
    S = lambda v: float(from_si(v, "stress", units))
    T = lambda v: float(from_si(v, "length", units))
    NL = lambda v: float(from_si(v, "force_per_length", units))
    C = lambda v: float(v * unit_factors(units)["force_per_length"])

    materials: list[Lamina] = list(dict.fromkeys(p.material for p in plies))
    many = len(materials) > 1
    # the ply groups: one per material, stated angle and thickness, bottom-most first
    groups: list[dict[str, Any]] = []
    for k, (ply, stated) in enumerate(zip(plies, stated_deg)):
        key = (materials.index(ply.material), float(stated), ply.thickness_m)
        found = next((g for g in groups if g["key"] == key), None)
        if found is None:
            groups.append(found := {"key": key, "material": key[0], "stated": float(stated), "theta": float(ply.angle_deg),
                                    "thickness": T(ply.thickness_m), "plies": []})
        found["plies"].append(k + 1)
    labels = {id(g): angle_label(g["stated"]) + (f",{g['material'] + 1}" if many else "") for g in groups}
    same_t = len({g["thickness"] for g in groups}) == 1
    if len({(g["material"], g["stated"]) for g in groups}) != len(groups):
        labels = {id(g): labels[id(g)] + rf",t={tex(g['thickness'])}" for g in groups}  # one angle at two thicknesses: name both

    steps: list[dict[str, Any]] = []

    # ---- 1. the ply stiffness in its fibre axes (engine `reduced_stiffness`)
    q_of: list[np.ndarray] = []
    for i, mat in enumerate(materials):
        q = reduced_stiffness(mat)
        q_of.append(np.array([[S(v) for v in row] for row in q]))
        E1, E2, G12, nu12 = S(mat.E1), S(mat.E2), S(mat.G12), mat.nu12
        d = 1 - mat.nu12 * mat.nu21
        _closes("nu21", nu12 * E2 / E1, mat.nu21, mat.nu21)
        qs = q_of[-1]
        _closes("Q11", E1 / d, qs[0, 0], qs[0, 0])
        _closes("Q22", E2 / d, qs[1, 1], qs[0, 0])
        _closes("Q12", nu12 * E2 / d, qs[0, 1], qs[0, 0])
        _closes("Q66", G12, qs[2, 2], qs[0, 0])
        nu21 = mat.nu21
        steps.append({
            "id": "ply_stiffness" + (f"_{i + 1}" if many else ""),
            "title": "The ply's stiffness in its fibre axes" + (f", material {i + 1}" if many else ""),
            "text": ("Axis 1 runs along the fibres and axis 2 across them, in the ply's plane. A thin ply is in plane stress, so its stress "
                     "and strain in these axes are related by the reduced stiffness $`\\mathbf{Q}`$, from the four elastic constants. The minor "
                     "Poisson's ratio follows from reciprocity, and $`Q_{66} = G_{12}`$ because the shear strain is the engineering one."),
            "given": [("E_1", E1, stress), ("E_2", E2, stress), ("G_{12}", G12, stress), (r"\nu_{12}", nu12, "-")],
            "equations": [
                _eq(r"\nu_{21}", r"\nu_{12}\,\dfrac{E_2}{E_1}", rf"{_f(nu12)} \times \dfrac{{{_f(E2)}}}{{{_f(E1)}}}", nu21, "-"),
                _eq(r"1 - \nu_{12}\nu_{21}", None, rf"1 - {_f(nu12)} \times {_f(nu21)}", d, "-"),
                _eq("Q_{11}", r"\dfrac{E_1}{1-\nu_{12}\nu_{21}}", rf"\dfrac{{{_f(E1)}}}{{{_f(d)}}}", qs[0, 0], stress),
                _eq("Q_{22}", r"\dfrac{E_2}{1-\nu_{12}\nu_{21}}", rf"\dfrac{{{_f(E2)}}}{{{_f(d)}}}", qs[1, 1], stress),
                _eq("Q_{12}", r"\dfrac{\nu_{12}E_2}{1-\nu_{12}\nu_{21}}", rf"\dfrac{{{_f(nu12)} \times {_f(E2)}}}{{{_f(d)}}}", qs[0, 1], stress),
                _eq("Q_{66}", "G_{12}", None, qs[2, 2], stress),
            ],
            "source": "Daniel and Ishai, Eq. 4.56",
        })

    # ---- 2. each ply angle's stiffness in the coupon's axes (engine `transformed_reduced_stiffness`)
    qbar: dict[int, np.ndarray] = {}
    cosines: dict[int, tuple[float, float]] = {}
    rotation_rows, rotation_equations = [], []
    for g in groups:
        mat = materials[g["material"]]
        engine = np.array([[S(v) for v in row] for row in transformed_reduced_stiffness(mat, g["theta"])])
        qbar[id(g)] = engine
        m, n = _cosines(g["theta"])
        cosines[id(g)] = (m, n)
        q11, q22, q12, q66 = (float(q_of[g["material"]][i, j]) for i, j in ((0, 0), (1, 1), (0, 1), (2, 2)))
        p = {"m4": m**4, "n4": n**4, "m2n2": m * m * n * n, "m3n": m**3 * n, "mn3": m * n**3, "m4n4": m**4 + n**4}
        Q11, Q22, Q12, Q66 = _f(q11), _f(q22), _f(q12), _f(q66)
        P = {key: _f(value) for key, value in p.items()}
        formulas = {  # each term's structure kept as the formula writes it, so the reader sees which Q goes where
            (0, 0): (r"Q_{11}m^4 + 2(Q_{12}+2Q_{66})m^2n^2 + Q_{22}n^4", q11 * p["m4"] + 2 * (q12 + 2 * q66) * p["m2n2"] + q22 * p["n4"],
                     rf"{Q11} \times {P['m4']} + 2({Q12} + 2 \times {Q66}) \times {P['m2n2']} + {Q22} \times {P['n4']}"),
            (1, 1): (r"Q_{11}n^4 + 2(Q_{12}+2Q_{66})m^2n^2 + Q_{22}m^4", q11 * p["n4"] + 2 * (q12 + 2 * q66) * p["m2n2"] + q22 * p["m4"],
                     rf"{Q11} \times {P['n4']} + 2({Q12} + 2 \times {Q66}) \times {P['m2n2']} + {Q22} \times {P['m4']}"),
            (0, 1): (r"(Q_{11}+Q_{22}-4Q_{66})m^2n^2 + Q_{12}(m^4+n^4)", (q11 + q22 - 4 * q66) * p["m2n2"] + q12 * p["m4n4"],
                     rf"({Q11} + {Q22} - 4 \times {Q66}) \times {P['m2n2']} + {Q12} \times {P['m4n4']}"),
            (2, 2): (r"(Q_{11}+Q_{22}-2Q_{12}-2Q_{66})m^2n^2 + Q_{66}(m^4+n^4)", (q11 + q22 - 2 * q12 - 2 * q66) * p["m2n2"] + q66 * p["m4n4"],
                     rf"({Q11} + {Q22} - 2 \times {Q12} - 2 \times {Q66}) \times {P['m2n2']} + {Q66} \times {P['m4n4']}"),
            (0, 2): (r"(Q_{11}-Q_{12}-2Q_{66})m^3n + (Q_{12}-Q_{22}+2Q_{66})mn^3", (q11 - q12 - 2 * q66) * p["m3n"] + (q12 - q22 + 2 * q66) * p["mn3"],
                     rf"({Q11} - {Q12} - 2 \times {Q66}) \times {P['m3n']} + ({Q12} - {Q22} + 2 \times {Q66}) \times {P['mn3']}"),
            (1, 2): (r"(Q_{11}-Q_{12}-2Q_{66})mn^3 + (Q_{12}-Q_{22}+2Q_{66})m^3n", (q11 - q12 - 2 * q66) * p["mn3"] + (q12 - q22 + 2 * q66) * p["m3n"],
                     rf"({Q11} - {Q12} - 2 \times {Q66}) \times {P['mn3']} + ({Q12} - {Q22} + 2 \times {Q66}) \times {P['m3n']}"),
        }
        scale = float(np.max(np.abs(engine)))
        lines = []
        for (i, j), (formula, value, substituted) in formulas.items():
            _closes(f"Qbar{i + 1}{j + 1} at {g['stated']:g}", value, engine[i, j], scale)
            name = {(0, 0): "11", (1, 1): "22", (0, 1): "12", (2, 2): "66", (0, 2): "16", (1, 2): "26"}[(i, j)]
            shown = float(settled(np.array([engine[i, j], scale]))[0])
            lines.append(_eq(rf"\bar{{Q}}_{{{name}}}^{{({labels[id(g)]})}}", formula, substituted, shown, stress))
        rotation_rows.append({"label": labels[id(g)], "stated": g["stated"], "theta": g["theta"], "plies": g["plies"], "m": m, "n": n, **p})
        rotation_equations.append({"label": labels[id(g)], "stated": g["stated"], "theta": g["theta"], "plies": g["plies"], "equations": lines})
    steps.append({
        "id": "rotation", "title": "Each ply angle's stiffness in the coupon's axes",
        "text": ("The coupon's axes are $`x`$ across its width and $`y`$ along its length, the direction it is pulled. A ply's stated angle is "
                 "counted from the length; the formulas count the fibre angle $`\\theta`$ from $`x`$, counterclockwise, so $`\\theta`$ is the stated "
                 "angle plus 90°, brought into $`(-90^\\circ, 90^\\circ]`$ since a fibre at $`\\theta`$ and at $`\\theta + 180^\\circ`$ is the "
                 "same fibre. With $`m = \\cos\\theta`$ and $`n = \\sin\\theta`$, turning $`\\mathbf{Q}`$ into the coupon's axes, "
                 "$`\\bar{\\mathbf{Q}} = \\mathbf{T}_\\sigma(-\\theta)\\,\\mathbf{Q}\\,\\mathbf{T}_\\varepsilon(\\theta)`$, gives the six terms below. "
                 "$`\\bar{Q}_{16}`$ and $`\\bar{Q}_{26}`$ couple stretching with shear: they are zero for fibres along or across the pull, "
                 "and equal and opposite for $`+\\theta`$ and $`-\\theta`$."),
        "angles": rotation_rows, "groups": rotation_equations, "equations": [],
        "source": "Daniel and Ishai, Eqs. 4.57 to 4.62 and 4.67",
    })

    # ---- 3. the laminate's membrane stiffness A (engine `abd_matrices`)
    A_si, B_si, _ = abd_matrices(plies)
    A = np.array([[NL(v) for v in row] for row in A_si])
    h = sum(T(p.thickness_m) for p in plies)
    a_scale = float(np.max(np.abs(A)))
    a_lines = []
    for (i, j), name in (((0, 0), "11"), ((1, 1), "22"), ((0, 1), "12"), ((2, 2), "66"), ((0, 2), "16"), ((1, 2), "26")):
        value = sum(len(g["plies"]) * g["thickness"] * qbar[id(g)][i, j] for g in groups)
        _closes(f"A{name}", value, A[i, j], a_scale)
        if same_t:
            t = groups[0]["thickness"]
            inner = _sum([(len(g["plies"]), rf"\bar{{Q}}_{{{name}}}^{{({labels[id(g)]})}}") for g in groups])
            numbers = _sum([(len(g["plies"]), _f(float(settled(np.array([qbar[id(g)][i, j], float(np.max(np.abs(qbar[id(g)])))]))[0])))
                            for g in groups])
            formula, substituted = rf"t\,\bigl({inner}\bigr)", rf"{_f(t)} \times \bigl({numbers}\bigr)"
        else:
            formula = _sum([(len(g["plies"]) * g["thickness"], rf"\bar{{Q}}_{{{name}}}^{{({labels[id(g)]})}}") for g in groups])
            substituted = _sum([(len(g["plies"]) * g["thickness"], _f(qbar[id(g)][i, j])) for g in groups])
        a_lines.append(_eq(f"A_{{{name}}}", formula, substituted, float(settled(np.array([A[i, j], a_scale]))[0]), per_length))
    symmetric = float(np.max(np.abs(B_si))) <= CLOSES * float(np.max(np.abs(A_si))) * sum(p.thickness_m for p in plies)
    count = ", ".join(f"{len(g['plies'])} at {g['stated']:g}°" for g in groups)
    steps.append({
        "id": "laminate", "title": "The laminate's membrane stiffness",
        "text": (f"Each ply carries the in-plane force in proportion to its thickness, so the laminate's membrane stiffness $`\\mathbf{{A}}`$ sums "
                 f"each ply's $`\\bar{{\\mathbf{{Q}}}}`$ times its thickness: $`\\mathbf{{N}} = \\mathbf{{A}}\\,\\boldsymbol{{\\varepsilon}}`$, "
                 f"the force per unit width for a strain of the mid-plane. This laminate has "
                 f"{len(plies)} plies ({count})" + (f", each {tex(given(groups[0]['thickness']))} {lab['length']} thick" if same_t else "")
                 + f", {tex(given(h))} {lab['length']} in all. "
                 + ("Every ply above the mid-plane has its mirror below it, so the coupling stiffness $`\\mathbf{B}`$ is zero: stretching the "
                    "laminate does not bend it, and $`\\mathbf{A}`$ alone describes a coupon loaded in its plane."
                    if symmetric else
                    "The layup is not symmetric about the mid-plane, so its coupling stiffness $`\\mathbf{B}`$ is not zero: stretching it also "
                    "bends it, which the steps below, written for a laminate loaded in its plane, do not follow.")),
        "given": [("t" if same_t else "h", groups[0]["thickness"] if same_t else h, lab["length"])],
        "equations": a_lines, "symmetric": symmetric, "thickness": h,
        "source": "Daniel and Ishai, Eq. 7.20",
    })

    # ---- 4. its compliance a = A^-1 and engineering constants (engine `abd_compliance`, `engineering_constants`)
    a_si = abd_compliance(plies)[0]
    a = np.array([[C(v) for v in row] for row in a_si])
    c_scale = float(np.max(np.abs(a)))
    balanced = abs(A[0, 2]) <= CLOSES * a_scale and abs(A[1, 2]) <= CLOSES * a_scale
    A11, A22, A12, A66, A16, A26 = A[0, 0], A[1, 1], A[0, 1], A[2, 2], A[0, 2], A[1, 2]
    c_lines = []
    if balanced:
        delta = A11 * A22 - A12**2
        c_lines.append(_eq(r"\Delta", r"A_{11}A_{22} - A_{12}^2", rf"{_f(A11)} \times {_f(A22)} - {_f(A12)}^2", delta, f"({per_length})²"))
        forms = {(0, 0): (r"\dfrac{A_{22}}{\Delta}", rf"\dfrac{{{_f(A22)}}}{{{_f(delta)}}}", A22 / delta),
                 (1, 1): (r"\dfrac{A_{11}}{\Delta}", rf"\dfrac{{{_f(A11)}}}{{{_f(delta)}}}", A11 / delta),
                 (0, 1): (r"-\dfrac{A_{12}}{\Delta}", rf"-\dfrac{{{_f(A12)}}}{{{_f(delta)}}}", -A12 / delta),
                 (2, 2): (r"\dfrac{1}{A_{66}}", rf"\dfrac{{1}}{{{_f(A66)}}}", 1 / A66)}
    else:
        det = A11 * (A22 * A66 - A26**2) - A12 * (A12 * A66 - A26 * A16) + A16 * (A12 * A26 - A22 * A16)
        c_lines.append(_eq(r"\det\mathbf{A}", r"A_{11}(A_{22}A_{66}-A_{26}^2) - A_{12}(A_{12}A_{66}-A_{26}A_{16}) + A_{16}(A_{12}A_{26}-A_{22}A_{16})",
                           None, det, f"({per_length})³"))
        forms = {(0, 0): (r"\dfrac{A_{22}A_{66}-A_{26}^2}{\det\mathbf{A}}", None, (A22 * A66 - A26**2) / det),
                 (1, 1): (r"\dfrac{A_{11}A_{66}-A_{16}^2}{\det\mathbf{A}}", None, (A11 * A66 - A16**2) / det),
                 (0, 1): (r"\dfrac{A_{16}A_{26}-A_{12}A_{66}}{\det\mathbf{A}}", None, (A16 * A26 - A12 * A66) / det),
                 (2, 2): (r"\dfrac{A_{11}A_{22}-A_{12}^2}{\det\mathbf{A}}", None, (A11 * A22 - A12**2) / det),
                 (0, 2): (r"\dfrac{A_{12}A_{26}-A_{16}A_{22}}{\det\mathbf{A}}", None, (A12 * A26 - A16 * A22) / det),
                 (1, 2): (r"\dfrac{A_{12}A_{16}-A_{11}A_{26}}{\det\mathbf{A}}", None, (A12 * A16 - A11 * A26) / det)}
    for (i, j), (formula, substituted, value) in forms.items():
        name = {(0, 0): "11", (1, 1): "22", (0, 1): "12", (2, 2): "66", (0, 2): "16", (1, 2): "26"}[(i, j)]
        _closes(f"a{name}", value, a[i, j], c_scale)
        c_lines.append(_eq(f"a_{{{name}}}", formula, substituted, a[i, j], compliance_unit))
    if balanced:
        _closes("a16", 0.0, a[0, 2], c_scale)
        _closes("a26", 0.0, a[1, 2], c_scale)
    constants = engineering_constants(plies)
    a11, a22, a12, a66, a26 = a[0, 0], a[1, 1], a[0, 1], a[2, 2], a[1, 2]
    k_lines = []
    for lhs, formula, substituted, value, engine, unit in (
            ("E_x", r"\dfrac{1}{h\,a_{11}}", rf"\dfrac{{1}}{{{_f(h)} \times {_f(a11)}}}", 1 / (h * a11), S(constants.Ex), stress),
            ("E_y", r"\dfrac{1}{h\,a_{22}}", rf"\dfrac{{1}}{{{_f(h)} \times {_f(a22)}}}", 1 / (h * a22), S(constants.Ey), stress),
            ("G_{xy}", r"\dfrac{1}{h\,a_{66}}", rf"\dfrac{{1}}{{{_f(h)} \times {_f(a66)}}}", 1 / (h * a66), S(constants.Gxy), stress),
            (r"\nu_{xy}", r"-\dfrac{a_{12}}{a_{11}}", rf"-\dfrac{{{_f(a12)}}}{{{_f(a11)}}}", -a12 / a11, constants.nu_xy, "-"),
            (r"\nu_{yx}", r"-\dfrac{a_{12}}{a_{22}}", rf"-\dfrac{{{_f(a12)}}}{{{_f(a22)}}}", -a12 / a22, constants.nu_yx, "-"),
            *(() if balanced else ((r"\eta_{ys}", r"\dfrac{a_{26}}{a_{22}}", rf"\dfrac{{{_f(a26)}}}{{{_f(a22)}}}", a26 / a22, constants.eta_ys, "-"),))):
        if symmetric:  # the engineering constants invert the whole ABD: with B zero that is A's inverse, and the formula closes
            _closes(lhs, value, engine, engine)
        k_lines.append(_eq(lhs, formula, substituted, engine, unit))
    steps.append({
        "id": "constants", "title": "The laminate's compliance and engineering constants",
        "text": ("The inverse of $`\\mathbf{A}`$, the compliance $`\\mathbf{a}`$, gives the mid-plane strain for a force per unit width, "
                 "$`\\boldsymbol{\\varepsilon} = \\mathbf{a}\\,\\mathbf{N}`$. "
                 + ("The laminate is balanced ($`A_{16} = A_{26} = 0`$), so the inverse is written with $`\\Delta`$ alone and $`a_{16} = a_{26} = 0`$. "
                    if balanced else "The laminate couples stretching with shear ($`A_{16}`$ or $`A_{26}`$ is not zero), so the whole inverse is written out. ")
                 + "Read as a homogeneous plate of thickness $`h`$, the laminate has the engineering constants below: $`E_y`$ is its modulus "
                 "along the pull, $`\\nu_{yx}`$ its Poisson's ratio under that pull."),
        "equations": c_lines + k_lines, "balanced": balanced,
        "source": "Daniel and Ishai, Eq. 7.84",
    })

    out: dict[str, Any] = {"units": units, "digits": GIVEN_DIGITS, "plies": len(plies), "groups": [
        {"label": labels[id(g)], "stated": g["stated"], "theta": g["theta"], "plies": g["plies"], "thickness": g["thickness"]} for g in groups],
        "constants": {"Ex": S(constants.Ex), "Ey": S(constants.Ey), "Gxy": S(constants.Gxy), "nu_xy": constants.nu_xy, "nu_yx": constants.nu_yx},
        "steps": steps, "state": None, "failure": None}
    if check is None or not symmetric:
        return out

    # ---- 5. the loading: the section force and the mid-plane strain with free edges (engine `mixed_response` in `laminate_check`)
    strain = settled(np.asarray(check.strain, dtype=float))
    force = settled(np.array([NL(v) for v in check.section_force]))
    w, L = T(check.width_m), T(check.free_length_m)
    Ny = float(force[1])
    eps_scale = float(np.max(np.abs(strain)))
    lines = []
    givens: list[tuple[str, float, str]] = []
    if check.control == "displacement":
        u = T(check.applied)
        givens += [("u", u, lab["length"]), ("w" if not check.narrowed else "w_n", w, lab["length"])]
        if check.narrowed:
            Lc = T(check.compliance_length_m)
            givens.append(("L_c", Lc, lab["length"]))
            _closes("Ny", u / (a22 * Lc), Ny, Ny)
            lines.append(_eq("N_y", r"\dfrac{u}{a_{22}\,L_c}", rf"\dfrac{{{_f(u)}}}{{{_f(a22)} \times {_f(Lc)}}}", Ny, per_length))
            _closes("eps_y", a22 * Ny, strain[1], eps_scale)
            lines.append(_eq(r"\varepsilon_y", r"a_{22}\,N_y", rf"{_f(a22)} \times {_f(Ny)}", strain[1], "-"))
            text = ("The coupon narrows between the grips, so the pull is shared along the free length as a bar of varying width shares it: "
                    "each length $`dy`$ stretches by $`a_{22} N_y\\,w_n / w(y)\\,dy`$. Summed over the free length, the pull is "
                    "$`u = a_{22} N_y L_c`$, with $`L_c = \\int w_n / w(y)\\,dy`$ over the free length, and $`N_y`$ is read at the narrowest "
                    "width $`w_n`$, where the gauge is. The long edges are free, so $`N_x = N_{xy} = 0`$.")
        else:
            givens.append(("L", L, lab["length"]))
            _closes("eps_y", u / L, strain[1], eps_scale)
            lines.append(_eq(r"\varepsilon_y", r"\dfrac{u}{L}", rf"\dfrac{{{_f(u)}}}{{{_f(L)}}}", strain[1], "-"))
            _closes("Ny", strain[1] / a22, Ny, Ny)
            lines.append(_eq("N_y", r"\dfrac{\varepsilon_y}{a_{22}}", rf"\dfrac{{{_f(strain[1])}}}{{{_f(a22)}}}", Ny, per_length))
            text = ("The grips move apart by $`u`$ over the free length $`L`$ between them, so the strain along the coupon is $`u/L`$. The long "
                    "edges are free, so no force acts across the width and none in shear: $`N_x = N_{xy} = 0`$. The force per unit width follows "
                    "from $`\\varepsilon_y = a_{22} N_y`$, and the strain across the width and in shear from the same compliance.")
    else:
        F = float(from_si(check.applied, "force", units))
        givens += [("F", F, lab["force"]), ("w", w, lab["length"])]
        _closes("Ny", F / w, Ny, Ny)
        lines.append(_eq("N_y", r"\dfrac{F}{w}", rf"\dfrac{{{_f(F)}}}{{{_f(w)}}}", Ny, per_length))
        _closes("eps_y", a22 * Ny, strain[1], eps_scale)
        lines.append(_eq(r"\varepsilon_y", r"a_{22}\,N_y", rf"{_f(a22)} \times {_f(Ny)}", strain[1], "-"))
        text = ("The force $`F`$ is spread over the width $`w`$, so the force per unit width is $`F/w`$. The long edges are free, so "
                "$`N_x = N_{xy} = 0`$, and the mid-plane strain is $`\\boldsymbol{\\varepsilon} = \\mathbf{a}\\,\\mathbf{N}`$.")
    _closes("eps_x", a12 * Ny, strain[0], eps_scale)
    lines.append(_eq(r"\varepsilon_x", r"a_{12}\,N_y", rf"{_f(a12)} \times {_f(Ny)}", strain[0], "-"))
    _closes("gamma_xy", a26 * Ny, strain[2], eps_scale)
    lines.append(_eq(r"\gamma_{xy}", r"a_{26}\,N_y", None if balanced else rf"{_f(a26)} \times {_f(Ny)}", strain[2], "-"))
    reaction = float(from_si(check.reaction_N, "force", units))
    if check.control == "displacement":
        _closes("F", Ny * w, reaction, reaction)
        lines.append(_eq("F", r"N_y\,w" + ("_n" if check.narrowed else ""), rf"{_f(Ny)} \times {_f(w)}", reaction, lab["force"]))
    steps.append({"id": "loading", "title": "The force and the strain the loading gives", "text": text, "given": givens, "equations": lines,
                  "source": "Daniel and Ishai, Section 7.12"})
    out["state"] = {"strain": [float(v) for v in strain], "Ny": Ny, "reaction": reaction, "control": check.control,
                    "applied": T(check.applied) if check.control == "displacement" else float(from_si(check.applied, "force", units))}

    # ---- 6 and 7. every ply angle's strain and stress in its fibre axes (engine `ply_surfaces` in `laminate_check`)
    ex, ey, gxy = (float(v) for v in strain)
    strain_groups, stress_groups, ply_states = [], [], {}
    stress_scale = float(np.max(np.abs(check.ply_stress_12)))
    for g in groups:
        k = g["plies"][0] - 1
        m, n = cosines[id(g)]
        e12 = settled(np.asarray(check.ply_strain_12[k], dtype=float)) if np.any(check.ply_strain_12[k]) else np.zeros(3)
        s12_si = np.asarray(check.ply_stress_12[k], dtype=float)
        s12 = np.array([S(v) for v in s12_si])
        s12 = np.where(np.abs(s12) <= CLOSES * S(stress_scale), 0.0, s12)
        e_scale = float(np.max(np.abs(check.ply_strain_12[k])))
        rows = [(r"\varepsilon_1", [(m * m, _f(ex), ex), (n * n, _f(ey), ey), (m * n, _f(gxy), gxy)], m * m * ex + n * n * ey + m * n * gxy),
                (r"\varepsilon_2", [(n * n, _f(ex), ex), (m * m, _f(ey), ey), (-m * n, _f(gxy), gxy)], n * n * ex + m * m * ey - m * n * gxy),
                (r"\gamma_{12}", [(-2 * m * n, _f(ex), ex), (2 * m * n, _f(ey), ey), (m * m - n * n, _f(gxy), gxy)],
                 -2 * m * n * ex + 2 * m * n * ey + (m * m - n * n) * gxy)]
        formulas = (r"m^2\varepsilon_x + n^2\varepsilon_y + mn\,\gamma_{xy}", r"n^2\varepsilon_x + m^2\varepsilon_y - mn\,\gamma_{xy}",
                    r"-2mn\,\varepsilon_x + 2mn\,\varepsilon_y + (m^2-n^2)\gamma_{xy}")
        lines = []
        for i, ((lhs, terms, value), formula) in enumerate(zip(rows, formulas)):
            _closes(f"ply strain {i + 1} at {g['stated']:g}", value, float(check.ply_strain_12[k][i]), max(e_scale, eps_scale))
            lines.append(_eq(lhs + rf"^{{({labels[id(g)]})}}", formula, _sum(terms), float(e12[i]), "-"))
        strain_groups.append({"label": labels[id(g)], "stated": g["stated"], "theta": g["theta"], "plies": g["plies"], "m": m, "n": n,
                              "equations": lines})
        q = q_of[g["material"]]
        e1, e2, g12 = (float(v) for v in e12)
        sigma = [(r"\sigma_1", r"Q_{11}\varepsilon_1 + Q_{12}\varepsilon_2", [(q[0, 0], _f(e1), e1), (q[0, 1], _f(e2), e2)], q[0, 0] * e1 + q[0, 1] * e2),
                 (r"\sigma_2", r"Q_{12}\varepsilon_1 + Q_{22}\varepsilon_2", [(q[0, 1], _f(e1), e1), (q[1, 1], _f(e2), e2)], q[0, 1] * e1 + q[1, 1] * e2),
                 (r"\tau_{12}", r"Q_{66}\gamma_{12}", [(q[2, 2], _f(g12), g12)], q[2, 2] * g12)]
        lines = []
        for i, (lhs, formula, terms, value) in enumerate(sigma):
            _closes(f"ply stress {i + 1} at {g['stated']:g}", value, float(s12[i]), S(stress_scale))
            lines.append(_eq(lhs + rf"^{{({labels[id(g)]})}}", formula, _sum(terms), float(s12[i]), stress))
        stress_groups.append({"label": labels[id(g)], "stated": g["stated"], "plies": g["plies"], "equations": lines})
        ply_states[id(g)] = (s12_si, s12, e12)
    steps.append({"id": "ply_strain", "title": "Every ply's strain in its fibre axes",
                  "text": ("Every ply shares the laminate's mid-plane strain, since the laminate is loaded in its plane and does not bend. "
                           "Turning that strain into each ply's fibre axes, $`\\boldsymbol{\\varepsilon}_{12} = \\mathbf{T}_\\varepsilon(\\theta)\\,"
                           "\\boldsymbol{\\varepsilon}_{xy}`$, gives the strain along and across its fibres. Plies at the same angle carry the same "
                           "strain, so one set of lines serves each angle."),
                  "groups": strain_groups, "equations": [], "source": "Daniel and Ishai, Eqs. 4.57 to 4.62"})
    steps.append({"id": "ply_stress", "title": "Every ply's stress in its fibre axes",
                  "text": "Each ply's stress in its fibre axes is its stiffness $`\\mathbf{Q}`$ times its strain in those axes.",
                  "groups": stress_groups, "equations": [], "source": "Daniel and Ishai, Eq. 4.56"})

    # ---- 8. each criterion's strength ratio for every ply angle (the engine's criterion functions)
    with_strengths = all(materials[g["material"]].strengths is not None for g in groups)
    criteria = [c for c in criteria if c in CRITERIA]
    if not criteria or not with_strengths:
        return out
    failure: dict[str, Any] = {}
    for criterion in criteria:
        if criterion == "tsai_wu" and f12_star is None:
            continue
        entries, coefficient_lines = [], []
        for g in groups:
            mat = materials[g["material"]]
            st = {name: S(getattr(mat.strengths, name)) for name in ("F1t", "F1c", "F2t", "F2c", "F6")}
            s12_si, (s1, s2, t12), _ = ply_states[id(g)]
            label = labels[id(g)]
            lines = []
            if criterion == "max_stress":
                engine, mode = max_stress_ratio(s12_si, mat.strengths)
                ratios = []
                for value, sym, tension, compression, index in ((s1, r"\sigma_1", "F1t", "F1c", "1"), (s2, r"\sigma_2", "F2t", "F2c", "2")):
                    if value == 0:
                        continue
                    key = tension if value > 0 else compression
                    r = st[key] / abs(value)
                    ratios.append(r)
                    lines.append(_eq(rf"R_{index}^{{({label})}}", rf"\dfrac{{F_{{{key[1:]}}}}}{{|{sym}|}}", rf"\dfrac{{{_f(st[key])}}}{{{_f(abs(value))}}}", r, "-"))
                if t12 != 0:
                    r = st["F6"] / abs(t12)
                    ratios.append(r)
                    lines.append(_eq(rf"R_6^{{({label})}}", r"\dfrac{F_6}{|\tau_{12}|}", rf"\dfrac{{{_f(st['F6'])}}}{{{_f(abs(t12))}}}", r, "-"))
                value = min(ratios) if ratios else math.inf
                _closes(f"max stress at {g['stated']:g}", value, engine, engine)
                lines.append(_eq(rf"R^{{({label})}}", r"\min(R_1, R_2, R_6)", None, engine, "-"))
            elif criterion == "tsai_hill":
                engine, mode = tsai_hill_ratio(s12_si, mat.strengths), "interactive"
                X, Y, Sh = st["F1c" if s1 < 0 else "F1t"], st["F2c" if s2 < 0 else "F2t"], st["F6"]
                fi = (s1 / X) ** 2 - s1 * s2 / X**2 + (s2 / Y) ** 2 + (t12 / Sh) ** 2
                _closes(f"Tsai-Hill index at {g['stated']:g}", fi, tsai_hill_index(s12_si, mat.strengths), fi)
                xs, ys = ("F_{1c}" if s1 < 0 else "F_{1t}"), ("F_{2c}" if s2 < 0 else "F_{2t}")
                lines.append(_eq(rf"\mathrm{{FI}}^{{({label})}}",
                                 rf"\left(\dfrac{{\sigma_1}}{{{xs}}}\right)^2 - \dfrac{{\sigma_1\sigma_2}}{{{xs}^2}} + \left(\dfrac{{\sigma_2}}{{{ys}}}\right)^2 + \left(\dfrac{{\tau_{{12}}}}{{F_6}}\right)^2",
                                 (rf"\left(\dfrac{{{_f(s1)}}}{{{_f(X)}}}\right)^2 - \dfrac{{{_f(s1)} \times {_f(s2)}}}{{{_f(X)}^2}} + "
                                  rf"\left(\dfrac{{{_f(s2)}}}{{{_f(Y)}}}\right)^2 + \left(\dfrac{{{_f(t12)}}}{{{_f(Sh)}}}\right)^2"), fi, "-"))
                _closes(f"Tsai-Hill at {g['stated']:g}", 1 / math.sqrt(fi) if fi > 0 else math.inf, engine, engine)
                lines.append(_eq(rf"R^{{({label})}}", r"\dfrac{1}{\sqrt{\mathrm{FI}}}", rf"\dfrac{{1}}{{\sqrt{{{_f(fi)}}}}}", engine, "-"))
            else:
                engine, mode = tsai_wu_ratio(s12_si, mat.strengths, f12_star), "interactive"
                f1, f2 = 1 / st["F1t"] - 1 / st["F1c"], 1 / st["F2t"] - 1 / st["F2c"]
                f11, f22, f66 = 1 / (st["F1t"] * st["F1c"]), 1 / (st["F2t"] * st["F2c"]), 1 / st["F6"] ** 2
                f12 = f12_star * math.sqrt(f11 * f22)
                if not coefficient_lines:
                    inv = f"1/{stress}"
                    coefficient_lines = [
                        _eq("f_1", r"\dfrac{1}{F_{1t}} - \dfrac{1}{F_{1c}}", rf"\dfrac{{1}}{{{_f(st['F1t'])}}} - \dfrac{{1}}{{{_f(st['F1c'])}}}", f1, inv),
                        _eq("f_2", r"\dfrac{1}{F_{2t}} - \dfrac{1}{F_{2c}}", rf"\dfrac{{1}}{{{_f(st['F2t'])}}} - \dfrac{{1}}{{{_f(st['F2c'])}}}", f2, inv),
                        _eq("f_{11}", r"\dfrac{1}{F_{1t}F_{1c}}", rf"\dfrac{{1}}{{{_f(st['F1t'])} \times {_f(st['F1c'])}}}", f11, f"{inv}²"),
                        _eq("f_{22}", r"\dfrac{1}{F_{2t}F_{2c}}", rf"\dfrac{{1}}{{{_f(st['F2t'])} \times {_f(st['F2c'])}}}", f22, f"{inv}²"),
                        _eq("f_{66}", r"\dfrac{1}{F_6^2}", rf"\dfrac{{1}}{{{_f(st['F6'])}^2}}", f66, f"{inv}²"),
                        _eq("f_{12}", r"f_{12}^*\sqrt{f_{11}f_{22}}", rf"{_f(f12_star)} \times \sqrt{{{_f(f11)} \times {_f(f22)}}}", f12, f"{inv}²"),
                    ]
                qa = f11 * s1**2 + f22 * s2**2 + f66 * t12**2 + 2 * f12 * s1 * s2
                qb = f1 * s1 + f2 * s2
                r = (-qb + math.sqrt(qb * qb + 4 * qa)) / (2 * qa) if qa > 0 else math.inf
                _closes(f"Tsai-Wu at {g['stated']:g}", r, engine, engine)
                lines += [_eq(rf"a^{{({label})}}", r"f_{11}\sigma_1^2 + f_{22}\sigma_2^2 + f_{66}\tau_{12}^2 + 2f_{12}\sigma_1\sigma_2",
                              _sum([(f11, f"{_f(s1)}^2", s1), (f22, f"{_f(s2)}^2", s2), (f66, f"{_f(t12)}^2", t12), (2 * f12, f"{_f(s1)} \\times {_f(s2)}", s1 * s2)]), qa, "-"),
                          _eq(rf"b^{{({label})}}", r"f_1\sigma_1 + f_2\sigma_2", _sum([(f1, _f(s1), s1), (f2, _f(s2), s2)]), qb, "-"),
                          _eq(rf"R^{{({label})}}", r"\dfrac{-b + \sqrt{b^2 + 4a}}{2a}",
                              rf"\dfrac{{-{_f(qb)} + \sqrt{{{_f(qb)}^2 + 4 \times {_f(qa)}}}}}{{2 \times {_f(qa)}}}", engine, "-")]
            entries.append({"label": label, "stated": g["stated"], "plies": g["plies"], "ratio": float(engine), "mode": mode, "equations": lines})
        finite = [e for e in entries if math.isfinite(e["ratio"])]
        if not finite:
            continue
        first = min(finite, key=lambda e: (e["ratio"], e["plies"][0]))
        tied = [e for e in finite if abs(e["ratio"] - first["ratio"]) <= CLOSES * first["ratio"]]
        failure[criterion] = {"entries": entries, "coefficients": coefficient_lines, "ratio": first["ratio"], "mode": first["mode"],
                              "stated": first["stated"], "plies": sorted(p for e in tied for p in e["plies"]), "angles": [e["stated"] for e in tied]}
    if not failure:
        return out
    applied = out["state"]["applied"]
    symbol, unit = ("u", lab["length"]) if check.control == "displacement" else ("F", lab["force"])
    texts = {"max_stress": ("Each stress against its own strength, the tensile or compressive one by the stress's sign: $`R`$ is the factor on "
                            "the loading at which that stress reaches its strength, and the smallest governs. A stress that is zero sets no limit."),
             "tsai_hill": ("The three stresses in one expression, with the tensile or compressive strengths by the signs of $`\\sigma_1`$ and "
                           "$`\\sigma_2`$: the ply fails when $`\\mathrm{FI}`$ reaches 1. $`\\mathrm{FI}`$ grows with the square of the loading, "
                           "so $`R = 1/\\sqrt{\\mathrm{FI}}`$."),
             "tsai_wu": ("One quadratic in the stresses, its coefficients from the five strengths and the interaction term "
                         f"$`f_{{12}}^* = {tex(given(f12_star)) if f12_star is not None else ''}`$ the material states. Scaling the stresses by "
                         "$`R`$, failure is $`a R^2 + b R = 1`$, whose positive root is $`R`$.")}
    for criterion, f in failure.items():
        steps.append({"id": f"failure_{criterion}", "title": f"First-ply failure by {CRITERION_WORDS[criterion]}", "text": texts[criterion],
                      "coefficients": f["coefficients"], "groups": f["entries"], "equations": [],
                      "source": {"max_stress": "Daniel and Ishai, Chapter 6", "tsai_hill": "Daniel and Ishai, Eq. 6.16",
                                 "tsai_wu": "Daniel and Ishai, Eqs. 6.57 to 6.59"}[criterion]})
    lines = []
    for criterion, f in failure.items():
        words = f"by {CRITERION_WORDS[criterion]}"
        lines.append(_eq(f"{symbol}_{{\\mathrm{{FPF}}}}", rf"R\,{symbol}", rf"{_f(f['ratio'])} \times {_f(applied)}", f["ratio"] * applied, unit, words))
        if check.control == "displacement":
            lines.append(_eq(r"F_{\mathrm{FPF}}", r"R\,F", rf"{_f(f['ratio'])} \times {_f(reaction)}", f["ratio"] * reaction, lab["force"], words))
    steps.append({"id": "first_ply_failure", "title": "The loading at first-ply failure",
                  "text": ("The model is linear, so every stress grows in proportion to the loading, and each criterion's smallest $`R`$ over "
                           "the plies is the factor on the applied loading at which the first ply fails. Below 1, the first ply fails before "
                           "the applied loading is reached."),
                  "equations": lines, "source": "Daniel and Ishai, Eqs. 6.57 to 6.59"})
    out["failure"] = {c: {k: v for k, v in f.items() if k in ("ratio", "mode", "stated", "plies", "angles")} for c, f in failure.items()}
    out["failure_at"] = {"symbol": symbol, "unit": unit, "applied": applied, "reaction": reaction}
    return out
