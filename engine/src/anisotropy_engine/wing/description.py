"""The wing description: one record of the shape, the layups and the flight envelope, in SI units.

Everything the wing calculation reads is here, and nothing is assumed for a value left out: a speed,
a gust entry, the aileron or the proof factor that is missing leaves the load cases that need it
out of the run, each named with what it needs (ADR-0003, ADR-0115).

Axes: y along the span from the root, x along the chord from the leading edge, z up. A layup's 0
degree direction is the span. Layups are given as half of a symmetric laminate, the outside ply
first; the other half mirrors it, with the core, when there is one, between the halves.

A layup may change along the span in zones, each a stretch of the half span with a half stack of its own; outside its zones a
part has its own half stack. The spar caps are a strip of each skin centred on each web, with a layup of their own (ADR-0125).
"""

import math
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, NonNegativeFloat, PositiveFloat, field_validator, model_validator

from ..failure import Criterion
from ..lamina import Lamina
from ..laminate import Ply
from ..layup_rules import RuleCheck, RuleLimits, layup_rules
from .airfoil import Airfoil
from .atmosphere import TROPOPAUSE_M

_FROZEN = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")


class StrengthSource(BaseModel):
    """Where one of a library material's strengths comes from: its basis, the record and the page (ADR-0126)."""

    model_config = _FROZEN

    role: str  # F1t, F1c, F2t, F2c or F6
    key: str  # the library property it came from: "F1c-derived", "F12-5pct"
    basis: str  # "B-basis", "B-estimate", "Measured mean", ...
    source_value: float
    source_unit: str
    page: int
    url: str


class WingMaterial(BaseModel):
    """A ply material with what a wing needs beside its stiffness: strengths, cured ply thickness and density. A library material says
    which of its datasets gave the strengths and on what basis (ADR-0126); a typed one says "typed"."""

    model_config = _FROZEN

    name: str
    lamina: Lamina
    ply_thickness_m: PositiveFloat
    density_kg_m3: PositiveFloat
    strength_basis: str = "typed"  # "B-basis", "mean" or "typed"
    strength_dataset: str | None = None  # the library dataset's label, "NCAMP 2019 · B-basis"
    strength_citation: str | None = None  # the report the strengths come from
    strength_sources: tuple[StrengthSource, ...] = ()

    @model_validator(mode="after")
    def _has_strengths(self) -> "WingMaterial":
        if self.lamina.strengths is None:
            raise ValueError(f"Material {self.name!r} needs its five strengths (F1t, F1c, F2t, F2c, F6) for the ply checks")
        return self


class CoreMaterial(BaseModel):
    """A sandwich core's stiffness and strength. The hand calculation reads only the core's density (sandwich.py takes its in-plane
    stiffness as zero and its shear stiffness as infinite); the finite element model reads these (ADR-0117)."""

    model_config = _FROZEN

    name: str
    modulus_Pa: PositiveFloat  # through the thickness, in compression
    shear_modulus_Pa: PositiveFloat  # transverse shear, the same in both directions
    shear_strength_Pa: PositiveFloat | None = None


class Zone(BaseModel):
    """A stretch of the span where a part has a half stack of its own: from `start` to `end`, fractions of the half span from the
    root (ADR-0125). The material and the core are the part's."""

    model_config = _FROZEN

    start: NonNegativeFloat
    end: PositiveFloat
    half_stack_deg: tuple[float, ...]

    @model_validator(mode="after")
    def _checked(self) -> "Zone":
        if not self.start < self.end <= 1:
            raise ValueError(f"A zone runs from its start to its end as fractions of the half span, 0 <= start < end <= 1; got {self.start:g} "
                             f"to {self.end:g}")
        if not self.half_stack_deg:
            raise ValueError("A zone needs at least one ply in its half stack")
        return self


class Layup(BaseModel):
    """A symmetric laminate by its outer half, with an optional core between the halves, and the zones of the span where its half
    stack is another (ADR-0125). `half_stack_deg` is the stack outside every zone; the properties below are of that stack."""

    model_config = _FROZEN

    material: WingMaterial
    half_stack_deg: tuple[float, ...]
    core_thickness_m: NonNegativeFloat = 0.0  # no core: a solid laminate
    core_density_kg_m3: PositiveFloat | None = None
    core: CoreMaterial | None = None  # the core's stiffness, which the finite element model needs and the hand calculation does not
    zones: tuple[Zone, ...] = ()  # in order from the root, none overlapping another

    @field_validator("zones")
    @classmethod
    def _in_order(cls, zones: tuple[Zone, ...]) -> tuple[Zone, ...]:
        ordered = tuple(sorted(zones, key=lambda zone: zone.start))
        for inner, outer in zip(ordered, ordered[1:]):
            if outer.start < inner.end:
                raise ValueError(f"Two zones overlap: {inner.start:g} to {inner.end:g} and {outer.start:g} to {outer.end:g} of the half span")
        return ordered

    @model_validator(mode="after")
    def _checked(self) -> "Layup":
        if not self.half_stack_deg:
            raise ValueError("A layup needs at least one ply in its half stack")
        if self.core_thickness_m == 0 and self.core is not None:
            raise ValueError("A core material was given without a core thickness")
        if self.core_thickness_m > 0 and self.core_density_kg_m3 is None:
            raise ValueError("A core needs its density")
        if self.core_thickness_m == 0 and self.core_density_kg_m3 is not None:
            raise ValueError("A core density was given without a core thickness")
        return self

    def face(self) -> list[Ply]:
        """The plies of one half, the outside ply first."""
        return [Ply(material=self.material.lamina, angle_deg=angle, thickness_m=self.material.ply_thickness_m)
                for angle in self.half_stack_deg]

    def plies(self) -> list[Ply]:
        """Both halves stacked without the core: the laminate that carries the in-plane load."""
        face = self.face()
        return face + face[::-1]

    def rules(self, limits: RuleLimits | None = None) -> tuple[RuleCheck, ...]:
        """The design rules on both halves, listed from one outer face to the other, the core between them (ADR-0123)."""
        return layup_rules(self.plies(), limits, core_after=len(self.half_stack_deg) if self.core_thickness_m > 0 else None)

    @property
    def fiber_thickness_m(self) -> float:
        """Thickness of the plies alone, both halves."""
        return 2 * len(self.half_stack_deg) * self.material.ply_thickness_m

    def with_stack(self, half_stack_deg: tuple[float, ...]) -> "Layup":
        """The same layup, material and core, with another half stack and no zones: what the part is inside one zone."""
        return self.model_copy(update={"half_stack_deg": tuple(half_stack_deg), "zones": ()})

    def stretches(self) -> tuple[tuple[float, float, "Layup"], ...]:
        """The part from root to tip as (start, end, uniform layup), fractions of the half span: its zones and the stretches between
        them; two neighbours of the same stack are one stretch."""
        found: list[tuple[float, float, tuple[float, ...]]] = []
        here = 0.0
        for zone in self.zones:
            if zone.start > here:
                found.append((here, zone.start, self.half_stack_deg))
            found.append((zone.start, zone.end, zone.half_stack_deg))
            here = zone.end
        if here < 1:
            found.append((here, 1.0, self.half_stack_deg))
        merged: list[tuple[float, float, tuple[float, ...]]] = []
        for start, end, stack in found:
            if merged and merged[-1][2] == stack:
                merged[-1] = (merged[-1][0], end, stack)
            else:
                merged.append((start, end, stack))
        return tuple((start, end, self.with_stack(stack)) for start, end, stack in merged)


class WingGeometry(BaseModel):
    """A straight wing of constant chord, one side, with two spars. Spar positions are fractions of the chord."""

    model_config = _FROZEN

    half_span_m: PositiveFloat
    chord_m: PositiveFloat
    airfoil: Airfoil
    front_spar: PositiveFloat
    rear_spar: PositiveFloat
    rib_spacing_m: PositiveFloat | None = None  # no ribs: the skin between the spars is one long panel

    @model_validator(mode="after")
    def _checked(self) -> "WingGeometry":
        if not self.front_spar < self.rear_spar < 1:
            raise ValueError("Spar positions must satisfy 0 < front < rear < 1 as fractions of the chord")
        for position in (self.front_spar, self.rear_spar):
            upper, lower = self.airfoil.surface_heights(position)
            if upper <= lower:
                raise ValueError(f"The airfoil has no height at {position} of the chord")
        if self.rib_spacing_m is not None and self.rib_spacing_m > self.half_span_m:
            raise ValueError("The rib spacing is longer than the half span")
        return self

    @property
    def rib_stations_m(self) -> tuple[float, ...]:
        """Where the ribs stand, metres from the root: the root, every rib spacing outboard, and the tip; none without a spacing.
        The shape, the finite element model and the page draw them here."""
        if self.rib_spacing_m is None:
            return ()
        count = math.floor(self.half_span_m / self.rib_spacing_m + 1e-9)
        stations = [k * self.rib_spacing_m for k in range(count + 1)]
        if self.half_span_m - stations[-1] > 1e-6 * self.half_span_m:
            stations.append(self.half_span_m)
        else:
            stations[-1] = self.half_span_m
        return tuple(stations)


class Aerodynamics(BaseModel):
    """Where the lift acts on the section and the airfoil's pitching moment coefficient about that point (nose up positive)."""

    model_config = _FROZEN

    aerodynamic_center: PositiveFloat  # fraction of the chord
    pitching_moment_coefficient: float
    lift_curve_slope_per_rad: PositiveFloat | None = None  # the section's; the divergence and reversal checks need it

    @model_validator(mode="after")
    def _checked(self) -> "Aerodynamics":
        if not self.aerodynamic_center < 1:
            raise ValueError("The aerodynamic center is a fraction of the chord, between 0 and 1")
        return self


class SparCaps(BaseModel):
    """The spar caps: a strip of the upper and of the lower skin centred on each web, as wide as given along the chord, with a layup
    of its own in place of the skin's (ADR-0125). A cap is a solid laminate: the skin's core, when it has one, stops at its edge."""

    model_config = _FROZEN

    front_width_m: PositiveFloat
    rear_width_m: PositiveFloat
    layup: Layup

    @model_validator(mode="after")
    def _checked(self) -> "SparCaps":
        if self.layup.core_thickness_m > 0:
            raise ValueError("A spar cap is a solid laminate: give it no core")
        return self


class Wing(BaseModel):
    """One wing: its shape, the skin, spar and rib layups, its spar caps and its section aerodynamics."""

    model_config = _FROZEN

    name: str
    geometry: WingGeometry
    skin: Layup
    spar: Layup
    aerodynamics: Aerodynamics
    rib: Layup | None = None  # the ribs' layup, when the geometry has ribs; the hand calculation does not use it
    design_rules: RuleLimits = RuleLimits()  # the limits its layups are judged by (ADR-0123); they change no number of the analysis
    spar_caps: SparCaps | None = None  # no caps: the skin's layup runs from spar to spar (ADR-0125)

    @model_validator(mode="after")
    def _checked(self) -> "Wing":
        if self.rib is not None and self.geometry.rib_spacing_m is None:
            raise ValueError("A rib layup was given but no rib spacing")
        if self.rib is not None and self.rib.zones:
            raise ValueError("A rib stands at one station: it has no zones along the span")
        caps = self.spar_caps
        if caps is not None:
            g = self.geometry
            front, rear = g.front_spar * g.chord_m, g.rear_spar * g.chord_m
            if front + caps.front_width_m / 2 >= rear - caps.rear_width_m / 2:
                raise ValueError("The spar caps meet between the spars: together they are wider than the box")
            if front - caps.front_width_m / 2 <= 0:
                raise ValueError("The front spar cap reaches the leading edge: make it narrower")
            if rear + caps.rear_width_m / 2 >= g.chord_m:
                raise ValueError("The rear spar cap reaches the trailing edge: make it narrower")
        return self

    @property
    def cap_edges_m(self) -> tuple[float, float, float, float] | None:
        """The chord positions of the caps' edges, metres from the leading edge: front cap fore and aft, rear cap fore and aft."""
        caps = self.spar_caps
        if caps is None:
            return None
        g = self.geometry
        front, rear = g.front_spar * g.chord_m, g.rear_spar * g.chord_m
        return (front - caps.front_width_m / 2, front + caps.front_width_m / 2, rear - caps.rear_width_m / 2, rear + caps.rear_width_m / 2)

    @property
    def has_zones(self) -> bool:
        return any(layup.zones for layup in (self.skin, self.spar, None if self.spar_caps is None else self.spar_caps.layup)
                   if layup is not None)


@dataclass(frozen=True)
class SpanSegment:
    """A stretch of the span over which no layup changes, metres from the root, with each part's layup there."""

    start_m: float
    end_m: float
    skin: Layup
    spar: Layup
    cap: Layup | None  # None without spar caps


def span_segments(wing: Wing) -> tuple[SpanSegment, ...]:
    """The wing from root to tip in stretches of constant layup: a new one starts wherever any part's zone starts or ends and its
    stack changes there (ADR-0125). A wing without zones is one segment."""
    parts = {"skin": wing.skin.stretches(), "spar": wing.spar.stretches(),
             "cap": None if wing.spar_caps is None else wing.spar_caps.layup.stretches()}
    edges = sorted({0.0, 1.0} | {edge for stretches in parts.values() if stretches for start, end, _ in stretches for edge in (start, end)})

    def at(stretches, middle: float) -> Layup | None:
        if stretches is None:
            return None
        return next(layup for start, end, layup in stretches if start <= middle < end)

    L = wing.geometry.half_span_m
    segments: list[SpanSegment] = []
    for start, end in zip(edges, edges[1:]):
        middle = (start + end) / 2
        segment = SpanSegment(start * L, end * L, at(parts["skin"], middle), at(parts["spar"], middle), at(parts["cap"], middle))
        if segments and (segments[-1].skin, segments[-1].spar, segments[-1].cap) == (segment.skin, segment.spar, segment.cap):
            segments[-1] = SpanSegment(segments[-1].start_m, segment.end_m, segment.skin, segment.spar, segment.cap)
        else:
            segments.append(segment)
    return tuple(segments)


class Speeds(BaseModel):
    """The speeds of the flight envelope, in m/s, all of one kind (FlightEnvelope.airspeed). One left out leaves its cases out."""

    model_config = _FROZEN

    stall_flaps: PositiveFloat | None = None
    stall_clean: PositiveFloat | None = None
    cruise: PositiveFloat | None = None
    dive: PositiveFloat | None = None
    flutter: PositiveFloat | None = None
    positive_maneuver: PositiveFloat | None = None  # the speed of the positive high angle of attack corner
    negative_maneuver: PositiveFloat | None = None  # the speed of the negative high angle of attack corner


class GustLoadFactors(BaseModel):
    """The four gust load factors, stated by the engineer."""

    model_config = _FROZEN

    cruise_positive: float
    cruise_negative: float
    dive_positive: float
    dive_negative: float


class GustSpeeds(BaseModel):
    """Derived gust speeds, from which the gust load factors are computed (14 CFR 23.341(c) before Amendment 23-64)."""

    model_config = _FROZEN

    cruise_gust_speed_m_s: PositiveFloat
    dive_gust_speed_m_s: PositiveFloat
    lift_curve_slope_per_rad: PositiveFloat
    wing_area_m2: PositiveFloat  # the reference area the wing loading uses


class Aileron(BaseModel):
    """An aileron as a change of section lift and moment coefficient over its span, trailing edge down and up."""

    model_config = _FROZEN

    span_start_m: NonNegativeFloat
    span_end_m: PositiveFloat
    down_delta_cl: float
    down_delta_cm: float
    up_delta_cl: float
    up_delta_cm: float
    roll_pull_up_fraction: PositiveFloat  # the roll pull-up case flies at this fraction of the positive load factor

    @model_validator(mode="after")
    def _checked(self) -> "Aileron":
        if self.span_end_m <= self.span_start_m:
            raise ValueError("The aileron's span must end outboard of where it starts")
        if self.roll_pull_up_fraction > 1:
            raise ValueError("The roll pull-up fraction is at most 1")
        return self


class FlightEnvelope(BaseModel):
    """The weight, load factors, speeds and altitudes the load cases are built from, and the factors the margins use."""

    model_config = _FROZEN

    gross_weight_N: PositiveFloat
    positive_load_factor: PositiveFloat
    negative_load_factor: float
    airspeed: Literal["equivalent", "true"]
    speeds: Speeds
    altitudes_m: tuple[float, ...]
    ultimate_factor: float
    proof_factor: float | None = None
    criterion: Criterion
    f12_star: float | None = None
    gust: GustLoadFactors | GustSpeeds | None = None
    aileron: Aileron | None = None

    @model_validator(mode="after")
    def _checked(self) -> "FlightEnvelope":
        if self.negative_load_factor >= 0:
            raise ValueError("The negative load factor must be below zero")
        if not self.altitudes_m:
            raise ValueError("The envelope needs at least one altitude")
        if len(set(self.altitudes_m)) != len(self.altitudes_m):
            raise ValueError("An altitude is listed twice")
        for altitude in self.altitudes_m:
            if not 0 <= altitude <= TROPOPAUSE_M:
                raise ValueError(f"Altitudes must be between 0 and {TROPOPAUSE_M:.0f} m, got {altitude}")
        if self.ultimate_factor < 1:
            raise ValueError("The ultimate factor must be at least 1")
        if self.proof_factor is not None and not 1 <= self.proof_factor <= self.ultimate_factor:
            raise ValueError("The proof factor must be between 1 and the ultimate factor")
        if self.criterion == "tsai_wu" and self.f12_star is None:
            raise ValueError("Tsai-Wu needs f12_star")
        if self.criterion != "tsai_wu" and self.f12_star is not None:
            raise ValueError("f12_star is used by Tsai-Wu only")
        return self
