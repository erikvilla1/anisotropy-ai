"""Solved problems ("cases") checked against the engine.

A case is a dict, read from a TOML file in engine/validation/cases or from a course Excel
input file: its units, the inputs (materials, laminate, applied), and under "expected" the
answers from an independent source with a relative tolerance. See
engine/validation/README.md for the format.

A laminate of one material uses [material] with a layup and one ply thickness. A laminate
of several materials or ply thicknesses uses named [materials.<name>] tables and a list of
plies, each with its own angle, material and thickness. Plies are listed bottom first.
"""

import math
import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ._validation import finite_vector
from .engineering import engineering_constants
from .failure import first_ply_failure
from .lamina import Lamina, Strengths, ThermalExpansion, reduced_compliance, reduced_stiffness
from .laminate import Ply, abd_matrices
from .response import (
    Loads, PlySurface, PrescribedCurvatureResult, abd_compliance, abd_matrix, midplane_response, ply_surfaces,
    prescribed_curvature_response,
)
from .rotation import strain_transformation, stress_transformation, transformed_compliance, transformed_reduced_stiffness
from .mixed import AVERAGE_STRESSES, DEFORMATIONS, PAIRS, MixedResult, mixed_response
from .thermal import thermal_ply_surfaces, thermal_resultants, thermomechanical_response
from .units import UNIT_SYSTEMS

APPLIED_KINDS = ("loads", "stress", "strains", "local_stress", "local_strain", "forces_curvature", "mixed")
# Case unit kind of each named quantity in [applied.mixed] and in the named scalar results.
QUANTITY_UNITS = {"Nx": "N", "Ny": "N", "Nxy": "N", "Mx": "M", "My": "M", "Mxy": "M",
                  "sigma_x": "stress", "sigma_y": "stress", "tau_xy": "stress",
                  "eps_x": None, "eps_y": None, "gamma_xy": None,
                  "kappa_x": "kappa", "kappa_y": "kappa", "kappa_xy": "kappa"}
STRENGTH_NAMES = ("F1t", "F1c", "F2t", "F2c", "F6")
ALPHA_NAMES = ("alpha1", "alpha2")
ELASTIC_NAMES = ("E1", "E2", "G12", "nu12")
PLY_FIELDS = ("angle", "material", "thickness")
LOAD_NAMES = ("Nx", "Ny", "Nxy", "Mx", "My", "Mxy")
_INDEX = {"1": 0, "2": 1, "6": 2}
# Results with one [3-value] row per ply. Expected values may give every row as a list, or
# only some plies as a table keyed by ply number, where ply 1 is the bottom ply.
PLY_TABLE_KEYS = tuple(f"ply_{quantity}_{axes}{face}" for quantity in ("strain", "stress")
                       for axes in ("global", "local") for face in ("", "_bottom", "_top"))


def load_case(path: Path) -> dict:
    """Read one case file: a TOML case, or a course Excel input file (.xlsx)."""
    path = Path(path)
    if path.suffix.lower() == ".xlsx":
        from .course_excel import read_course_workbook
        case = read_course_workbook(path)
    else:
        case = tomllib.loads(path.read_text(encoding="utf-8"))
    validate_case_inputs(case)
    return case


def _fields(value: dict, name: str, required: set[str], optional: set[str]) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a table")
    missing, unknown = required - value.keys(), value.keys() - required - optional
    if missing or unknown:
        raise ValueError(f"{name}: missing fields {sorted(missing)}; unknown fields {sorted(unknown)}")


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _check_material(table: dict, name: str) -> None:
    _fields(table, name, set(ELASTIC_NAMES), set(STRENGTH_NAMES) | set(ALPHA_NAMES))
    supplied = set(STRENGTH_NAMES) & table.keys()
    if supplied and supplied != set(STRENGTH_NAMES):
        raise ValueError(f"{name} needs either all five strengths or none")
    alphas = set(ALPHA_NAMES) & table.keys()
    if alphas and alphas != set(ALPHA_NAMES):
        raise ValueError(f"{name} needs both alpha1 and alpha2 or neither")


def validate_case_inputs(case: dict) -> None:
    """Reject incomplete or misspelled case inputs before converting units or solving."""
    _fields(case, "case", {"units", "laminate", "applied"},
            {"title", "source", "expected", "f12_star", "material", "materials"})
    if ("material" in case) == ("materials" in case):
        raise ValueError("case needs exactly one of [material] (one material) or [materials.<name>] tables")
    if case["units"] not in UNIT_SYSTEMS:
        raise ValueError(f"units must be one of {tuple(UNIT_SYSTEMS)}")
    laminate = case["laminate"]
    if "material" in case:
        _check_material(case["material"], "material")
        _fields(laminate, "laminate", {"layup", "ply_thickness"}, set())
        angles = np.asarray(laminate["layup"], dtype=float)
        if angles.ndim != 1 or not angles.size or not np.all(np.isfinite(angles)):
            raise ValueError("laminate.layup must be a nonempty vector of finite angles")
        tables = {"material": case["material"]}
        used = ["material"]
    else:
        if not isinstance(case["materials"], dict) or not case["materials"]:
            raise ValueError("[materials] needs at least one named material table")
        for name, table in case["materials"].items():
            _check_material(table, f"materials.{name}")
        _fields(laminate, "laminate", {"plies"}, set())
        plies = laminate["plies"]
        if not isinstance(plies, list) or not plies:
            raise ValueError("laminate.plies must be a nonempty list of plies, bottom ply first")
        for number, ply in enumerate(plies, 1):
            _fields(ply, f"laminate.plies ply {number}", set(PLY_FIELDS), set())
            if not _is_number(ply["angle"]):
                raise ValueError(f"laminate.plies ply {number}: angle must be a finite number of degrees")
            if not _is_number(ply["thickness"]) or ply["thickness"] <= 0:
                raise ValueError(f"laminate.plies ply {number}: thickness must be a positive number")
            if ply["material"] not in case["materials"]:
                raise ValueError(f"laminate.plies ply {number}: material {ply['material']!r} is not in [materials]")
        tables = case["materials"]
        used = list(dict.fromkeys(ply["material"] for ply in plies))
    applied = case["applied"]
    _fields(applied, "applied", set(), set(APPLIED_KINDS) | {"delta_T"})
    kinds = [kind for kind in APPLIED_KINDS if kind in applied]
    if len(kinds) != 1:
        raise ValueError(f"[applied] needs exactly one of {APPLIED_KINDS}, plus delta_T when temperature changes")
    kind = kinds[0]
    if kind == "mixed":
        mixed = applied["mixed"]
        _fields(mixed, "applied.mixed", set(), set(QUANTITY_UNITS))
        for pair in PAIRS:
            given = [name for name in pair if name in mixed]
            if len(given) != 1:
                raise ValueError(f"applied.mixed needs exactly one of {pair}; got {given or 'none'}")
        bad = [name for name, value in mixed.items() if not _is_number(value)]
        if bad:
            raise ValueError(f"applied.mixed: {bad} must be finite numbers")
    else:
        finite_vector(applied[kind], f"applied.{kind}", 6 if kind in ("loads", "strains", "forces_curvature") else 3)
    if "delta_T" in applied:
        if not _is_number(applied["delta_T"]):
            raise ValueError("applied.delta_T must be a finite number (a temperature change)")
        missing = [name for name in used if "alpha1" not in tables[name]]
        if missing:
            where = "[material]" if "material" in case else f"materials {missing}"
            raise ValueError(f"applied.delta_T needs alpha1 and alpha2 in {where}")
    if "f12_star" in case and not -1 < case["f12_star"] < 1:
        raise ValueError("f12_star must be finite and strictly between -1 and 1")
    if "expected" in case:
        tolerance = case["expected"].get("tolerance") if isinstance(case["expected"], dict) else None
        if not _is_number(tolerance) or tolerance <= 0:
            raise ValueError("[expected] needs a positive relative tolerance, for example tolerance = 0.001")


@dataclass(frozen=True)
class CaseSolution:
    """Everything a case's inputs determine, in SI units, for printing or comparison."""

    units: str
    materials: dict[str, Lamina]  # by name; a one-material case uses the name "material"
    ply_materials: list[str]  # material name of each ply, bottom ply first
    plies: list[Ply]
    kind: str  # the [applied] entry
    delta_T: float | None  # K; None when the case gives no temperature change
    N_T: np.ndarray  # thermal resultants, zero without delta_T
    M_T: np.ndarray
    loads: Loads  # mechanical resultants, as given or as solved
    eps0: np.ndarray
    kappa: np.ndarray
    surfaces: list[PlySurface]  # bottom then top face of every ply
    constrained: PrescribedCurvatureResult | None  # set for forces_curvature
    mixed: MixedResult | None  # set for mixed


def _lamina(table: dict, si) -> Lamina:
    strengths = expansion = None
    if "F1t" in table:
        strengths = Strengths(**{name: float(si(table[name], "stress")) for name in STRENGTH_NAMES})
    if "alpha1" in table:
        expansion = ThermalExpansion(**{name: float(si(table[name], "alpha")) for name in ALPHA_NAMES})
    return Lamina(E1=float(si(table["E1"], "modulus")), E2=float(si(table["E2"], "modulus")),
                  G12=float(si(table["G12"], "modulus")), nu12=table["nu12"],
                  strengths=strengths, thermal_expansion=expansion)


def solve_case(case: dict) -> CaseSolution:
    """Build the laminate from the case and solve it once, in SI units."""
    validate_case_inputs(case)
    units = UNIT_SYSTEMS[case["units"]]

    def si(value, kind):
        return np.asarray(value, dtype=float) * units[kind][0]

    if "material" in case:
        materials = {"material": _lamina(case["material"], si)}
        thickness = float(si(case["laminate"]["ply_thickness"], "length"))
        layers = [(angle, "material", thickness) for angle in case["laminate"]["layup"]]
    else:
        materials = {name: _lamina(table, si) for name, table in case["materials"].items()}
        layers = [(ply["angle"], ply["material"], float(si(ply["thickness"], "length")))
                  for ply in case["laminate"]["plies"]]
    plies = [Ply(material=materials[name], angle_deg=angle, thickness_m=t) for angle, name, t in layers]
    ply_materials = [name for _, name, _ in layers]
    h = sum(ply.thickness_m for ply in plies)

    applied = case["applied"]
    kind = next(kind for kind in APPLIED_KINDS if kind in applied)
    value = applied[kind]
    if kind.startswith("local") and len({(angle, name) for angle, name, _ in layers}) != 1:
        raise ValueError("local_stress and local_strain need a layup with a single angle and material")
    # A temperature change is applied only when the case states one; it is never assumed.
    delta_T = float(si(applied["delta_T"], "delta_T")) if "delta_T" in applied else None
    N_T, M_T = thermal_resultants(plies, delta_T) if delta_T is not None else (np.zeros(3), np.zeros(3))
    constrained = mixed = None

    if kind in ("loads", "stress", "local_stress"):
        if kind == "loads":
            resultants = np.concatenate([si(value[:3], "N"), si(value[3:], "M")])
        else:
            stress = si(value, "stress")
            if kind == "local_stress":
                stress = stress_transformation(-layers[0][0]) @ stress  # rotating back by -theta: local to global
            resultants = np.concatenate([stress * h, np.zeros(3)])
        loads = Loads(**dict(zip(LOAD_NAMES, resultants)))
        if delta_T is None:
            eps0, kappa = midplane_response(plies, loads)
        else:
            eps0, kappa = thermomechanical_response(plies, loads, delta_T)
    elif kind == "mixed":
        # Mechanical loads or deformations, one per pair; the solver adds any thermal resultants.
        known = {name: float(si(v, QUANTITY_UNITS[name])) if QUANTITY_UNITS[name] else float(v)
                 for name, v in value.items()}
        mixed = mixed_response(plies, known, delta_T)
        eps0, kappa, loads = mixed.midplane_strain, mixed.curvature, mixed.loads
    elif kind == "forces_curvature":
        # Solve with total forces N + N_T; the solved total moments include M_T, so remove it.
        forces, kappa = si(value[:3], "N"), si(value[3:], "kappa")
        constrained = prescribed_curvature_response(plies, forces + N_T, kappa)
        eps0 = constrained.midplane_strain
        loads = Loads(**dict(zip(LOAD_NAMES, np.concatenate([forces, constrained.moments - M_T]))))
    else:
        if kind == "strains":
            eps0, kappa = np.asarray(value[:3], dtype=float), si(value[3:], "kappa")
        else:
            eps0, kappa = strain_transformation(-layers[0][0]) @ np.asarray(value, dtype=float), np.zeros(3)
        total = abd_matrix(plies) @ np.concatenate([eps0, kappa])
        loads = Loads(**dict(zip(LOAD_NAMES, total - np.concatenate([N_T, M_T]))))

    surfaces = (ply_surfaces(plies, eps0, kappa) if delta_T is None
                else thermal_ply_surfaces(plies, eps0, kappa, delta_T))
    return CaseSolution(case["units"], materials, ply_materials, plies, kind, delta_T, N_T, M_T,
                        loads, eps0, kappa, surfaces, constrained, mixed)


def engine_results(case: dict) -> dict:
    """Everything the case's inputs determine, in the case's units, as {key: (value, scale)}.

    The scale is the largest magnitude in the same group of results, used to judge
    expected values of zero.
    """
    solution = solve_case(case)
    units = UNIT_SYSTEMS[case["units"]]
    plies = solution.plies

    def shown(value_si, kind):
        return np.asarray(value_si) / units[kind][0]

    def add(key, value):
        value = np.asarray(value, dtype=float)
        results[key] = (value, np.abs(value).max(initial=0.0))

    def add_matrix(prefix, matrix, kind):
        values = shown(matrix, kind)
        for i in "126":
            for j in "126":
                results[f"{prefix}{i}{j}"] = (values[_INDEX[i], _INDEX[j]], np.abs(values).max())

    results = {}
    used = list(dict.fromkeys(solution.ply_materials))
    if len(used) == 1:
        material = solution.materials[used[0]]
        add_matrix("Q", reduced_stiffness(material), "modulus")
        add_matrix("S", reduced_compliance(material), "compliance")
        if len({ply.angle_deg for ply in plies}) == 1:
            angle = plies[0].angle_deg
            add_matrix("Qbar", transformed_reduced_stiffness(material, angle), "modulus")
            add_matrix("Sbar", transformed_compliance(material, angle), "compliance")
    for name, matrix in zip("ABD", abd_matrices(plies)):
        add_matrix(name, matrix, name)
    for name, matrix in zip("abd", abd_compliance(plies)):
        add_matrix(name, matrix, name)
    add("strain_global", solution.eps0)
    add("curvature", shown(solution.kappa, "kappa"))
    add("moments", shown(solution.loads.as_vector()[3:], "M"))
    # Named scalars, as answer keys state them: mechanical resultants, average stress N/h,
    # mid-plane strains and curvatures. Each is judged against the scale of its group.
    h = sum(ply.thickness_m for ply in plies)
    vector = solution.loads.as_vector()
    groups = {"N": vector[:3], "M": vector[3:], "stress": vector[:3] / h,
              None: solution.eps0, "kappa": solution.kappa}
    names = {"N": ("Nx", "Ny", "Nxy"), "M": ("Mx", "My", "Mxy"), "stress": AVERAGE_STRESSES,
             None: DEFORMATIONS[:3], "kappa": DEFORMATIONS[3:]}
    for kind, values in groups.items():
        values = shown(values, kind) if kind else np.asarray(values)
        for name, v in zip(names[kind], values):
            results[name] = (float(v), np.abs(values).max())
    if solution.delta_T is not None:
        add("N_T", shown(solution.N_T, "N"))
        add("M_T", shown(solution.M_T, "M"))

    # One row per ply, bottom ply first: each face, and mid-thickness. Strain and stress are
    # linear through a ply, so mid-thickness is the face average and the ply's value when
    # curvature is zero.
    bottoms, tops = solution.surfaces[::2], solution.surfaces[1::2]
    for quantity, kind in (("strain", None), ("stress", "stress")):
        for axes, suffix in (("global", "xy"), ("local", "12")):
            attribute = f"{quantity}_{suffix}"
            faces = {face: np.array([getattr(s, attribute) for s in group])
                     for face, group in (("bottom", bottoms), ("top", tops))}
            if kind:
                faces = {face: shown(values, kind) for face, values in faces.items()}
            add(f"ply_{quantity}_{axes}_bottom", faces["bottom"])
            add(f"ply_{quantity}_{axes}_top", faces["top"])
            add(f"ply_{quantity}_{axes}", (faces["bottom"] + faces["top"]) / 2)

    if len({(ply.angle_deg, name) for ply, name in zip(plies, solution.ply_materials)}) == 1 \
            and not np.any(solution.kappa):
        # One fiber direction and material and no bending: every ply face carries the same state.
        face = solution.surfaces[0]
        add("strain_local", face.strain_12)
        add("stress_global", shown(face.stress_xy, "stress"))
        add("stress_local", shown(face.stress_12, "stress"))

    constants = engineering_constants(plies)
    for key in ("Ex", "Ey", "Gxy"):
        results[key] = (shown(getattr(constants, key), "modulus"), 0.0)
    results["nu_xy"] = (constants.nu_xy, 0.0)
    results["nu_yx"] = (constants.nu_yx, 0.0)

    # Residual thermal stress does not scale with the applied load, so first_ply_failure's
    # ratio would be wrong with a temperature change. No failure result is given then.
    has_strengths = all(ply.material.strengths is not None for ply in plies)
    if has_strengths and solution.delta_T is None and np.any(solution.loads.as_vector()):
        results["fpf_ratio_max_stress"] = (first_ply_failure(plies, solution.loads).strength_ratio, 0.0)
        if "f12_star" in case:
            tsai_wu = first_ply_failure(plies, solution.loads, "tsai_wu", case["f12_star"])
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


def _expected_rows(key: str, value, got: np.ndarray) -> tuple[list[tuple[str, np.ndarray, np.ndarray]], list[str]]:
    """Pair expected values with the engine's, as (label prefix, wanted, computed) groups."""
    if isinstance(value, dict):
        # Only some plies, keyed by ply number with ply 1 at the bottom, as answer keys state them.
        if key not in PLY_TABLE_KEYS:
            return [], [f"{key}: only per-ply results can be given by ply number"]
        groups, problems = [], []
        for number, row in value.items():
            if not str(number).isdigit() or not 1 <= int(number) <= len(got):
                problems.append(f"{key}: ply {number} does not exist; plies run from 1 (bottom) to {len(got)}")
                continue
            want = np.asarray(row, dtype=float)
            if want.shape != (3,):
                problems.append(f"{key}: ply {number} needs exactly 3 values")
                continue
            groups.append((f"{key}[ply {int(number)}]", want, got[int(number) - 1]))
        return groups, problems
    want = np.atleast_1d(np.asarray(value, dtype=float))
    if want.shape != got.shape:
        return [], [f"{key}: expected shape {want.shape}, the engine gives {got.shape}"]
    return [(key, want, got)], []


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
        groups, found = _expected_rows(key, value, np.atleast_1d(computed))
        problems += found
        for prefix, want, got in groups:
            # Tables such as ply_stress_local are labelled key[row,column].
            for index, w in np.ndenumerate(want):
                label = prefix if want.size == 1 else f"{prefix}[{','.join(map(str, index))}]"
                allowed = tolerance * (abs(w) if w != 0 else scale)
                comparisons.append(Comparison(label, float(w), float(got[index]), float(allowed)))
    return comparisons, problems


def disagreements(case: dict) -> list[str]:
    """Plain-language list of every expected value the engine does not reproduce."""
    comparisons, problems = compare(case)
    mismatches = [f"{c.key}: expected {c.expected:.6g}, engine gives {c.engine:.6g}" for c in comparisons if not c.agrees]
    return problems + mismatches
