"""A reference solver's results and our kernel's, element by element, on two decks of the same model (ADR-0035).

The reference values are Abaqus/CAE field reports (`abaqus_report.read_field_report`), numbered as in the reference deck.
`equivalence.deck_equivalence` has matched every reference element to one of ours by its corner nodes; this module puts our
kernel's value for the same element, layer and quantity beside each reference value, checks that the two centroids coincide,
and summarises the agreement over a band of the coupon. Values are in the reports' unit system, stated by the caller.

Quantities: S11, S22, S12 are the ply stress in its material axes (Abaqus reports S at a composite section point in the
ply's axes; the 2026-10-18 comparison confirmed this for 0-degree plies), Mises the plane-stress von Mises value of the
same state (`recovery.ply_mises`). Layers count from 1 at the bottom, as Abaqus numbers them and as ADR-0004 lists plies.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .abaqus_report import FieldReport, instance_in_deck
from .equivalence import DeckEquivalence
from .mesh import KernelError
from .model import Deck
from .recovery import element_ply_states, ply_mises
from .results import MembraneSolution
from .units import from_si, to_si

COMPONENT = {"S11": 0, "S22": 1, "S12": 2}
CENTROID_TOLERANCE = 1e-6  # m: a report prints centroids to about six digits; a mapped element's centroid must lie this close


@dataclass(frozen=True)
class PairedValue:
    quantity: str
    layer: int  # 1 at the bottom
    reference_element: int  # label in the reference deck
    our_element: int  # label in our deck
    x: float  # the reference's reported centroid, in the stated units
    y: float
    reference: float
    ours: float

    @property
    def difference(self) -> float:
        return self.ours - self.reference


@dataclass(frozen=True)
class Agreement:
    """How one quantity agrees over a band of the coupon: the largest difference as a fraction of the largest reference magnitude."""

    quantity: str
    band: str
    y_range: tuple[float, float]  # element centroids with lo <= y <= hi, stated units
    count: int
    largest: float  # max |reference| in the band
    worst: PairedValue | None
    within: int  # values whose |difference| is at most `fraction` times `largest`
    fraction: float

    @property
    def worst_fraction(self) -> float:
        return abs(self.worst.difference) / self.largest if self.worst is not None and self.largest > 0 else 0.0


def ply_values(solution: MembraneSolution, units: str) -> dict[str, np.ndarray]:
    """Quantity -> (elements, plies) array in the stated stress unit: S11, S22, S12 in material axes and Mises."""
    field = element_ply_states(solution)
    plies = {len(s) for s in field.stress_12}
    if len(plies) != 1:
        raise KernelError("side-by-side values need one ply count over the mesh (one section)")
    stress = np.stack(field.stress_12)
    mises = np.stack(ply_mises(field))[:, :, 0]
    convert = lambda a: from_si(a, "stress", units)  # noqa: E731
    return {"S11": convert(stress[:, :, 0]), "S22": convert(stress[:, :, 1]), "S12": convert(stress[:, :, 2]), "Mises": convert(mises)}


def element_centroid(solution: MembraneSolution, index: int) -> np.ndarray:
    """SI centroid of one kernel element: the mean of its four corner nodes."""
    return solution.mesh.xy[solution.mesh.connectivity[index, :4]].mean(axis=0)


def pair_reports(reports: list[FieldReport], reference: Deck, solution: MembraneSolution, equivalence: DeckEquivalence, units: str) -> list[PairedValue]:
    """Every value of every report beside our kernel's value for the same element, layer and quantity."""
    values = ply_values(solution, units)
    plies = next(iter(values.values())).shape[1]
    position = {key: i for i, key in enumerate(solution.mesh.element_keys)}
    paired: list[PairedValue] = []
    for report in reports:
        if report.quantity not in values:
            raise KernelError(f"{report.path}: quantity {report.quantity!r} has no kernel counterpart; use S11, S22, S12 or Mises")
        instance = instance_in_deck(report, reference)
        for (element, layer), value in sorted(report.values.items()):
            key = (instance, element)
            if key not in equivalence.element_map:
                raise KernelError(f"{report.path}: element {element} is not matched to one of ours")
            if not 1 <= layer <= plies:
                raise KernelError(f"{report.path}: element {element} reports layer {layer}; the laminate has {plies} plies")
            ours_key = equivalence.element_map[key]
            index = position[ours_key]
            x, y = report.centroids[element]
            offset = float(np.linalg.norm(element_centroid(solution, index) - np.array([to_si(x, "length", units), to_si(y, "length", units)])))
            if offset > CENTROID_TOLERANCE:
                raise KernelError(f"{report.path}: element {element} is reported at ({x:g}, {y:g}); our matched element {ours_key[1]} has its centroid "
                                  f"{offset:g} m away")
            paired.append(PairedValue(report.quantity, layer, element, ours_key[1], x, y, float(value), float(values[report.quantity][index, layer - 1])))
    return paired


def agreement(paired: list[PairedValue], quantity: str, band: str, y_range: tuple[float, float], fraction: float) -> Agreement:
    """The agreement of one quantity over the elements whose centroid lies in the band."""
    lo, hi = y_range
    members = [p for p in paired if p.quantity == quantity and lo <= p.y <= hi]
    if not members:
        return Agreement(quantity, band, y_range, 0, 0.0, None, 0, fraction)
    largest = max(abs(p.reference) for p in members)
    worst = max(members, key=lambda p: abs(p.difference))
    within = sum(abs(p.difference) <= fraction * largest for p in members)
    return Agreement(quantity, band, y_range, len(members), largest, worst, within, fraction)


def kernel_difference(reference_solution: MembraneSolution, our_solution: MembraneSolution, equivalence: DeckEquivalence, units: str) -> tuple[float, float]:
    """Our kernel run on both decks: the largest difference of any ply stress component over all matched elements, and the
    largest such stress, both in the stated unit. Zero up to the node offsets shows that the decks are the same model."""
    ref, ours = ply_values(reference_solution, units), ply_values(our_solution, units)
    ref_position = {key: i for i, key in enumerate(reference_solution.mesh.element_keys)}
    our_position = {key: i for i, key in enumerate(our_solution.mesh.element_keys)}
    pairs = [(ref_position[r], our_position[o]) for r, o in equivalence.element_map.items()]
    ri, oi = np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs])
    largest_difference = max(float(np.abs(ref[q][ri] - ours[q][oi]).max()) for q in ("S11", "S22", "S12"))
    largest = max(float(np.abs(ref[q][ri]).max()) for q in ("S11", "S22", "S12"))
    return largest_difference, largest
