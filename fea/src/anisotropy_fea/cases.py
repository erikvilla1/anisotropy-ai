"""Finite element validation cases: a deck, expected numbers, a source and a tolerance (ADR-0007, ADR-0029).

A case is a TOML file:

    title = "..."
    source = "where the expected numbers come from"
    units = "mm-MPa"                      # the deck's unit system; expected values are in the same units

    [mesh]
    deck = "../decks/coupon-1x1-im7-8552.inp"   # relative to the case file

    [expected]
    tolerance = 1e-9                      # relative to |expected|, or to the group's largest magnitude when expected is 0
    [expected.rf]                         # [RFx, RFy] at a node ("Assembly.1", "Coupon-1.3") or summed over an assembly node set ("Top")
    "Top" = [0.0, 1234.5]
    [expected.u]                          # [u, v] at a node
    "Coupon-1.3" = [0.0123, 0.8]
    [expected.strain]                     # [eps_x, eps_y, gamma_xy] at an element's centroid; "*" means every element
    "*" = [-0.0031, 0.01, 0.0004]
    [expected.section_force]              # [Nx, Ny, Nxy] at an element's centroid, force per length; "*" as above
    "*" = [0.0, 123.4, 0.0]
    [expected.w]                          # [w] at a node: the out-of-plane displacement of a shell solve (ADR-0053)
    "Coupon-1.3" = [-0.5]
    [expected.rotation]                   # [theta_x, theta_y] at a node, radians
    "Coupon-1.3" = [0.0, 0.01]
    [expected.rf_z]                       # [RFz] at a node or summed over an assembly node set
    "Support-Left" = [250.0]
    [expected.curvature]                  # [kappa_x, kappa_y, kappa_xy] at an element's centroid, 1/length
    "*" = [0.001, 0.0, 0.0]
    [expected.moment]                     # [Mx, My, Mxy] at an element's centroid, moment per unit width (force units)
    "*" = [12.3, 0.4, 0.0]
    [expected.shear_force]                # [Qx, Qy] at an element's centroid, force per length
    "*" = [0.0, 1.0]
    [expected.ply_stress_local."*"]       # per ply, bottom ply is 1: [sigma_1, sigma_2, tau_12] in material axes, stress units
    1 = [1234.5, 12.3, -4.5]              # a shell state has two faces per ply: write "1:bottom" and "1:top" instead of 1
    [expected.ply_strain_local."Coupon-1.1"]   # per ply: [eps_1, eps_2, gamma_12]
    2 = [0.004, -0.001, 0.002]
    [expected.ply_mises."Coupon-1.1"]          # per ply: [von Mises of the in-plane ply stress]
    1 = [1234.5]
    [expected.fpf.max_stress]             # first-ply failure by one criterion: the factor on the applied loading and, optionally, where and the mode
    ratio = 12.3
    element = "Coupon-1.1"                # omit element, ply and mode when identical plies tie (a uniform state)
    ply = 2
    mode = "transverse tension"

Comparison labels read `group[name][component]`, like the engine's, so a disagreement names exactly one number.
A component written as `nan` was not reported by the source (an Abaqus report without S12, say) and is skipped.
"""

from __future__ import annotations

import math
import tomllib
from pathlib import Path

import numpy as np

from anisotropy_engine.cases import Comparison
from anisotropy_engine.failure import CRITERIA

from .abaqus_reader import read_deck
from .kernel import solve_deck
from .model import Deck, ElementKey, NodeKey
from .recovery import FACES, deck_f12_star, element_ply_states, ply_mises, strength_ratios
from .results import ShellSolution, Solution
from .units import from_si

# group -> (unit kind for conversion out of SI, vector length, what a name may be)
GROUPS: dict[str, tuple[str | None, int, str]] = {
    "rf": ("force", 2, "a node or an assembly node set"),
    "u": ("length", 2, "a node"),
    "strain": (None, 3, "an element or *"),
    "section_force": ("force_per_length", 3, "an element or *"),
    "w": ("length", 1, "a node"),
    "rotation": (None, 2, "a node"),
    "rf_z": ("force", 1, "a node or an assembly node set"),
    "curvature": ("per_length", 3, "an element or *"),
    "moment": ("force", 3, "an element or *"),
    "shear_force": ("force_per_length", 2, "an element or *"),
}
SHELL_GROUPS = ("w", "rotation", "rf_z", "curvature", "moment", "shear_force")  # a membrane solve has none of these
# ply group -> (unit kind, vector length)
PLY_GROUPS: dict[str, tuple[str | None, int]] = {"ply_stress_local": ("stress", 3), "ply_strain_local": (None, 3), "ply_mises": ("stress", 1)}
FPF_FIELDS = ("ratio", "element", "ply", "mode", "face")
REQUIRED = ("title", "source", "units", "mesh", "expected")


def load_case(path: Path | str) -> dict:
    path = Path(path)
    with path.open("rb") as handle:
        case = tomllib.load(handle)
    case["_dir"] = str(path.parent)
    validate_case(case)
    return case


def validate_case(case: dict) -> None:
    for field in REQUIRED:
        if field not in case:
            raise ValueError(f"case needs {field!r}")
    unknown = set(case) - set(REQUIRED) - {"_dir"}
    if unknown:
        raise ValueError(f"case has unknown keys {sorted(unknown)}")
    mesh = case["mesh"]
    if not isinstance(mesh, dict) or set(mesh) != {"deck"} or not isinstance(mesh["deck"], str):
        raise ValueError("[mesh] must hold exactly `deck = \"path\"`")
    expected = case["expected"]
    tolerance = expected.get("tolerance")
    if not isinstance(tolerance, (int, float)) or not tolerance > 0:
        raise ValueError("[expected] needs a positive `tolerance`")
    for group, rows in expected.items():
        if group == "tolerance":
            continue
        if group in GROUPS:
            _, length, _ = GROUPS[group]
            if not isinstance(rows, dict) or not rows:
                raise ValueError(f"[expected.{group}] must be a table of name = [values]")
            for name, vector in rows.items():
                _check_vector(f"[expected.{group}] {name!r}", vector, length)
        elif group in PLY_GROUPS:
            if not isinstance(rows, dict) or not rows:
                raise ValueError(f"[expected.{group}] must be a table of element = {{ply = [values]}}")
            length = PLY_GROUPS[group][1]
            for name, plies in rows.items():
                if not isinstance(plies, dict) or not plies:
                    raise ValueError(f"[expected.{group}.{name!r}] must be a table of ply number = [{length} values]")
                for ply, vector in plies.items():
                    number, _, face = str(ply).partition(":")
                    if not number.isdigit() or int(number) < 1 or face not in ("", *FACES):
                        raise ValueError(f"[expected.{group}.{name!r}] ply keys are numbers from 1 (bottom), with :bottom or :top for a shell state; got {ply!r}")
                    _check_vector(f"[expected.{group}.{name!r}] ply {ply}", vector, length)
        elif group == "fpf":
            if not isinstance(rows, dict) or not rows:
                raise ValueError("[expected.fpf] must hold one table per criterion")
            for criterion, fields in rows.items():
                if criterion not in CRITERIA:
                    raise ValueError(f"[expected.fpf.{criterion}] is not a criterion; known: {', '.join(CRITERIA)}")
                if not isinstance(fields, dict) or "ratio" not in fields or set(fields) - set(FPF_FIELDS):
                    raise ValueError(f"[expected.fpf.{criterion}] needs `ratio` and may have element, ply, mode")
                if not isinstance(fields["ratio"], (int, float)):
                    raise ValueError(f"[expected.fpf.{criterion}] ratio must be a number")
        else:
            known = ", ".join(list(GROUPS) + list(PLY_GROUPS) + ["fpf"])
            raise ValueError(f"[expected.{group}] is not a result group; known: {known}")


def _check_vector(where: str, vector, length: int) -> None:
    if not isinstance(vector, list) or len(vector) != length or not all(isinstance(v, (int, float)) for v in vector):
        raise ValueError(f"{where} must be a list of {length} numbers")


def deck_path(case: dict) -> Path:
    return (Path(case["_dir"]) / case["mesh"]["deck"]).resolve()


def solve_case(case: dict) -> tuple[Deck, Solution]:
    """The deck solved by the kernel its loads and layup call for (`kernel.solve_deck`)."""
    deck = read_deck(deck_path(case), case["units"])
    return deck, solve_deck(deck)


def parse_node_name(name: str) -> NodeKey:
    """`Assembly.N` is a reference node; `Instance.N` is an instance node."""
    instance, dot, label = name.rpartition(".")
    if not dot or not label.isdigit():
        raise ValueError(f"{name!r} is not a node name of the form Instance.label or Assembly.label")
    return (None if instance == "Assembly" else instance, int(label))


def parse_element_name(name: str) -> ElementKey:
    instance, dot, label = name.rpartition(".")
    if not dot or not label.isdigit() or instance == "Assembly":
        raise ValueError(f"{name!r} is not an element name of the form Instance.label")
    return (instance, int(label))


def element_name(key: ElementKey) -> str:
    return f"{key[0]}.{key[1]}"


def fe_results(case: dict) -> tuple[dict[str, tuple[np.ndarray, float]], dict[str, object]]:
    """Numbers: `label -> (vector in case units, group scale)`. Identities: `label -> value` for fpf element, ply and mode."""
    deck, solution = solve_case(case)
    units = case["units"]
    numbers: dict[str, tuple[np.ndarray, float]] = {}
    identities: dict[str, object] = {}
    expected = case["expected"]
    ply_field = element_ply_states(solution) if any(group in expected for group in PLY_GROUPS) or "fpf" in expected else None

    def store(group: str, vectors: dict[str, np.ndarray], kind: str | None) -> None:
        converted = {label: value if kind is None else np.array([from_si(float(v), kind, units) for v in value]) for label, value in vectors.items()}
        scale = max((float(np.max(np.abs(v))) for v in converted.values()), default=0.0)
        for label, value in converted.items():
            numbers[f"{group}[{label}]"] = (value, scale)

    for group, rows in expected.items():
        if group == "tolerance":
            continue
        if group in GROUPS:
            kind = GROUPS[group][0]
            vectors: dict[str, np.ndarray] = {}
            for name in rows:
                vectors.update(_quantity(group, name, deck, solution))
            store(group, vectors, kind)
        elif group in PLY_GROUPS:
            field = {"ply_stress_local": ply_field.stress_12, "ply_strain_local": ply_field.strain_12, "ply_mises": ply_mises(ply_field)}[group]
            vectors = {}
            for name, plies in rows.items():
                for element_label, e in _elements(name, solution):
                    for ply in plies:
                        number, _, face = str(ply).partition(":")
                        k = int(number) - 1
                        if k >= field[e].shape[0]:
                            raise ValueError(f"{group}[{element_label}][{ply}]: element has {field[e].shape[0]} plies")
                        if ply_field.faces is None:
                            if face:
                                raise ValueError(f"{group}[{element_label}][{ply}]: a membrane state has one value per ply; write {number}")
                            vectors[f"{element_label}][{ply}"] = field[e][k]
                        else:
                            if not face:
                                raise ValueError(f"{group}[{element_label}][{ply}]: a shell state has two faces per ply; write {number}:bottom or {number}:top")
                            vectors[f"{element_label}][{ply}"] = field[e][k, ply_field.faces.index(face)]
            store(group, vectors, PLY_GROUPS[group][0])
        elif group == "fpf":
            f12_star = deck_f12_star(deck)
            for criterion in rows:
                failure = strength_ratios(solution, criterion, f12_star, ply_field)
                numbers[f"fpf[{criterion}][ratio]"] = (np.array([failure.factor]), failure.factor)
                identities[f"fpf[{criterion}][element]"] = element_name(failure.element)
                identities[f"fpf[{criterion}][ply]"] = failure.ply
                identities[f"fpf[{criterion}][mode]"] = failure.governing_mode
                identities[f"fpf[{criterion}][face]"] = failure.face
    return numbers, identities


def _elements(name: str, solution: Solution) -> list[tuple[str, int]]:
    mesh = solution.mesh
    if name == "*":
        return [(element_name(key), e) for e, key in enumerate(mesh.element_keys)]
    return [(name, mesh.element(parse_element_name(name)))]


def _quantity(group: str, name: str, deck: Deck, solution: Solution) -> dict[str, np.ndarray]:
    """The SI vectors a name stands for; `*` expands to every element. The in-plane groups read the first two components of a shell
    solve; a shell group asked of a membrane solve is reported as a result the case cannot produce."""
    mesh = solution.mesh
    shell = isinstance(solution, ShellSolution)
    if group in SHELL_GROUPS and not shell:
        raise ValueError(f"{group}[{name}]: a membrane solve has no {group}; the deck neither bends nor carries a pressure")
    if group in ("rf", "rf_z"):
        columns = slice(0, 2) if group == "rf" else slice(2, 3)
        if name in deck.nsets:
            return {name: solution.reaction_of(deck.nsets[name])[columns]}
        return {name: solution.reaction[mesh.node(parse_node_name(name))][columns]}
    if group in ("u", "w", "rotation"):
        columns = {"u": slice(0, 2), "w": slice(2, 3), "rotation": slice(3, 5)}[group]
        return {name: solution.displacement[mesh.node(parse_node_name(name))][columns]}
    field = getattr(solution, group)
    return {label: field[e] for label, e in _elements(name, solution)}


def compare(case: dict) -> tuple[list[Comparison], list[str]]:
    """Every expected number next to the kernel's, plus problems: names the case cannot produce and identities that differ."""
    expected = case["expected"]
    tolerance = float(expected["tolerance"])
    try:
        numbers, identities = fe_results(case)
    except ValueError as exc:  # DeckError, KernelError and name errors are all ValueErrors
        return [], [str(exc)]
    comparisons: list[Comparison] = []
    problems: list[str] = []

    def add(label: str, want: list) -> None:
        if label not in numbers:
            problems.append(f"{label}: not a result this case produces")
            return
        got, scale = numbers[label]
        for i, w in enumerate(want):
            if isinstance(w, float) and math.isnan(w):
                continue  # not reported by the source
            allowed = tolerance * (abs(w) if w != 0 else scale)
            comparisons.append(Comparison(f"{label}[{i}]", float(w), float(got[i]), float(allowed)))

    for group, rows in expected.items():
        if group == "tolerance":
            continue
        if group in GROUPS:
            for name, want in rows.items():
                labels = [key for key in numbers if key.startswith(f"{group}[")] if name == "*" else [f"{group}[{name}]"]
                for label in labels:
                    add(label, want)
        elif group in PLY_GROUPS:
            for name, plies in rows.items():
                for ply, want in plies.items():
                    labels = ([key for key in numbers if key.startswith(f"{group}[") and key.endswith(f"][{ply}]")]
                              if name == "*" else [f"{group}[{name}][{ply}]"])
                    for label in labels:
                        add(label, want)
        elif group == "fpf":
            for criterion, fields in rows.items():
                add(f"fpf[{criterion}][ratio]", [fields["ratio"]])
                for field in ("element", "ply", "mode", "face"):
                    if field in fields:
                        label = f"fpf[{criterion}][{field}]"
                        if identities.get(label) != fields[field]:
                            problems.append(f"{label}: expected {fields[field]!r}, kernel gives {identities.get(label)!r}")
    return comparisons, problems


def disagreements(case: dict) -> list[str]:
    """Plain-language list of every expected value the kernel does not reproduce."""
    comparisons, problems = compare(case)
    mismatches = [f"{c.key}: expected {c.expected:.6g}, kernel gives {c.engine:.6g}" for c in comparisons if not c.agrees]
    return problems + mismatches
