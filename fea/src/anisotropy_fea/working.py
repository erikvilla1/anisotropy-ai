"""The working behind an answer (ADR-0103): for the first ply to fail by each criterion, the chain from the ply's strain to the loading
at first-ply failure, each step as its formula, the values put in, and the result. Every number here is this package's or the engine's:
the strain and the stress are the solve's own at that ply of that element, the stiffness is the engine's `reduced_stiffness`, the
strength ratio is the engine's criterion function called again on that stress. A step is written only when it closes: the stress
recomputed from the strain equals the solve's, and the ratio recomputed from the stress equals the reported factor. A chain that does
not close is left out, so the page never shows working that does not give the answer beside it.

The values put in are written to GIVEN_DIGITS significant figures and the results to the fact sheet's DIGITS, so a reader who repeats
a step on a calculator meets the result at the digits shown. The formulas are LaTeX, as the page typesets them.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from anisotropy_engine.failure import max_stress_ratio, tsai_hill_index, tsai_hill_ratio
from anisotropy_engine.lamina import reduced_stiffness

from .explain import DIGITS, MODE_WORDS, printed
from .recovery import FACES, PlyField
from .units import UNIT_LABEL, from_si

GIVEN_DIGITS = 6
CLOSES = 1e-9  # relative: a recomputed value equals the solve's
NEGLIGIBLE = 1e-9  # a stress component below this share of the ply's largest sets no limit worth a line
WORKED = ("max_stress", "tsai_hill")  # the criteria whose working is written; another criterion has none yet
SOURCES = {
    "strain": "Finite element theory, 6. Ply stresses in material axes",
    "stress": "Laminate theory, 1. Ply stiffness",
    "criterion": "Laminate theory, 5. Failure",
    "loading": "Finite element theory, 7. First-ply failure",
}
APPLIED_SYMBOL = {"displacement": "u", "force": "F", "pressure": "p"}


def given(value: float) -> float:
    """A value put into a formula, as written: GIVEN_DIGITS significant figures."""
    if value == 0 or not math.isfinite(value):
        return value
    return float(f"{value:.{GIVEN_DIGITS - 1}e}")


def tex(value: float, digits: int = GIVEN_DIGITS) -> str:
    """A number as the formulas write it: plain decimals between 1e-4 and 1e7, a power of ten outside."""
    if value == 0:
        return "0"
    mantissa, exponent = f"{value:.{digits - 1}e}".split("e")
    power = int(exponent)
    if -4 <= power < 7:
        return np.format_float_positional(float(f"{value:.{digits - 1}e}"), trim="-")
    return f"{np.format_float_positional(float(mantissa), trim='-')} \\times 10^{{{power}}}"


def factor_tex(value: float) -> str:
    """A number as a factor of a product: a negative one in brackets."""
    return f"({tex(value)})" if value < 0 else tex(value)


def settled(values: np.ndarray) -> np.ndarray:
    """A state as it is written: a component that is zero to the solver's precision, below NEGLIGIBLE of the largest, is zero."""
    values = np.asarray(values, dtype=float)
    return np.where(np.abs(values) <= NEGLIGIBLE * float(np.max(np.abs(values))), 0.0, values)


def _row(symbol: str, value: float, unit: str, what: str) -> dict[str, Any]:
    return {"symbol": symbol, "value": given(value), "unit": unit, "what": what}


def _equation(formula: str, substituted: str, symbol: str, value: float, unit: str) -> dict[str, Any]:
    return {"formula": formula, "substituted": f"{substituted} = {tex(value, DIGITS)}", "result": {"symbol": symbol, "value": printed(value), "unit": unit}}


def _strain_step(strain: np.ndarray, where: str) -> dict[str, Any]:
    return {"id": "strain", "title": "The ply's strain in its fibre axes", "source": SOURCES["strain"],
            "text": f"The solve's strain at {where}, turned into the ply's fibre axes. The probe table shows the same three values.",
            "given": [_row(r"\varepsilon_1", strain[0], "-", "strain along the fibres"), _row(r"\varepsilon_2", strain[1], "-", "strain across the fibres"),
                      _row(r"\gamma_{12}", strain[2], "-", "engineering shear strain")],
            "equations": []}


def _stress_step(q: np.ndarray, strain: np.ndarray, stress: np.ndarray, unit: str) -> dict[str, Any]:
    e1, e2, g12 = (float(v) for v in strain)
    return {"id": "stress", "title": "The ply's stress from its strain", "source": SOURCES["stress"],
            "text": "The ply's stiffness in its fibre axes, from its elastic constants, times the strain.",
            "given": [_row("Q_{11}", q[0, 0], unit, "stiffness along the fibres"), _row("Q_{12}", q[0, 1], unit, "coupling of the two directions"),
                      _row("Q_{22}", q[1, 1], unit, "stiffness across the fibres"), _row("G_{12}", q[2, 2], unit, "in-plane shear modulus")],
            "equations": [
                _equation(r"\sigma_1 = Q_{11}\,\varepsilon_1 + Q_{12}\,\varepsilon_2",
                          rf"\sigma_1 = {factor_tex(given(q[0, 0]))} \times {factor_tex(given(e1))} + {factor_tex(given(q[0, 1]))} \times {factor_tex(given(e2))}",
                          r"\sigma_1", float(stress[0]), unit),
                _equation(r"\sigma_2 = Q_{12}\,\varepsilon_1 + Q_{22}\,\varepsilon_2",
                          rf"\sigma_2 = {factor_tex(given(q[0, 1]))} \times {factor_tex(given(e1))} + {factor_tex(given(q[1, 1]))} \times {factor_tex(given(e2))}",
                          r"\sigma_2", float(stress[1]), unit),
                _equation(r"\tau_{12} = G_{12}\,\gamma_{12}", rf"\tau_{{12}} = {factor_tex(given(q[2, 2]))} \times {factor_tex(given(g12))}", r"\tau_{12}", float(stress[2]), unit),
            ]}


def _max_stress_step(stress: np.ndarray, strengths: dict[str, float], factor: float, mode: str, unit: str) -> dict[str, Any]:
    s1, s2, t12 = (float(v) for v in stress)
    rows: list[dict[str, Any]] = []
    equations: list[dict[str, Any]] = []
    names: list[str] = []
    skipped: list[str] = []
    for value, symbol, tension, compression, index, words in ((s1, r"\sigma_1", "F1t", "F1c", "1", "along the fibres"), (s2, r"\sigma_2", "F2t", "F2c", "2", "across the fibres")):
        if value == 0:
            skipped.append(symbol)
            continue
        key = tension if value > 0 else compression
        f = rf"F_{{{key[1:]}}}"
        rows.append(_row(f, strengths[key], unit, f"{'tensile' if value > 0 else 'compressive'} strength {words}"))
        top = f"{f}}}{{{symbol}" if value > 0 else f"{f}}}{{-{symbol}"
        equations.append(_equation(rf"R_{index} = \frac{{{top}}}", rf"R_{index} = \frac{{{tex(given(strengths[key]))}}}{{{tex(given(abs(value)))}}}", f"R_{index}",
                                   strengths[key] / abs(value), "-"))
        names.append(f"R_{index}")
    if t12 != 0:
        rows.append(_row("F_6", strengths["F6"], unit, "in-plane shear strength"))
        equations.append(_equation(r"R_6 = \frac{F_6}{|\tau_{12}|}", rf"R_6 = \frac{{{tex(given(strengths['F6']))}}}{{{tex(given(abs(t12)))}}}", "R_6", strengths["F6"] / abs(t12), "-"))
        names.append("R_6")
    else:
        skipped.append(r"\tau_{12}")
    equations.append({"formula": rf"R = \min({', '.join(names)})", "substituted": rf"R = {tex(factor, DIGITS)}", "result": {"symbol": "R", "value": printed(factor), "unit": "-"}})
    equations.append(_shown_index(factor))
    step = {"id": "criterion", "title": "The maximum stress criterion", "source": SOURCES["criterion"],
            "text": f"Each stress against its own strength; the smallest ratio governs: {MODE_WORDS.get(mode, mode)}. "
                    "The failure index the results show is 1/R.",
            "given": rows, "equations": equations}
    if skipped:
        step["note"] = "A stress that is zero sets no limit and is left out."
        step["skipped"] = skipped
    return step


def _tsai_hill_step(stress: np.ndarray, strengths: dict[str, float], index: float, factor: float, unit: str) -> dict[str, Any]:
    s1, s2, t12 = (float(v) for v in stress)
    x_key, y_key = ("F1c" if s1 < 0 else "F1t"), ("F2c" if s2 < 0 else "F2t")
    x, y, s = strengths[x_key], strengths[y_key], strengths["F6"]
    g1, g2, g6 = given(s1), given(s2), given(t12)
    terms = [(s1 / x) ** 2, -(s1 * s2) / x**2, (s2 / y) ** 2, (t12 / s) ** 2]
    parts = " ".join(("- " if t < 0 else "+ ") + tex(abs(t), DIGITS) for t in terms[1:])
    return {"id": "criterion", "title": "The Tsai-Hill criterion", "source": SOURCES["criterion"],
            "text": "The three stresses in one expression, with the tensile or compressive strength by the sign of each stress. The laminate fails when the sum reaches one.",
            "given": [_row("X", x, unit, f"{'compressive' if s1 < 0 else 'tensile'} strength along the fibres, F{x_key[1:]}"),
                      _row("Y", y, unit, f"{'compressive' if s2 < 0 else 'tensile'} strength across the fibres, F{y_key[1:]}"),
                      _row("F_6", s, unit, "in-plane shear strength")],
            "equations": [
                {"formula": r"\mathrm{FI} = \left(\frac{\sigma_1}{X}\right)^2 - \frac{\sigma_1\,\sigma_2}{X^2} + \left(\frac{\sigma_2}{Y}\right)^2 + \left(\frac{\tau_{12}}{F_6}\right)^2",
                 "substituted": (rf"\mathrm{{FI}} = \left(\frac{{{tex(g1)}}}{{{tex(given(x))}}}\right)^2 - \frac{{{factor_tex(g1)} \times {factor_tex(g2)}}}{{{tex(given(x))}^2}}"
                                 rf" + \left(\frac{{{tex(g2)}}}{{{tex(given(y))}}}\right)^2 + \left(\frac{{{tex(g6)}}}{{{tex(given(s))}}}\right)^2"),
                 "result": None},
                {"formula": None, "substituted": rf"\mathrm{{FI}} = {tex(terms[0], DIGITS)} {parts} = {tex(index, DIGITS)}",
                 "result": {"symbol": r"\mathrm{FI}", "value": printed(index), "unit": "-"}},
                _equation(r"R = \frac{1}{\sqrt{\mathrm{FI}}}", rf"R = \frac{{1}}{{\sqrt{{{tex(given(index))}}}}}", "R", factor, "-"),
                _shown_index(factor, index),
            ],
            "note": "FI here is the Tsai-Hill sum. The failure index the results show is 1/R, the square root of this sum: both reach one at the "
                    "same loading."}


def _shown_index(factor: float, tsai_hill_sum: float | None = None) -> dict[str, Any]:
    """The failure index the results show, 1/R (ADR-0103 amendment 2): for maximum stress the largest stress over its strength, for
    Tsai-Hill the square root of its sum. Written in the working so that "the failure index" means the number on the page."""
    if tsai_hill_sum is None:
        return _equation(r"\frac{1}{R}", rf"\frac{{1}}{{R}} = \frac{{1}}{{{tex(given(factor))}}}", "1/R", 1.0 / factor, "-")
    return _equation(r"\frac{1}{R} = \sqrt{\mathrm{FI}}", rf"\frac{{1}}{{R}} = \sqrt{{{tex(given(tsai_hill_sum))}}}", "1/R", 1.0 / factor, "-")


def _loading_step(factor: float, applied: dict[str, Any], reaction: dict[str, Any], at: dict[str, Any]) -> dict[str, Any]:
    symbol = APPLIED_SYMBOL.get(applied["control"], "u")
    a, r = abs(float(applied["value"])), abs(float(reaction["value"]))
    equations = [_equation(rf"{symbol}_{{\mathrm{{FPF}}}} = R\,{symbol}", rf"{symbol}_{{\mathrm{{FPF}}}} = {tex(given(factor))} \times {tex(given(a))}",
                           rf"{symbol}_{{\mathrm{{FPF}}}}", abs(float(at["applied"])), at["unit"])]
    rows = [_row("R", factor, "-", "the factor at first-ply failure"), _row(symbol, a, applied["unit"], f"the applied {applied['control']}")]
    if applied["control"] != "force":  # under a stated force the reaction is that force
        rows.append(_row(r"F_{\mathrm{reaction}}", r, at["reaction_unit"], f"the reaction at {reaction.get('set', 'the top grip')}"))
        equations.append(_equation(r"F_{\mathrm{FPF}} = R\,F_{\mathrm{reaction}}", rf"F_{{\mathrm{{FPF}}}} = {tex(given(factor))} \times {tex(given(r))}",
                                   r"F_{\mathrm{FPF}}", abs(float(at["reaction"])), at["reaction_unit"]))
    return {"id": "loading", "title": "The loading at first-ply failure", "source": SOURCES["loading"],
            "text": "The model is linear, so every stress grows with the loading: the first ply fails at the factor times what is applied.",
            "given": rows, "equations": equations}


def working_of(solution: Any, field: PlyField, summary: dict[str, Any], units: str) -> dict[str, Any] | None:
    """The working of the answer `summary` gives, by criterion, on the verdict's basis; None for a result with none to show (an
    isotropic part, or no criterion worked here). `field` is the solve's ply states, SI; `summary` is `field_data`'s, in `units`."""
    if summary.get("isotropic"):
        return None
    verdict = summary.get("verdict")
    basis = verdict["basis"] if verdict and verdict["basis"] in ("gauge", "away") else "whole"  # a plate away from its held corners (ADR-0108 am. 2)
    table = summary.get({"gauge": "fpf_gauge", "away": "fpf_away"}[basis], {}) if basis != "whole" else summary["fpf"]
    mesh = solution.mesh
    lab = UNIT_LABEL[units]
    unit = lab["stress"]
    out: dict[str, Any] = {}
    for criterion, entry in table.items():
        if criterion not in WORKED:
            continue
        e, k = int(entry["element"]), int(entry["ply"]) - 1
        material = mesh.sections[mesh.element_section[e]].plies[k].material
        if material.strengths is None:
            continue
        strain_si, stress_si = np.asarray(field.strain_12[e][k], dtype=float), np.asarray(field.stress_12[e][k], dtype=float)
        if field.faces is not None:  # a shell state: the face that fails first
            face = FACES.index(entry["face"])
            strain_si, stress_si = strain_si[face], stress_si[face]
        q_si = reduced_stiffness(material)
        scale = float(np.max(np.abs(stress_si)))
        if scale == 0 or not np.allclose(q_si @ strain_si, stress_si, rtol=0, atol=1e-6 * scale):
            continue  # the stress is not this stiffness times this strain (a state this working does not cover): no working, never a wrong one
        factor = float(entry["factor"])
        again = max_stress_ratio(stress_si, material.strengths)[0] if criterion == "max_stress" else tsai_hill_ratio(stress_si, material.strengths)
        if not math.isfinite(again) or abs(again - factor) > CLOSES * abs(factor):
            continue
        stress, strain = settled(from_si(stress_si, "stress", units)), settled(strain_si)
        q = from_si(q_si, "stress", units)
        strengths = {name: float(from_si(getattr(material.strengths, name), "stress", units)) for name in ("F1t", "F1c", "F2t", "F2c", "F6")}
        label = str(entry["label"]).rsplit(".", 1)[-1]
        where = f"ply {entry['ply']} ({printed(float(entry['angle'])):g}°), element {label}" + (f", {entry['face']} face" if entry.get("face") else "")
        steps = [_strain_step(strain, where), _stress_step(q, strain, stress, unit)]
        if criterion == "max_stress":
            steps.append(_max_stress_step(stress, strengths, factor, entry["mode"], unit))
        else:
            steps.append(_tsai_hill_step(stress, strengths, float(tsai_hill_index(stress_si, material.strengths)), factor, unit))
        if entry.get("at_failure"):
            steps.append(_loading_step(factor, summary["applied"], summary["reaction"], entry["at_failure"]))
        out[criterion] = {"ply": int(entry["ply"]), "angle": float(entry["angle"]), "element": label, "face": entry.get("face"), "where": where,
                          "factor": printed(factor), "steps": steps}
    if not out:
        return None
    return {"basis": basis, "digits": {"given": GIVEN_DIGITS, "result": DIGITS}, "criteria": out}
