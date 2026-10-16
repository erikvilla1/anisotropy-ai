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

Comparison labels read `group[name][component]`, like the engine's, so a disagreement names exactly one number.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import numpy as np

from anisotropy_engine.cases import Comparison

from .abaqus_reader import read_deck
from .membrane import solve_membrane
from .model import Deck, ElementKey, NodeKey
from .results import MembraneSolution
from .units import from_si

# group -> (unit kind for conversion out of SI, vector length, what a name may be)
GROUPS: dict[str, tuple[str | None, int, str]] = {
    "rf": ("force", 2, "a node or an assembly node set"),
    "u": ("length", 2, "a node"),
    "strain": (None, 3, "an element or *"),
    "section_force": ("force_per_length", 3, "an element or *"),
}
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
        if group not in GROUPS:
            raise ValueError(f"[expected.{group}] is not a result group; known: {', '.join(GROUPS)}")
        _, length, _ = GROUPS[group]
        if not isinstance(rows, dict) or not rows:
            raise ValueError(f"[expected.{group}] must be a table of name = [values]")
        for name, vector in rows.items():
            if not isinstance(vector, list) or len(vector) != length or not all(isinstance(v, (int, float)) for v in vector):
                raise ValueError(f"[expected.{group}] {name!r} must be a list of {length} numbers")


def deck_path(case: dict) -> Path:
    return (Path(case["_dir"]) / case["mesh"]["deck"]).resolve()


def solve_case(case: dict) -> tuple[Deck, MembraneSolution]:
    deck = read_deck(deck_path(case), case["units"])
    return deck, solve_membrane(deck)


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


def fe_results(case: dict) -> dict[str, tuple[np.ndarray, float]]:
    """Every requested quantity in the case's units, labelled `group[name]`, with the group's largest magnitude as scale."""
    deck, solution = solve_case(case)
    units = case["units"]
    out: dict[str, tuple[np.ndarray, float]] = {}
    for group, rows in case["expected"].items():
        if group == "tolerance":
            continue
        kind, _, _ = GROUPS[group]
        vectors: dict[str, np.ndarray] = {}
        for name in rows:
            for label, value in _quantity(group, name, deck, solution).items():
                vectors[label] = value if kind is None else np.array([from_si(float(v), kind, units) for v in value])
        scale = max((float(np.max(np.abs(v))) for v in vectors.values()), default=0.0)
        for label, value in vectors.items():
            out[f"{group}[{label}]"] = (value, scale)
    return out


def _quantity(group: str, name: str, deck: Deck, solution: MembraneSolution) -> dict[str, np.ndarray]:
    """The SI vectors a name stands for; `*` expands to every element."""
    mesh = solution.mesh
    if group == "rf":
        if name in deck.nsets:
            return {name: solution.reaction_of(deck.nsets[name])}
        return {name: solution.reaction[mesh.node(parse_node_name(name))]}
    if group == "u":
        return {name: solution.displacement[mesh.node(parse_node_name(name))]}
    field = solution.strain if group == "strain" else solution.section_force
    if name == "*":
        return {f"{instance}.{label}": field[e] for e, (instance, label) in enumerate(mesh.element_keys)}
    return {name: field[mesh.element(parse_element_name(name))]}


def compare(case: dict) -> tuple[list[Comparison], list[str]]:
    """Every expected number next to the kernel's, plus problems with names the case cannot produce."""
    expected = case["expected"]
    tolerance = float(expected["tolerance"])
    try:
        results = fe_results(case)
    except ValueError as exc:  # DeckError, KernelError and name errors are all ValueErrors
        return [], [str(exc)]
    comparisons: list[Comparison] = []
    problems: list[str] = []
    for group, rows in expected.items():
        if group == "tolerance":
            continue
        for name, want in rows.items():
            labels = [key for key in results if key.startswith(f"{group}[")] if name == "*" else [f"{group}[{name}]"]
            if name != "*" and labels[0] not in results:
                problems.append(f"{group}[{name}]: not a result this case produces")
                continue
            for label in labels:
                got, scale = results[label]
                for i, w in enumerate(want):
                    allowed = tolerance * (abs(w) if w != 0 else scale)
                    comparisons.append(Comparison(f"{label}[{i}]", float(w), float(got[i]), float(allowed)))
    return comparisons, problems


def disagreements(case: dict) -> list[str]:
    """Plain-language list of every expected value the kernel does not reproduce."""
    comparisons, problems = compare(case)
    mismatches = [f"{c.key}: expected {c.expected:.6g}, kernel gives {c.engine:.6g}" for c in comparisons if not c.agrees]
    return problems + mismatches
