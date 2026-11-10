"""The quantities a test standard reports, read from the solved coupon (ADR-0072, part 3).

A test reduces its record to a few numbers: the area of the cross-section, the stress as force over area, the strain an extensometer or a
strain gauge reads, the chord modulus between two strains, Poisson's ratio, and for an open hole the net section. A linear model gives each
of them at the load it was solved for and, scaled, at any other: the formulas below are the standards' own (each names its clause), applied
to the model's reaction and to the displacements of two nodes placed where the strain measurement's ends sit.

Two things a model cannot give are named apart, never written as the standard's quantity:
- the ultimate strength (D3039 Eq 5, C1869 Eq 3 and 4) is the maximum force a test reaches; a linear model has none. The first-ply failure
  stress below is the load at which the first ply fails by the chosen criterion, divided by the area: a different number, named as such;
- the transition strain, the proportional limit and the percent bending need a nonlinear response or two faces of a bent coupon.

Everything here works in SI; `method_summary` writes the block in the coupon's stated units (ADR-0002, ADR-0061).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from anisotropy_engine.engineering import engineering_constants

from .spec import full_angles, section_width, spec_ply_thickness
from .standards import PROFILES
from .units import UNIT_LABEL, from_si

CHORD_RANGE = (1000e-6, 3000e-6)  # D3039 Table 3: the chord modulus between 1000 and 3000 microstrain
NOTE_B_STRAIN = 6000e-6  # D3039 Table 3 note B: below this failure strain the chord range moves to 25 to 50 % of the ultimate
STRAIN_PROBES = ("extensometer_bottom", "extensometer_top")  # the probe nodes at the strain measurement's ends, placed by the form


def gross_area(width: float, thickness: float) -> float:
    """The cross-section the standards divide by, the hole disregarded: width times thickness (D3039 §11.2.2, C1869 Eq 2)."""
    return width * thickness


def net_area(width: float, thickness: float, hole_diameter: float) -> float:
    """The cross-section through an open hole: the width less the hole, times the thickness (C1869 Eq 5)."""
    return (width - hole_diameter) * thickness


def engineering_stress(force: float, area: float) -> float:
    """Force over area (D3039 Eq 6, C1869 Eq 1)."""
    return force / area


def extensometer_strain(v_bottom: float, v_top: float, y_bottom: float, y_top: float) -> float:
    """The strain a measurement between two points along the load reads: their change of distance over their distance (D3039 Eq 7)."""
    return (v_top - v_bottom) / (y_top - y_bottom)


def chord_modulus(stress: float, strain: float, low: float = CHORD_RANGE[0], high: float = CHORD_RANGE[1]) -> tuple[float, float, float]:
    """The stresses at the two strains of the chord and the chord modulus between them (D3039 Eq 8), from one point of a linear response:
    the stress at a strain is the stress solved for scaled by the ratio of the strains, so the chord equals stress over strain."""
    at_low, at_high = stress * low / strain, stress * high / strain
    return at_low, at_high, (at_high - at_low) / (high - low)


def poisson_ratio(transverse_strain: float, longitudinal_strain: float) -> float:
    """Minus the transverse strain over the longitudinal strain (D3039 Eq 9), from one point of a linear response."""
    return -transverse_strain / longitudinal_strain


@dataclass(frozen=True)
class MethodInputs:
    """What the test-method quantities need of the spec, in SI."""

    designation: str | None  # the standard named, or None when only a strain measurement is stated
    kind: str
    width: float  # the section the load is read over: a dog-bone's narrow section (ADR-0075)
    thickness: float
    hole_diameter: float | None
    device: str | None  # "extensometer" or "strain gauge"
    gauge_length: float | None  # as stated; the modelled length is the distance of the two probe nodes


def method_inputs(spec) -> MethodInputs | None:
    """The inputs of a spec that names a standard or states a strain measurement; None otherwise. The spec must be in SI."""
    if spec.test_method is None and spec.strain is None:
        return None
    g = spec.geometry
    return MethodInputs(designation=PROFILES[spec.test_method.id].designation if spec.test_method is not None else None, kind=spec.kind,
                        width=section_width(spec), thickness=len(full_angles(spec)) * spec_ply_thickness(spec), hole_diameter=g.hole_diameter,
                        device=spec.strain.device if spec.strain is not None else None,
                        gauge_length=spec.strain.gauge_length if spec.strain is not None else None)


def method_summary(inputs: MethodInputs, xy: np.ndarray, displacement: np.ndarray, probe_nodes: dict[str, int], force: float, plies: list,
                   failures: dict[str, dict[str, Any]], failures_basis: str, units: str, node_names: list[str]) -> dict[str, Any]:
    """The block `fields.field_data` writes as `summary["test_method"]`, every value in the stated units at full precision.

    `force` is the force the coupon carries along its length (positive in tension); `probe_nodes` maps the probes' names to node indexes;
    `failures` is the summary's first-ply failure by criterion (each with its `factor`), taken over `failures_basis`."""
    length = lambda v: float(from_si(v, "length", units))  # noqa: E731
    area_of = lambda v: float(from_si(v, "area", units))  # noqa: E731
    stress_of = lambda v: float(from_si(v, "stress", units))  # noqa: E731
    w, h, d = inputs.width, inputs.thickness, inputs.hole_diameter
    area = gross_area(w, h)
    stress = engineering_stress(force, area)
    block: dict[str, Any] = {
        "designation": inputs.designation, "width": length(w), "thickness": length(h), "area": area_of(area), "force": float(from_si(force, "force", units)),
        "stress": stress_of(stress), "hole": None, "strain": None,
        "units": {"length": UNIT_LABEL[units]["length"], "area": UNIT_LABEL[units]["area"], "force": UNIT_LABEL[units]["force"],
                  "stress": UNIT_LABEL[units]["stress"], "modulus": UNIT_LABEL[units]["modulus"]},
    }
    if d is not None:
        net = net_area(w, h, d)
        block["hole"] = {"diameter": length(d), "net_area": area_of(net), "net_stress": stress_of(engineering_stress(force, net)),
                         "width_to_hole": w / d, "hole_to_thickness": d / h}
    constants = engineering_constants(plies)
    block["laminate_theory"] = {"modulus": float(from_si(constants.Ey, "modulus", units)), "poisson": float(constants.nu_yx),
                                "note": "the laminate's modulus along the pull and its Poisson's ratio from the engine's ABD (classical laminate theory)"}
    strain = None
    if inputs.device is not None and all(name in probe_nodes for name in STRAIN_PROBES):
        bottom, top = (probe_nodes[name] for name in STRAIN_PROBES)
        y_bottom, y_top = float(xy[bottom, 1]), float(xy[top, 1])
        strain = extensometer_strain(float(displacement[bottom, 1]), float(displacement[top, 1]), y_bottom, y_top)
        at_low, at_high, modulus = chord_modulus(stress, strain)
        entry: dict[str, Any] = {
            "device": inputs.device, "gauge_length": length(inputs.gauge_length), "modelled_length": length(y_top - y_bottom),
            "nodes": [node_names[bottom], node_names[top]], "x": [length(xy[bottom, 0]), length(xy[top, 0])], "value": float(strain),
            "microstrain": float(strain * 1e6),
            "chord": {"from": CHORD_RANGE[0], "to": CHORD_RANGE[1], "stress_from": stress_of(at_low), "stress_to": stress_of(at_high),
                      "force_from": float(from_si(at_low * area, "force", units)), "force_to": float(from_si(at_high * area, "force", units)),
                      "modulus": float(from_si(modulus, "modulus", units))},
            "poisson": None,
        }
        if d is None:  # across the width at mid-length: on an open hole that section is the hole's, so no Poisson's ratio there
            middle = float(xy[:, 1].min() + xy[:, 1].max()) / 2.0
            left = int(np.argmin(np.hypot(xy[:, 0] - xy[:, 0].min(), xy[:, 1] - middle)))
            right = int(np.argmin(np.hypot(xy[:, 0] - xy[:, 0].max(), xy[:, 1] - middle)))
            transverse = (float(displacement[right, 0]) - float(displacement[left, 0])) / (float(xy[right, 0]) - float(xy[left, 0]))
            entry["poisson"] = float(poisson_ratio(transverse, strain))
            entry["transverse_nodes"] = [node_names[left], node_names[right]]
        block["strain"] = entry
    block["fpf"] = {}
    for criterion, found in failures.items():
        factor = float(found["factor"])
        row: dict[str, Any] = {"factor": factor, "force": float(from_si(factor * force, "force", units)), "stress": stress_of(factor * stress),
                               "place": found.get("place")}
        if d is not None:
            row["net_stress"] = stress_of(factor * engineering_stress(force, net_area(w, h, d)))
        if strain is not None:
            row["strain"] = float(factor * strain)
            row["microstrain"] = float(factor * strain * 1e6)
        block["fpf"][criterion] = row
    block["fpf_basis"] = failures_basis
    block["earliest"] = min(block["fpf"], key=lambda c: block["fpf"][c]["factor"]) if block["fpf"] else None
    first = block["fpf"].get(block["earliest"]) if block["earliest"] else None
    block["note_b"] = bool(first is not None and "strain" in first and abs(first["strain"]) < NOTE_B_STRAIN)
    return block
