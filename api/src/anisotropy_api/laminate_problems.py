"""A laminate problem as an engineer states it (ADR-0060): each value with the unit it was typed in, the stack as a list of
angles, the six loads per unit width, and the system the answer is reported in.

This module converts every value with the engine's unit table, builds the case the engine's case runner solves (the format of
ADR-0024), and words the result from the engine's numbers for the chat, the way the fea package words a coupon's result for the
assistant (ADR-0052). Nothing here computes a laminate quantity: the engine does, and the sentences quote its numbers.
"""

from __future__ import annotations

import math
from typing import Any

from anisotropy_engine.cases import LOAD_NAMES, STRENGTH_NAMES, CaseSolution
from anisotropy_engine.failure import FirstPlyFailure
from anisotropy_engine.summary import LaminateSummary
from anisotropy_engine.units import UNIT_SYSTEMS, in_system

from .schemas import LaminateProblem, LibraryChoice, Quantity

LOAD_KINDS = {"Nx": "N", "Ny": "N", "Nxy": "N", "Mx": "M", "My": "M", "Mxy": "M"}
REPORTED_KINDS = ("modulus", "stress", "length", "N", "M", "kappa", "A", "B", "D", "areal_mass")
CRITERION_WORDS = {"max_stress": "maximum stress", "max_strain": "maximum strain", "tsai_hill": "Tsai-Hill", "tsai_wu": "Tsai-Wu"}
# The engine's own mode words (failure.max_stress_ratio), and the stress component and strength each one compares.
MODE_COMPONENTS = {"longitudinal tension": ("sigma1", "F1t"), "longitudinal compression": ("sigma1", "F1c"),
                   "transverse tension": ("sigma2", "F2t"), "transverse compression": ("sigma2", "F2c"), "in-plane shear": ("tau12", "F6")}
RELATIVE_ZERO = 1e-9  # the summary's tolerance (ADR-0059): roundoff of a symmetric stack is not a curvature


def _converted(quantity: Quantity, kind: str, system: str, field: str) -> float:
    """One typed value in the reporting system's unit for its kind; a refusal names the field."""
    try:
        return in_system(quantity.value, quantity.unit, kind, system)
    except ValueError as error:
        raise ValueError(f"{field}: {error}") from None


def case_of(problem: LaminateProblem) -> dict[str, Any]:
    """The case the engine solves, in the reporting system's units, from the problem's typed values."""
    system = problem.report_units
    material: dict[str, Any]
    if isinstance(problem.material, LibraryChoice):
        material = {"library": problem.material.library}
        if problem.material.dataset is not None:
            material["dataset"] = problem.material.dataset
    else:
        own = problem.material
        material = {"E1": _converted(own.E1, "modulus", system, "material.E1"), "E2": _converted(own.E2, "modulus", system, "material.E2"),
                    "G12": _converted(own.G12, "modulus", system, "material.G12"), "nu12": own.nu12}
        if own.F1t is not None:
            for name in STRENGTH_NAMES:
                material[name] = _converted(getattr(own, name), "stress", system, f"material.{name}")
    if problem.material.strain_limits is not None:  # a stated choice, not a value: maximum strain with limits from the strengths (ADR-0021)
        material["strain_limits"] = problem.material.strain_limits
    laminate: dict[str, Any] = {"layup": [float(angle) for angle in problem.layup]}
    if problem.ply_thickness is not None:
        laminate["ply_thickness"] = _converted(problem.ply_thickness, "length", system, "ply_thickness")
    loads = [_converted(getattr(problem.loads, name), LOAD_KINDS[name], system, f"loads.{name}") for name in LOAD_NAMES]
    case: dict[str, Any] = {"title": problem.title or "A laminate problem stated in the chat", "units": system,
                            "material": material, "laminate": laminate, "applied": {"loads": loads}}
    if problem.f12_star is not None:
        case["f12_star"] = problem.f12_star
    return case


def unit_labels(system: str) -> dict[str, str]:
    """The unit of each reported kind in a reporting system, for the page to print beside the numbers."""
    return {kind: UNIT_SYSTEMS[system][kind][1] for kind in REPORTED_KINDS}


def printed(value: float, figures: int = 4) -> float:
    """A number as the sentences print it: four significant figures, so a fact and its mention agree digit for digit."""
    if value == 0 or not math.isfinite(value):
        return value
    return float(f"{value:.{figures - 1}e}")


def _is_zero(value: float, scale: float) -> bool:
    return abs(value) <= RELATIVE_ZERO * scale


def facts_of(case: dict[str, Any], results: dict[str, Any], solution: CaseSolution, failures: dict[str, FirstPlyFailure],
             summary: LaminateSummary) -> dict[str, Any]:
    """The fact sheet the sentences quote and the number guard checks against (ADR-0052): every number in the reporting
    system's units, printed to four figures, with the words that go with it. `results` is the engine's dictionary as the case
    runner returns it, in those units."""
    system = case["units"]
    units = unit_labels(system)

    def number(key: str) -> float:
        return float(results[key][0])  # the runner pairs every value with the scale of its group

    strain = [float(v) for v in results["strain_global"][0]]
    kappa = [float(v) for v in results["curvature"][0]]
    # A curvature counts as zero when the bending strain it puts on a face, kappa h/2, is roundoff beside the mid-plane strain:
    # the curvature of a symmetric stack is 1e-16 of nothing, and its own largest entry is no scale (ADR-0059's reasoning for B).
    strain_scale = max(abs(v) for v in strain)
    half_thickness_m = number("total_thickness") * UNIT_SYSTEMS[system]["length"][0] / 2
    kappa_per_m = UNIT_SYSTEMS[system]["kappa"][0]
    facts: dict[str, Any] = {
        "units": units, "ply_count": summary.ply_count, "layup": case["laminate"]["layup"],
        "total_thickness": printed(number("total_thickness")), "kind": summary.kind,
        "symmetric": summary.symmetric, "antisymmetric": summary.antisymmetric, "balanced": summary.balanced,
        "extension_bending_coupling": summary.coupling.extension_bending,
    }
    for name, value in zip(LOAD_NAMES, case["applied"]["loads"]):
        facts[name] = printed(float(value))
    for name, value in zip(("eps_x", "eps_y", "gamma_xy"), strain):
        facts[f"{name}_microstrain"] = 0.0 if _is_zero(value, strain_scale) else printed(value * 1e6)
    for name, value in zip(("kappa_x", "kappa_y", "kappa_xy"), kappa):
        facts[name] = 0.0 if _is_zero(value * kappa_per_m * half_thickness_m, strain_scale) else printed(value)
    for key in ("Ex", "Ey", "Gxy", "nu_xy"):
        facts[key] = printed(number(key))
    material = solution.materials["material"]
    if material.strengths is not None:
        stress_factor = UNIT_SYSTEMS[system]["stress"][0]
        for name in STRENGTH_NAMES:
            facts[name] = printed(getattr(material.strengths, name) / stress_factor)
    facts["criteria"] = list(failures)
    earliest = min(failures, key=lambda c: failures[c].strength_ratio) if failures else None
    facts["earliest"] = earliest
    for criterion, fpf in failures.items():
        governing = fpf.governing
        ratio = float(fpf.strength_ratio)
        facts[f"{criterion}_ratio"] = printed(ratio) if math.isfinite(ratio) else None
        facts[f"{criterion}_ply"] = governing.ply_index + 1
        facts[f"{criterion}_angle"] = printed(float(governing.angle_deg))
        facts[f"{criterion}_mode"] = governing.mode
        stress_factor = UNIT_SYSTEMS[system]["stress"][0]
        for name, value in zip(("sigma1", "sigma2", "tau12"), governing.stress_12):  # the failing face's stresses at failure, R times the applied
            facts[f"{criterion}_{name}_at_failure"] = printed(float(value) / stress_factor)
        failure_loads = fpf.failure_loads.as_vector()
        for name, value, kind in zip(LOAD_NAMES, failure_loads, ("N",) * 3 + ("M",) * 3):
            if not _is_zero(float(value), max(abs(float(v)) for v in failure_loads) or 1.0):
                facts[f"{criterion}_{name}"] = printed(float(value) / UNIT_SYSTEMS[system][kind][0])
    return facts


def _words(value: float | None) -> str:
    """A fact as the sentence writes it: the printed value, four figures, without a trailing .0."""
    if value is None:
        return "unbounded"
    return f"{value:.4g}" if abs(value) >= 1e-3 or value == 0 else f"{value:.3e}"


def _angle(angle: float) -> str:
    return f"{angle:g}"


def sentences_of(facts: dict[str, Any]) -> list[str]:
    """The template's sentences from the fact sheet, for an engineer: what the stack is, how it deforms, how stiff it is, and
    where it fails first. Every number is a fact, written as the sheet prints it."""
    units = facts["units"]
    stacking = "symmetric" if facts["symmetric"] else "antisymmetric" if facts["antisymmetric"] else "unsymmetric"
    balance = "balanced" if facts["balanced"] else "unbalanced"
    layup = "/".join(_angle(a) for a in facts["layup"])
    first = (f"The stack [{layup}] of {facts['ply_count']} plies is {_words(facts['total_thickness'])} {units['length']} thick, "
             f"{facts['kind']}, {stacking} and {balance}"
             + (", so no in-plane load bends it (B = 0)." if not facts["extension_bending_coupling"] else
                "; its B matrix is not zero, so an in-plane load also bends it."))
    applied = [f"{name} = {_words(facts[name])} {units['N' if name.startswith('N') else 'M']}" for name in LOAD_NAMES if facts[name] != 0]
    loads = ", ".join(applied) if applied else "no load"
    strain_words = []
    for name, axis in (("eps_x_microstrain", "x"), ("eps_y_microstrain", "y")):
        value = facts[name]
        sense = "no strain" if value == 0 else "it stretches" if value > 0 else "it shortens"
        strain_words.append(f"eps_{axis} = {_words(value)} microstrain ({sense} along {axis})" if value != 0 else f"eps_{axis} = 0 (no strain along {axis})")
    shear = facts["gamma_xy_microstrain"]
    strain_words.append("gamma_xy = 0 (no shear strain)" if shear == 0 else f"gamma_xy = {_words(shear)} microstrain")
    curvature = [facts[k] for k in ("kappa_x", "kappa_y", "kappa_xy")]
    per = units["kappa"].replace("1/", "per ")  # "1/m" would read as the number 1 to the guard
    curvature_words = ("it does not curve" if all(v == 0 for v in curvature)
                       else "it curves: " + ", ".join(f"{k} = {_words(v)} {per}" for k, v in zip(("kappa_x", "kappa_y", "kappa_xy"), curvature) if v != 0))
    second = f"Under {loads} the mid-plane strain is {', '.join(strain_words)}, and {curvature_words}."
    third = (f"Its in-plane moduli are Ex = {_words(facts['Ex'])} {units['modulus']}, Ey = {_words(facts['Ey'])} {units['modulus']}, "
             f"Gxy = {_words(facts['Gxy'])} {units['modulus']} and nu_xy = {_words(facts['nu_xy'])}.")
    sentences = [first, second, third]
    earliest = facts["earliest"]
    if earliest is None:
        sentences.append("No first-ply failure is predicted: the material has no strengths." if "F1t" not in facts
                         else "No first-ply failure is predicted: no load was applied.")
        return sentences
    ratio = facts[f"{earliest}_ratio"]
    ply, angle, mode = facts[f"{earliest}_ply"], facts[f"{earliest}_angle"], facts[f"{earliest}_mode"]
    at = [f"{name} = {_words(facts[f'{earliest}_{name}'])} {units['N' if name.startswith('N') else 'M']}" for name in LOAD_NAMES if f"{earliest}_{name}" in facts]
    how = f"in {mode}" if mode in MODE_COMPONENTS else "by the interaction of its stresses" if mode == "interactive" else f"in {mode}"
    fourth = (f"By {CRITERION_WORDS[earliest]}, ply {ply} ({_angle(angle)} degrees) fails first, {how}, "
              + (f"when every load reaches {_words(ratio)} times its value: {', '.join(at)}." if ratio is not None and at
                 else "but no face reaches the criterion under these loads." if ratio is None else f"at {_words(ratio)} times the applied loads."))
    sentences.append(fourth)
    # The maximum-stress mode names the stress that limits the ply and the strength it reaches, which an interactive criterion cannot.
    if "max_stress" in facts["criteria"] and facts["max_stress_mode"] in MODE_COMPONENTS and "F1t" in facts:
        component, strength = MODE_COMPONENTS[facts["max_stress_mode"]]
        reaches = f"when its {component} reaches {strength} = {_words(facts[strength])} {units['stress']}"
        if earliest == "max_stress":
            sentences.append(f"That is {reaches}.")
        else:
            which = "that ply" if facts["max_stress_ply"] == ply else f"ply {facts['max_stress_ply']} ({_angle(facts['max_stress_angle'])} degrees)"
            sentences.append(f"By maximum stress {which} fails in {facts['max_stress_mode']}, {reaches}.")
    others = [c for c in facts["criteria"] if c != earliest]
    if others:
        sentences.append("The other criteria give " + ", ".join(
            f"{CRITERION_WORDS[c]} R = {_words(facts[f'{c}_ratio'])} (ply {facts[f'{c}_ply']})" for c in others) + ".")
    return sentences
