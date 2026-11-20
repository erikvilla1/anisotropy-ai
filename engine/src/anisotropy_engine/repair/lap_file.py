"""A stepped lap stated as a table (a TOML file or a dict) in a unit system, and its answer in the same units (ADR-0130).

    units = "mm-MPa"                 # or "SI", "US", "psi": the systems of units.py
    [adhesive]  shear_modulus, thickness, shear_strength (optional), plastic_strain (optional)
    [[steps]]   length, outer_thickness, outer_modulus, inner_thickness, inner_modulus    (from the patch's tip)
    [applied]   load                 # per unit width, tension positive

A shear modulus is entered in the system's unit of stress, an adherend's modulus in its unit of modulus. Nothing is
guessed: a missing value, an unknown key or an unknown unit system is refused (ADR-0003).
"""

from ..units import UNIT_SYSTEMS
from .step_lap import Adhesive, Step, StepLap, elastic_limit_load, step_constants, step_lap

ADHESIVE_KEYS = {"shear_modulus": "stress", "thickness": "length", "shear_strength": "stress", "plastic_strain": None}
STEP_KEYS = {"length": "length", "outer_thickness": "length", "outer_modulus": "modulus", "inner_thickness": "length", "inner_modulus": "modulus"}


def _table(data: dict, name: str, keys: dict, required: set[str]) -> dict:
    if not isinstance(data, dict):
        raise ValueError(f"{name} must be a table of values")
    unknown = sorted(set(data) - set(keys))
    if unknown:
        raise ValueError(f"{name} has values this calculation does not read: {', '.join(unknown)}")
    missing = sorted(required - set(data))
    if missing:
        raise ValueError(f"{name} is missing: {', '.join(missing)}")
    return data


def _system(units: object) -> dict:
    if units not in UNIT_SYSTEMS:
        raise ValueError(f"units must be one of {', '.join(UNIT_SYSTEMS)}, got {units!r}")
    return UNIT_SYSTEMS[units]


def lap_from_dict(data: dict) -> StepLap:
    """The stepped lap a table states, solved."""
    system = _system(data.get("units"))
    si = lambda value, quantity: value if quantity is None else value * system[quantity][0]  # noqa: E731
    stated = _table(data.get("adhesive"), "The adhesive", ADHESIVE_KEYS, {"shear_modulus", "thickness"})
    adhesive = Adhesive(si(stated["shear_modulus"], "stress"), si(stated["thickness"], "length"),
                        si(stated["shear_strength"], "stress") if "shear_strength" in stated else None, stated.get("plastic_strain", 0.0))
    rows = data.get("steps")
    if not isinstance(rows, list) or not rows:
        raise ValueError("A lap needs at least one step")
    steps = []
    for number, row in enumerate(rows, 1):
        stated = _table(row, f"Step {number}", STEP_KEYS, set(STEP_KEYS))
        steps.append(Step(*(si(stated[key], quantity) for key, quantity in STEP_KEYS.items())))
    applied = _table(data.get("applied"), "The applied load", {"load": "N"}, {"load"})
    return step_lap(steps, adhesive, si(applied["load"], "N"))


def lap_report(lap: StepLap, units: str) -> dict:
    """The answer in a unit system: each step's lambda times its length (no unit) and the force the outer adherend would
    carry if the adherends strained alike, the outer adherend's force at every step boundary, the shear stress at the two
    ends of every step, the largest one with its place, the largest stress in each adherend of every step, and, when the
    adhesive has a strength, the load at its elastic limit."""
    system = _system(units)
    force, stress = system["N"][0], system["stress"][0]
    constants = [step_constants(step, lap.adhesive, lap.load_n_per_m) for step in lap.steps]
    value, step, end = lap.peak_shear
    report = {
        "units": {"force": system["N"][1], "stress": system["stress"][1], "length": system["length"][1]},
        "lambda_length": [lam * step_.length_m for (lam, _), step_ in zip(constants, lap.steps)],
        "shared_forces": [shared / force for _, shared in constants],
        "boundary_forces": [float(value_) / force for value_ in lap.forces],
        "shear_at_ends": [[float(a) / stress, float(b) / stress] for a, b in lap.shear_at_ends],
        "peak_shear": {"value": value / stress, "step": step + 1, "end": end},
        "adherend_stresses": [[float(a) / stress, float(b) / stress] for a, b in lap.adherend_stresses()],
    }
    if lap.adhesive.shear_strength_pa is not None and value != 0:
        report["elastic_limit_load"] = elastic_limit_load(lap) / force
    return report
