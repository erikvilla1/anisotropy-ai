"""Runs every case in engine/validation/cases against the engine.

Each case states its inputs and the answers from an independent source (a textbook, an
answer key, later lab measurements). A case fails when the engine and the source disagree
by more than the case's tolerance. See engine/validation/README.md.
"""

import tomllib
from pathlib import Path

import numpy as np
import pytest

from anisotropy_engine.engineering import engineering_constants
from anisotropy_engine.failure import first_ply_failure
from anisotropy_engine.lamina import Lamina, Strengths
from anisotropy_engine.laminate import Ply, abd_matrices
from anisotropy_engine.response import Loads, abd_matrix, midplane_response, ply_surfaces
from anisotropy_engine.rotation import strain_transformation, stress_transformation
from anisotropy_engine.units import UNIT_SYSTEMS

CASE_DIR = Path(__file__).parents[1] / "validation" / "cases"
CASES = sorted(path for path in CASE_DIR.glob("*.toml") if not path.name.startswith("_"))
APPLIED_KINDS = ("loads", "stress", "strains", "local_stress", "local_strain")
STRENGTH_NAMES = ("F1t", "F1c", "F2t", "F2c", "F6")
INDEX = {"1": 0, "2": 1, "6": 2}


def engine_results(case):
    """Everything the case's inputs determine, in the case's units, as {key: (value, scale)}.

    The scale is the largest magnitude in the same group, used to judge expected zeros.
    """
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
    assert len(kinds) == 1, f"[applied] needs exactly one of {APPLIED_KINDS}, found {list(applied)}"
    kind, value = kinds[0], applied[kinds[0]]
    single_angle = len(set(layup)) == 1
    assert single_angle or not kind.startswith("local"), "local_stress and local_strain need a single-angle layup"

    if kind in ("loads", "stress", "local_stress"):
        if kind == "loads":
            resultants = np.concatenate([si(value[:3], "N"), si(value[3:], "M")])
        else:
            stress = si(value, "stress")
            if kind == "local_stress":
                stress = stress_transformation(-layup[0]) @ stress
            resultants = np.concatenate([stress * h, np.zeros(3)])
        loads = Loads(**dict(zip(["Nx", "Ny", "Nxy", "Mx", "My", "Mxy"], resultants)))
        eps0, kappa = midplane_response(plies, loads)
    else:
        if kind == "strains":
            eps0, kappa = np.asarray(value[:3], dtype=float), si(value[3:], "kappa")
        else:
            eps0, kappa = strain_transformation(-layup[0]) @ np.asarray(value, dtype=float), np.zeros(3)
        resultants = abd_matrix(plies) @ np.concatenate([eps0, kappa])
        loads = Loads(**dict(zip(["Nx", "Ny", "Nxy", "Mx", "My", "Mxy"], resultants)))

    results = {}
    for name, matrix in zip("ABD", abd_matrices(plies)):
        values = shown(matrix, name)
        for i in "126":
            for j in "126":
                results[f"{name}{i}{j}"] = (values[INDEX[i], INDEX[j]], np.abs(values).max())
    results["strain_global"] = (eps0, np.abs(eps0).max())
    results["curvature"] = (shown(kappa, "kappa"), np.abs(shown(kappa, "kappa")).max())

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


def disagreements(case):
    """Plain-language list of every expected value the engine does not reproduce."""
    expected = dict(case["expected"])
    tolerance = expected.pop("tolerance")
    results = engine_results(case)
    problems = []
    for key, value in expected.items():
        if key not in results:
            problems.append(f"{key}: not a result this case can produce; available: {', '.join(results)}")
            continue
        computed, scale = results[key]
        want, got = np.atleast_1d(np.asarray(value, dtype=float)), np.atleast_1d(computed)
        if want.shape != got.shape:
            problems.append(f"{key}: expected {want.size} values, the engine gives {got.size}")
            continue
        for w, g in zip(want, got):
            allowed = tolerance * (abs(w) if w != 0 else scale)
            if not abs(g - w) <= allowed:
                problems.append(f"{key}: expected {w:.6g}, engine gives {g:.6g}")
    return problems


@pytest.mark.parametrize("path", CASES, ids=[path.stem for path in CASES])
def test_engine_reproduces_the_case(path):
    case = tomllib.loads(path.read_text(encoding="utf-8"))
    for field in ("title", "source", "units"):
        assert field in case, f"{path.name} is missing {field}"
    problems = disagreements(case)
    assert not problems, f"{case['title']}\nSource: {case['source']}\n" + "\n".join(problems)


def test_a_wrong_expected_value_is_reported():
    # Guards the runner itself: a deliberately wrong answer must not pass.
    case = tomllib.loads((CASE_DIR / "daniel-ishai-problem-7-11.toml").read_text(encoding="utf-8"))
    case["expected"]["A11"] = 61.0
    assert disagreements(case) == ["A11: expected 61, engine gives 60.2447"]


def test_an_unknown_result_key_is_reported():
    case = tomllib.loads((CASE_DIR / "daniel-ishai-problem-7-11.toml").read_text(encoding="utf-8"))
    case["expected"]["A99"] = 1.0
    assert disagreements(case)[0].startswith("A99: not a result this case can produce")
