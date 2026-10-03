"""Solved problems ("cases") checked against the engine.

A case is a dict, usually read from a TOML file in engine/validation/cases: its units, the
inputs (material, laminate, applied), and under "expected" the answers from an independent
source with a relative tolerance. See engine/validation/README.md for the format.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ._validation import finite_vector
from .engineering import engineering_constants
from .failure import first_ply_failure
from .lamina import Lamina, Strengths
from .laminate import Ply, abd_matrices
from .response import Loads, abd_matrix, midplane_response, ply_surfaces, prescribed_curvature_response
from .rotation import strain_transformation, stress_transformation
from .units import UNIT_SYSTEMS

APPLIED_KINDS = ("loads", "stress", "strains", "local_stress", "local_strain", "forces_curvature")
STRENGTH_NAMES = ("F1t", "F1c", "F2t", "F2c", "F6")
LOAD_NAMES = ("Nx", "Ny", "Nxy", "Mx", "My", "Mxy")
_INDEX = {"1": 0, "2": 1, "6": 2}


def load_case(path: Path) -> dict:
    """Read one case file."""
    case = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    validate_case_inputs(case)
    return case


def _fields(value: dict, name: str, required: set[str], optional: set[str]) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a table")
    missing, unknown = required - value.keys(), value.keys() - required - optional
    if missing or unknown:
        raise ValueError(f"{name}: missing fields {sorted(missing)}; unknown fields {sorted(unknown)}")


def validate_case_inputs(case: dict) -> None:
    """Reject incomplete or misspelled case inputs before converting units or solving."""
    _fields(case, "case", {"units", "material", "laminate", "applied"}, {"title", "source", "expected", "f12_star"})
    if case["units"] not in UNIT_SYSTEMS:
        raise ValueError(f"units must be one of {tuple(UNIT_SYSTEMS)}")
    material = case["material"]
    _fields(material, "material", {"E1", "E2", "G12", "nu12"}, set(STRENGTH_NAMES))
    supplied = set(STRENGTH_NAMES) & material.keys()
    if supplied and supplied != set(STRENGTH_NAMES):
        raise ValueError("material needs either all five strengths or none")
    _fields(case["laminate"], "laminate", {"layup", "ply_thickness"}, set())
    angles = np.asarray(case["laminate"]["layup"], dtype=float)
    if angles.ndim != 1 or not angles.size or not np.all(np.isfinite(angles)):
        raise ValueError("laminate.layup must be a nonempty vector of finite angles")
    _fields(case["applied"], "applied", set(), set(APPLIED_KINDS))
    if len(case["applied"]) != 1:
        raise ValueError(f"[applied] needs exactly one of {APPLIED_KINDS}")
    kind, values = next(iter(case["applied"].items()))
    finite_vector(values, f"applied.{kind}", 6 if kind in ("loads", "strains", "forces_curvature") else 3)
    if "f12_star" in case and not -1 < case["f12_star"] < 1:
        raise ValueError("f12_star must be finite and strictly between -1 and 1")


def engine_results(case: dict) -> dict:
    """Everything the case's inputs determine, in the case's units, as {key: (value, scale)}.

    The scale is the largest magnitude in the same group of results, used to judge
    expected values of zero.
    """
    validate_case_inputs(case)
    units = UNIT_SYSTEMS[case["units"]]

    def si(value, kind):
        return np.asarray(value, dtype=float) * units[kind][0]

    def shown(value_si, kind):
        return np.asarray(value_si) / units[kind][0]

    m = case["material"]
    strengths = None
    if all(name in m for name in STRENGTH_NAMES):
        strengths = Strengths(**{name: float(si(m[name], "stress")) for name in STRENGTH_NAMES})
    material = Lamina(
        E1=float(si(m["E1"], "modulus")), E2=float(si(m["E2"], "modulus")),
        G12=float(si(m["G12"], "modulus")), nu12=m["nu12"], strengths=strengths,
    )
    layup = case["laminate"]["layup"]
    thickness = float(si(case["laminate"]["ply_thickness"], "length"))
    plies = [Ply(material=material, angle_deg=angle, thickness_m=thickness) for angle in layup]
    h = thickness * len(plies)

    applied = case["applied"]
    kinds = [kind for kind in APPLIED_KINDS if kind in applied]
    if len(kinds) != 1:
        raise ValueError(f"[applied] needs exactly one of {APPLIED_KINDS}, found {list(applied)}")
    kind, value = kinds[0], applied[kinds[0]]
    single_angle = len(set(layup)) == 1
    if kind.startswith("local") and not single_angle:
        raise ValueError("local_stress and local_strain need a layup with a single angle")

    if kind in ("loads", "stress", "local_stress"):
        if kind == "loads":
            resultants = np.concatenate([si(value[:3], "N"), si(value[3:], "M")])
        else:
            stress = si(value, "stress")
            if kind == "local_stress":
                stress = stress_transformation(-layup[0]) @ stress  # rotating back by -theta: local to global
            resultants = np.concatenate([stress * h, np.zeros(3)])
        loads = Loads(**dict(zip(LOAD_NAMES, resultants)))
        eps0, kappa = midplane_response(plies, loads)
    elif kind == "forces_curvature":
        forces, kappa = si(value[:3], "N"), si(value[3:], "kappa")
        constrained = prescribed_curvature_response(plies, forces, kappa)
        eps0 = constrained.midplane_strain
        loads = Loads(**dict(zip(LOAD_NAMES, np.concatenate([forces, constrained.moments]))))
    else:
        if kind == "strains":
            eps0, kappa = np.asarray(value[:3], dtype=float), si(value[3:], "kappa")
        else:
            eps0, kappa = strain_transformation(-layup[0]) @ np.asarray(value, dtype=float), np.zeros(3)
        loads = Loads(**dict(zip(LOAD_NAMES, abd_matrix(plies) @ np.concatenate([eps0, kappa]))))

    results = {}
    for name, matrix in zip("ABD", abd_matrices(plies)):
        values = shown(matrix, name)
        for i in "126":
            for j in "126":
                results[f"{name}{i}{j}"] = (values[_INDEX[i], _INDEX[j]], np.abs(values).max())
    results["strain_global"] = (eps0, np.abs(eps0).max())
    results["curvature"] = (shown(kappa, "kappa"), np.abs(shown(kappa, "kappa")).max())
    moments = shown(loads.as_vector()[3:], "M")
    results["moments"] = (moments, np.abs(moments).max())

    if single_angle and not np.any(kappa):
        # One fiber direction and no bending: every ply face carries the same state.
        face = ply_surfaces(plies, eps0, kappa)[0]
        for key, vector, quantity in (("strain_local", face.strain_12, None),
                                      ("stress_global", face.stress_xy, "stress"),
                                      ("stress_local", face.stress_12, "stress")):
            vector = shown(vector, quantity) if quantity else vector
            results[key] = (vector, np.abs(vector).max())

    constants = engineering_constants(plies)
    for key in ("Ex", "Ey", "Gxy"):
        results[key] = (shown(getattr(constants, key), "modulus"), 0.0)
    results["nu_xy"] = (constants.nu_xy, 0.0)
    results["nu_yx"] = (constants.nu_yx, 0.0)

    if strengths is not None and np.any(loads.as_vector()):
        results["fpf_ratio_max_stress"] = (first_ply_failure(plies, loads).strength_ratio, 0.0)
        if "f12_star" in case:
            tsai_wu = first_ply_failure(plies, loads, "tsai_wu", case["f12_star"])
            results["fpf_ratio_tsai_wu"] = (tsai_wu.strength_ratio, 0.0)
    return results


@dataclass(frozen=True)
class Comparison:
    """One expected value next to the engine's value."""

    key: str
    expected: float
    engine: float
    allowed: float  # largest accepted absolute difference

    @property
    def agrees(self) -> bool:
        return abs(self.engine - self.expected) <= self.allowed


def compare(case: dict) -> tuple[list[Comparison], list[str]]:
    """Every expected value next to the engine's, plus problems with keys the case cannot produce."""
    expected = dict(case["expected"])
    tolerance = expected.pop("tolerance")
    results = engine_results(case)
    comparisons, problems = [], []
    for key, value in expected.items():
        if key not in results:
            problems.append(f"{key}: not a result this case can produce; available: {', '.join(results)}")
            continue
        computed, scale = results[key]
        want, got = np.atleast_1d(np.asarray(value, dtype=float)), np.atleast_1d(computed)
        if want.shape != got.shape:
            problems.append(f"{key}: expected {want.size} values, the engine gives {got.size}")
            continue
        for k, (w, g) in enumerate(zip(want, got)):
            label = key if want.size == 1 else f"{key}[{k}]"
            allowed = tolerance * (abs(w) if w != 0 else scale)
            comparisons.append(Comparison(label, float(w), float(g), float(allowed)))
    return comparisons, problems


def disagreements(case: dict) -> list[str]:
    """Plain-language list of every expected value the engine does not reproduce."""
    comparisons, problems = compare(case)
    mismatches = [f"{c.key}: expected {c.expected:.6g}, engine gives {c.engine:.6g}" for c in comparisons if not c.agrees]
    return problems + mismatches
