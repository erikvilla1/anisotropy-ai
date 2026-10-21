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
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ._validation import finite_vector
from .buckling import BucklingResult, plate_buckling
from .engineering import engineering_constants
from .failure import FirstPlyFailure, first_ply_failure_combined
from .lamina import Lamina, StrainLimits, Strengths, ThermalExpansion, reduced_compliance, reduced_stiffness, strain_limits_from_strengths
from .library import LibraryMaterial, library_material
from .laminate import Ply, abd_matrices
from .micromechanics import E2_MODELS, G12_MODELS, Fiber, Matrix, MicromechanicsResult, lamina_from_constituents
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
STRAIN_LIMIT_NAMES = ("eps1t", "eps1c", "eps2t", "eps2c", "gamma12")
STRAIN_LIMITS_FROM_STRENGTHS = "from-strengths"
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


CONSTITUENT_NAMES = ("fiber", "matrix", "Vf", "E2_model", "G12_model")
FIBER_NAMES = ("E1", "E2", "G12", "nu12")
MATRIX_NAMES = ("E", "nu")


def _check_constituents(table: dict, name: str) -> None:
    """A material stated by its fiber, matrix, fiber volume ratio and the named models (micromechanics)."""
    _fields(table, name, set(CONSTITUENT_NAMES),
            {"xi_E2", "xi_G12"} | set(STRENGTH_NAMES) | set(ALPHA_NAMES) | set(STRAIN_LIMIT_NAMES) | {"strain_limits"})
    _fields(table["fiber"], f"{name}.fiber", set(FIBER_NAMES), set())
    _fields(table["matrix"], f"{name}.matrix", set(MATRIX_NAMES), set())
    for group, keys in (("fiber", FIBER_NAMES), ("matrix", MATRIX_NAMES)):
        bad = [key for key in keys if not _is_number(table[group][key])]
        if bad:
            raise ValueError(f"{name}.{group}: {bad} must be finite numbers")
    if not _is_number(table["Vf"]) or not 0 < table["Vf"] < 1:
        raise ValueError(f"{name}.Vf must be a fiber volume ratio strictly between 0 and 1 (a fraction, not percent)")
    if table["E2_model"] not in E2_MODELS:
        raise ValueError(f"{name}.E2_model must be one of {E2_MODELS}")
    if table["G12_model"] not in G12_MODELS:
        raise ValueError(f"{name}.G12_model must be one of {G12_MODELS}")
    for key, model in (("xi_E2", table["E2_model"]), ("xi_G12", table["G12_model"])):
        if model == "halpin_tsai" and key not in table:
            raise ValueError(f"{name}: {key} is required with the halpin_tsai model and is never assumed")
        if model != "halpin_tsai" and key in table:
            raise ValueError(f"{name}: {key} belongs to the halpin_tsai model only")
        if key in table and (not _is_number(table[key]) or table[key] < 0):
            raise ValueError(f"{name}.{key} must be a finite number, zero or positive")


def _check_material(table: dict, name: str) -> None:
    if isinstance(table, dict) and "fiber" in table:
        _check_constituents(table, name)
        supplied = set(STRENGTH_NAMES) & table.keys()
        if supplied and supplied != set(STRENGTH_NAMES):
            raise ValueError(f"{name} needs either all five strengths or none")
        _check_strain_limits(table, name)
        alphas = set(ALPHA_NAMES) & table.keys()
        if alphas and alphas != set(ALPHA_NAMES):
            raise ValueError(f"{name} needs both alpha1 and alpha2 or neither")
        return
    if isinstance(table, dict) and "library" in table:
        # A library dataset supplies the values; typed values cannot be mixed in. The maximum-strain
        # policy is a stated choice, not a value, so it may accompany a library dataset.
        _fields(table, name, {"library"}, {"dataset", "strain_limits"})
        if not isinstance(table["library"], str) or not isinstance(table.get("dataset", ""), str):
            raise ValueError(f"{name}: library and dataset must be a material id and a dataset id")
        _check_strain_limits(table, name)
        return
    _fields(table, name, set(ELASTIC_NAMES), set(STRENGTH_NAMES) | set(ALPHA_NAMES) | set(STRAIN_LIMIT_NAMES) | {"strain_limits"})
    supplied = set(STRENGTH_NAMES) & table.keys()
    if supplied and supplied != set(STRENGTH_NAMES):
        raise ValueError(f"{name} needs either all five strengths or none")
    _check_strain_limits(table, name)
    if "strain_limits" in table and "F1t" not in table:
        raise ValueError(f"{name}: strain_limits = \"{STRAIN_LIMITS_FROM_STRENGTHS}\" needs all five strengths")
    alphas = set(ALPHA_NAMES) & table.keys()
    if alphas and alphas != set(ALPHA_NAMES):
        raise ValueError(f"{name} needs both alpha1 and alpha2 or neither")


def _check_strain_limits(table: dict, name: str) -> None:
    """Maximum-strain limits are five explicit magnitudes, or the stated from-strengths choice, not both."""
    explicit = set(STRAIN_LIMIT_NAMES) & table.keys()
    if explicit and explicit != set(STRAIN_LIMIT_NAMES):
        raise ValueError(f"{name} needs either all five strain limits {STRAIN_LIMIT_NAMES} or none")
    if explicit and any(not _is_number(table[k]) or table[k] <= 0 for k in STRAIN_LIMIT_NAMES):
        raise ValueError(f"{name}: strain limits must be positive magnitudes (fractions, not percent)")
    if "strain_limits" in table:
        if table["strain_limits"] != STRAIN_LIMITS_FROM_STRENGTHS:
            raise ValueError(f"{name}: strain_limits must be \"{STRAIN_LIMITS_FROM_STRENGTHS}\" (strength divided by modulus); "
                             "give eps1t, eps1c, eps2t, eps2c and gamma12 for measured limits")
        if explicit:
            raise ValueError(f"{name}: give explicit strain limits or strain_limits = \"{STRAIN_LIMITS_FROM_STRENGTHS}\", not both")


def _with_strain_limits(lamina: Lamina, table: dict, name: str) -> Lamina:
    """Attach the case's maximum-strain limits to a lamina, explicit or derived by stated choice."""
    if "eps1t" in table:
        return lamina.model_copy(update={"strain_limits": StrainLimits(**{k: float(table[k]) for k in STRAIN_LIMIT_NAMES})})
    if table.get("strain_limits") == STRAIN_LIMITS_FROM_STRENGTHS:
        if lamina.strengths is None:
            raise ValueError(f"{name}: strain_limits = \"{STRAIN_LIMITS_FROM_STRENGTHS}\" needs strengths, which this dataset does not provide")
        return lamina.model_copy(update={"strain_limits": strain_limits_from_strengths(lamina)})
    return lamina


def _resolve_library(tables: dict) -> dict[str, LibraryMaterial]:
    """Load every library material a case names, so its contents can be checked like typed ones."""
    resolved = {}
    for name, table in tables.items():
        if "library" in table:
            try:
                resolved[name] = library_material(table["library"], table.get("dataset"))
            except ValueError as error:
                where = "[material]" if name == "material" else f"[materials.{name}]"
                raise ValueError(f"{where}: {error}") from None
    return resolved


def _supplies(tables: dict, resolved: dict, name: str, what: str) -> bool:
    if name in resolved:
        lamina = resolved[name].lamina
        return (lamina.thermal_expansion if what == "alpha" else lamina.strengths) is not None
    return ("alpha1" if what == "alpha" else "F1t") in tables[name]


def validate_case_inputs(case: dict) -> None:
    """Reject incomplete or misspelled case inputs before converting units or solving."""
    _fields(case, "case", {"units", "laminate", "applied"},
            {"title", "source", "expected", "f12_star", "material", "materials", "failure", "plate", "buckling"})
    if ("plate" in case) != ("buckling" in case):
        raise ValueError("plate buckling needs both a [plate] table (a, b, edges) and a [buckling] table (loads, terms)")
    if "plate" in case:
        _fields(case["plate"], "plate", {"a", "b", "edges"}, set())
        if case["plate"]["edges"] != "simply-supported":
            raise ValueError('plate.edges must be "simply-supported"; other edge conditions are not implemented')
        if any(not _is_number(case["plate"][k]) or case["plate"][k] <= 0 for k in ("a", "b")):
            raise ValueError("plate.a and plate.b must be positive lengths")
        _fields(case["buckling"], "buckling", {"loads"}, {"terms"})
        finite_vector(case["buckling"]["loads"], "buckling.loads", 3)
        if not np.any(case["buckling"]["loads"]):
            raise ValueError("buckling.loads needs at least one nonzero reference resultant [Nx, Ny, Nxy]")
        terms = case["buckling"].get("terms")
        if terms is not None and (not isinstance(terms, int) or isinstance(terms, bool) or terms < 1):
            raise ValueError("buckling.terms must be a positive integer (series terms per direction)")
    if ("material" in case) == ("materials" in case):
        raise ValueError("case needs exactly one of [material] (one material) or [materials.<name>] tables")
    if case["units"] not in UNIT_SYSTEMS:
        raise ValueError(f"units must be one of {tuple(UNIT_SYSTEMS)}")
    laminate = case["laminate"]
    if "material" in case:
        _check_material(case["material"], "material")
        _fields(laminate, "laminate", {"layup"}, {"ply_thickness"})
        if "ply_thickness" not in laminate and "library" not in case["material"]:
            raise ValueError("laminate.ply_thickness is required unless [material] names a library dataset that records one")
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
    resolved = _resolve_library(tables)
    if "material" in case and "ply_thickness" not in laminate and resolved["material"].ply_thickness_m is None:
        raise ValueError(f"library dataset {resolved['material'].dataset_id!r} has no ply thickness; give laminate.ply_thickness")
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
        missing = [name for name in used if not _supplies(tables, resolved, name, "alpha")]
        if missing:
            where = "[material]" if "material" in case else f"materials {missing}"
            raise ValueError(f"applied.delta_T needs alpha1 and alpha2 in {where}")
    if "failure" in case:
        _fields(case["failure"], "failure", {"fixed", "variable"}, set())
        for name in ("fixed", "variable"):
            finite_vector(case["failure"][name], f"failure.{name}", 6)
        if not np.any(case["failure"]["variable"]):
            raise ValueError("failure.variable needs at least one nonzero load to scale")
        no_strengths = [name for name in used if not _supplies(tables, resolved, name, "strengths")]
        if no_strengths:
            raise ValueError(f"[failure] needs all five strengths for {no_strengths}")
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
    library: dict[str, LibraryMaterial] = field(default_factory=dict)  # library datasets by material name
    constituents: dict[str, MicromechanicsResult] = field(default_factory=dict)  # materials stated by fiber, matrix and Vf


def _constituents(table: dict, si, name: str = "material") -> MicromechanicsResult:
    """The micromechanics result of a material stated by its constituents, in SI."""
    fiber = Fiber(E1=float(si(table["fiber"]["E1"], "modulus")), E2=float(si(table["fiber"]["E2"], "modulus")),
                  G12=float(si(table["fiber"]["G12"], "modulus")), nu12=float(table["fiber"]["nu12"]))
    matrix = Matrix(E=float(si(table["matrix"]["E"], "modulus")), nu=float(table["matrix"]["nu"]))
    strengths = Strengths(**{k: float(si(table[k], "stress")) for k in STRENGTH_NAMES}) if "F1t" in table else None
    expansion = ThermalExpansion(**{k: float(si(table[k], "alpha")) for k in ALPHA_NAMES}) if "alpha1" in table else None
    try:
        return lamina_from_constituents(fiber, matrix, float(table["Vf"]), table["E2_model"], table["G12_model"],
                                        table.get("xi_E2"), table.get("xi_G12"), strengths, expansion)
    except ValueError as error:
        raise ValueError(f"{name}: {error}") from None


def _lamina(table: dict, si, resolved: dict[str, LibraryMaterial] | None = None, name: str = "material") -> Lamina:
    if resolved and name in resolved:
        return _with_strain_limits(resolved[name].lamina, table, name)
    if "fiber" in table:
        return _with_strain_limits(_constituents(table, si, name).lamina, table, name)
    strengths = expansion = None
    if "F1t" in table:
        strengths = Strengths(**{name: float(si(table[name], "stress")) for name in STRENGTH_NAMES})
    if "alpha1" in table:
        expansion = ThermalExpansion(**{name: float(si(table[name], "alpha")) for name in ALPHA_NAMES})
    lamina = Lamina(E1=float(si(table["E1"], "modulus")), E2=float(si(table["E2"], "modulus")),
                    G12=float(si(table["G12"], "modulus")), nu12=table["nu12"],
                    strengths=strengths, thermal_expansion=expansion)
    return _with_strain_limits(lamina, table, name)


def solve_case(case: dict) -> CaseSolution:
    """Build the laminate from the case and solve it once, in SI units."""
    validate_case_inputs(case)
    units = UNIT_SYSTEMS[case["units"]]

    def si(value, kind):
        return np.asarray(value, dtype=float) * units[kind][0]

    tables = {"material": case["material"]} if "material" in case else case["materials"]
    resolved = _resolve_library(tables)
    if "material" in case:
        materials = {"material": _lamina(case["material"], si, resolved)}
        thickness = (float(si(case["laminate"]["ply_thickness"], "length")) if "ply_thickness" in case["laminate"]
                     else resolved["material"].ply_thickness_m)
        layers = [(angle, "material", thickness) for angle in case["laminate"]["layup"]]
    else:
        materials = {name: _lamina(table, si, resolved, name) for name, table in case["materials"].items()}
        layers = [(ply["angle"], ply["material"], float(si(ply["thickness"], "length")))
                  for ply in case["laminate"]["plies"]]
    plies = [Ply(material=materials[name], angle_deg=angle, thickness_m=t) for angle, name, t in layers]
    ply_materials = [name for _, name, _ in layers]
    constituents = {name: _constituents(table, si, name) for name, table in tables.items() if "fiber" in table}
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
                        loads, eps0, kappa, surfaces, constrained, mixed, resolved, constituents)


def buckling_result(case: dict, solution: CaseSolution) -> BucklingResult | None:
    """Plate buckling for a case with [plate] and [buckling], in SI, or None without them."""
    if "plate" not in case:
        return None
    units = UNIT_SYSTEMS[case["units"]]
    a, b = (float(case["plate"][k]) * units["length"][0] for k in ("a", "b"))
    loads = np.asarray(case["buckling"]["loads"], dtype=float) * units["N"][0]
    return plate_buckling(solution.plies, a, b, loads, case["buckling"].get("terms"))


def failure_loads(case: dict, solution: CaseSolution) -> tuple[Loads, Loads] | None:
    """The (fixed, variable) loads for first-ply failure, in SI, or None when it cannot be checked.

    A [failure] table names both, as six resultants in the case's units. Without one, the
    case's mechanical loads (given or solved) scale and nothing mechanical is held fixed; a
    temperature change then stays fixed, as in Daniel & Ishai Section 9.8. None means some
    ply has no strengths or nothing would scale.
    """
    if not all(ply.material.strengths is not None for ply in solution.plies):
        return None
    if "failure" in case:
        factors = [UNIT_SYSTEMS[case["units"]][kind][0] for kind in ("N",) * 3 + ("M",) * 3]
        fixed, variable = (np.asarray(case["failure"][name], dtype=float) * factors for name in ("fixed", "variable"))
        return (Loads(**dict(zip(LOAD_NAMES, fixed))), Loads(**dict(zip(LOAD_NAMES, variable))))
    if not np.any(solution.loads.as_vector()):
        return None
    return Loads(**dict.fromkeys(LOAD_NAMES, 0.0)), solution.loads


def first_ply_failures(case: dict, solution: CaseSolution) -> dict[str, FirstPlyFailure]:
    """First-ply failure for each criterion the case supports.

    Maximum stress and Tsai-Hill need strengths; maximum strain needs strain limits on every
    ply (explicit, or from strengths by stated choice); Tsai-Wu needs f12_star as well.
    """
    loads = failure_loads(case, solution)
    if loads is None:
        return {}
    criteria = ["max_stress"]
    if all(ply.material.strain_limits is not None for ply in solution.plies):
        criteria.append("max_strain")
    criteria.append("tsai_hill")
    if "f12_star" in case:
        criteria.append("tsai_wu")
    return {criterion: first_ply_failure_combined(solution.plies, *loads, solution.delta_T, criterion,
                                                  case.get("f12_star"))
            for criterion in criteria}


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
    if len(used) == 1 and used[0] in solution.constituents:
        # The lamina constants the micromechanics models produced, as answer keys state them.
        derived = solution.constituents[used[0]]
        for key in ("E1", "E2", "G12"):
            results[key] = (float(shown(getattr(derived, key), "modulus")), 0.0)
        results["nu12"] = (derived.nu12, 0.0)
        results["nu21"] = (derived.nu21, 0.0)
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

    # Plate buckling: the factor on the reference loads, the critical loads, and the mode.
    buckling = buckling_result(case, solution)
    if buckling is not None:
        results["buckling_factor"] = (buckling.load_factor, 0.0)
        add("buckling_loads", shown(buckling.critical_loads, "N"))
        if buckling.mode is not None:
            add("buckling_mode", np.array(buckling.mode, dtype=float))
        if buckling.orthotropic_factor is not None:
            results["buckling_orthotropic_factor"] = (buckling.orthotropic_factor, 0.0)

    # First-ply failure: the ratio on the variable loads, the loads at failure, and where it occurs.
    for criterion, fpf in first_ply_failures(case, solution).items():
        results[f"fpf_ratio_{criterion}"] = (fpf.strength_ratio, 0.0)
        add(f"fpf_forces_{criterion}", shown(fpf.failure_loads.as_vector()[:3], "N"))
        add(f"fpf_moments_{criterion}", shown(fpf.failure_loads.as_vector()[3:], "M"))
        results[f"fpf_ply_{criterion}"] = (float(fpf.governing.ply_index + 1), 0.0)
        results[f"fpf_z_{criterion}"] = (float(shown(fpf.governing.z_m, "length")), float(shown(h / 2, "length")))
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
