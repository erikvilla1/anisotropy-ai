"""The wing description: one record of the shape, the layups and the flight envelope, in SI units.

Everything the wing calculation reads is here, and nothing is assumed for a value left out: a speed,
a gust entry, the aileron or the proof factor that is missing leaves the load cases that need it
out of the run, each named with what it needs (ADR-0003, ADR-0115).

Axes: y along the span from the root, x along the chord from the leading edge, z up. A layup's 0
degree direction is the span. Layups are given as half of a symmetric laminate, the outside ply
first; the other half mirrors it, with the core, when there is one, between the halves.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, NonNegativeFloat, PositiveFloat, model_validator

from ..failure import Criterion
from ..lamina import Lamina
from ..laminate import Ply
from .airfoil import Airfoil
from .atmosphere import TROPOPAUSE_M

_FROZEN = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")


class WingMaterial(BaseModel):
    """A ply material with what a wing needs beside its stiffness: strengths, cured ply thickness and density."""

    model_config = _FROZEN

    name: str
    lamina: Lamina
    ply_thickness_m: PositiveFloat
    density_kg_m3: PositiveFloat

    @model_validator(mode="after")
    def _has_strengths(self) -> "WingMaterial":
        if self.lamina.strengths is None:
            raise ValueError(f"Material {self.name!r} needs its five strengths (F1t, F1c, F2t, F2c, F6) for the ply checks")
        return self


class Layup(BaseModel):
    """A symmetric laminate by its outer half, with an optional core between the halves."""

    model_config = _FROZEN

    material: WingMaterial
    half_stack_deg: tuple[float, ...]
    core_thickness_m: NonNegativeFloat = 0.0  # no core: a solid laminate
    core_density_kg_m3: PositiveFloat | None = None

    @model_validator(mode="after")
    def _checked(self) -> "Layup":
        if not self.half_stack_deg:
            raise ValueError("A layup needs at least one ply in its half stack")
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

    @property
    def fiber_thickness_m(self) -> float:
        """Thickness of the plies alone, both halves."""
        return 2 * len(self.half_stack_deg) * self.material.ply_thickness_m


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


class Aerodynamics(BaseModel):
    """Where the lift acts on the section and the airfoil's pitching moment coefficient about that point (nose up positive)."""

    model_config = _FROZEN

    aerodynamic_center: PositiveFloat  # fraction of the chord
    pitching_moment_coefficient: float

    @model_validator(mode="after")
    def _checked(self) -> "Aerodynamics":
        if not self.aerodynamic_center < 1:
            raise ValueError("The aerodynamic center is a fraction of the chord, between 0 and 1")
        return self


class Wing(BaseModel):
    """One wing: its shape, the skin and spar layups and its section aerodynamics."""

    model_config = _FROZEN

    name: str
    geometry: WingGeometry
    skin: Layup
    spar: Layup
    aerodynamics: Aerodynamics


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
