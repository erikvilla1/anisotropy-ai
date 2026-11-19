"""The wing's hand calculation: every load case, at every station, checked ply by ply and for skin and web buckling.

One call runs the chain an engineer would work by hand for a two-spar composite wing:
section stiffness, the loads of each flight case along the span, the in-plane load in each skin
and web, the stress in every ply angle, the strength ratio by the chosen failure criterion, the
skin's and each web's buckling ratio, deflection, twist and the margins at proof and at ultimate load. It is
written on arrays over cases and stations, so every case of the envelope costs about the same as
one.

Beam theory with the section of section.py: plane sections stay plane, each skin carries the
bending as an in-plane load at its own height, the closed box carries the torque as a constant
shear flow, and each web adds its share of the vertical shear. Not modeled: shear lag, taper,
sweep, ribs as load paths, the leading and trailing edge skins, the interaction of shear with
compression in skin buckling and of the web's bending stress with its shear in web buckling, and everything sandwich.py lists. The finite element
model of the same description is the check on all of these (ADR-0115).
"""

import math
import time
from dataclasses import dataclass
from typing import Literal

import numpy as np

from ..failure import check_criterion, scaled_strength_ratios
from .aeroelastic import Aeroelastic, divergence_dynamic_pressure, equivalent_airspeed, reversal_dynamic_pressure
from .atmosphere import density_ratio
from .description import FlightEnvelope, Wing
from .loads import CaseNotRun, LoadCase, flight_cases, span_loads
from .section import BoxSection, MemberLaminate, box_section

CheckName = Literal["skin plies", "spar plies", "skin buckling", "web buckling"]
SKINS = ("upper skin", "lower skin")
SPARS = ("front spar", "rear spar")


@dataclass(frozen=True)
class Check:
    """One check of one case: how far the limit load can be scaled before it is reached, where, and the margins."""

    name: CheckName
    strength_ratio: float  # failure or buckling at this factor on the limit load; infinity when nothing loads the check
    margin_ultimate: float  # strength_ratio / ultimate factor - 1
    margin_proof: float | None  # the same at the proof factor, when the envelope gives one
    station_m: float | None  # distance from the root of the governing station
    member: str | None
    ply_angle_deg: float | None
    mode: str | None


@dataclass(frozen=True)
class SpanStations:
    """One case along the span, at limit load, SI units; arrays of one value per station."""

    y: np.ndarray
    running_lift: np.ndarray
    shear: np.ndarray
    moment: np.ndarray
    torque: np.ndarray
    deflection: np.ndarray  # m, up positive
    twist: np.ndarray  # rad, nose up positive
    skin_load: np.ndarray  # (2, stations): Nx of the upper and lower skin, N/m, tension positive
    shear_flow: np.ndarray  # the box's torsion shear flow, N/m
    web_shear_flow: np.ndarray  # (2, stations): front and rear web, N/m
    skin_ratio: np.ndarray  # (2, stations): strength ratio of the upper and lower skin's plies
    spar_ratio: np.ndarray  # (2, stations): of the front and rear web's plies
    buckling_ratio: np.ndarray  # (stations,): buckling load over the larger skin compression
    web_buckling_ratio: np.ndarray  # (2, stations): each web's buckling shear flow over its shear flow


@dataclass(frozen=True)
class CaseResult:
    case: LoadCase
    root_shear: float
    root_moment: float
    root_torque: float
    tip_deflection: float
    tip_twist: float
    checks: tuple[Check, Check, Check, Check]
    stations: SpanStations

    @property
    def governing(self) -> Check:
        """The check with the lowest margin at ultimate load."""
        return min(self.checks, key=lambda check: check.margin_ultimate)


@dataclass(frozen=True)
class WingResult:
    wing: Wing
    envelope: FlightEnvelope
    section: BoxSection
    cases: tuple[CaseResult, ...]
    not_run: tuple[CaseNotRun, ...]
    seconds: float  # time the calculation took
    aeroelastic: Aeroelastic | None = None  # divergence and aileron reversal

    @property
    def governing(self) -> tuple[CaseResult, Check] | None:
        """The case and check with the lowest margin at ultimate load, over every case that ran."""
        if not self.cases:
            return None
        case = min(self.cases, key=lambda result: result.governing.margin_ultimate)
        return case, case.governing

    @property
    def passes(self) -> bool | None:
        """Every margin of every case that ran is zero or more; None when no case ran. Cases not run are not judged."""
        if not self.cases:
            return None
        margins = [m for case in self.cases for check in case.checks for m in (check.margin_ultimate, check.margin_proof) if m is not None]
        return min(margins) >= 0


def cumulative_trapezoid(values: np.ndarray, y: np.ndarray) -> np.ndarray:
    """The integral from the root to each station by the trapezoid rule, along the last axis."""
    steps = (values[..., 1:] + values[..., :-1]) / 2 * np.diff(y)
    return np.concatenate([np.zeros(values.shape[:-1] + (1,)), np.cumsum(steps, axis=-1)], axis=-1)


def _ply_ratios(member: MemberLaminate, Nx: np.ndarray, Nxy: np.ndarray, criterion: str, f12_star: float | None):
    """Strength ratio of the weakest ply at every entry of Nx and Nxy (same shape), with its angle index and mode."""
    per_load = member.stress_per_load  # (angles, 3, 3)
    stress = Nx[..., None, None] * per_load[:, :, 0] + Nxy[..., None, None] * per_load[:, :, 2]  # (..., angles, 3)
    ratios, modes = scaled_strength_ratios(criterion, member.layup.material.lamina, stress.reshape(-1, 3), f12_star)
    ratios = ratios.reshape(stress.shape[:-1])
    weakest = np.argmin(ratios, axis=-1)
    modes = np.array(modes, dtype=object).reshape(stress.shape[:-1])
    return (np.take_along_axis(ratios, weakest[..., None], axis=-1)[..., 0], weakest,
            np.take_along_axis(modes, weakest[..., None], axis=-1)[..., 0])


def _margins(ratio: float, envelope: FlightEnvelope) -> tuple[float, float | None]:
    proof = None if envelope.proof_factor is None else ratio / envelope.proof_factor - 1
    return ratio / envelope.ultimate_factor - 1, proof


def _ply_check(name: CheckName, labels, member: MemberLaminate, ratio, weakest, modes, y, envelope) -> Check:
    """The governing entry of a (members, stations) set of ply ratios for one case."""
    if not np.isfinite(ratio).any():
        return Check(name, math.inf, *_margins(math.inf, envelope), None, None, None, None)
    k, s = np.unravel_index(np.argmin(ratio), ratio.shape)
    value = float(ratio[k, s])
    return Check(name, value, *_margins(value, envelope), float(y[s]), labels[k], float(member.angles_deg[weakest[k, s]]), modes[k, s])


def aeroelastic_checks(wing: Wing, envelope: FlightEnvelope, section: BoxSection) -> Aeroelastic:
    """Divergence and aileron reversal of the uniform wing (aeroelastic.py), with the dive speed they are read against."""
    g = wing.geometry
    torque_arm = section.shear_center_m - wing.aerodynamics.aerodynamic_center * g.chord_m
    slope = wing.aerodynamics.lift_curve_slope_per_rad
    needs = []
    dive = envelope.speeds.dive
    if dive is not None and envelope.airspeed == "true":
        dive = max(dive * math.sqrt(density_ratio(h)) for h in envelope.altitudes_m)  # the highest equivalent airspeed
    q_divergence = q_reversal = None
    if slope is None:
        needs.append("the section's lift curve slope, for divergence and reversal")
    else:
        q_divergence = divergence_dynamic_pressure(section.GJ, g.half_span_m, g.chord_m, torque_arm, slope)
        aileron = envelope.aileron
        if aileron is None:
            needs.append("the aileron, for reversal")
        else:
            down = aileron.down_delta_cl != 0
            q_reversal = reversal_dynamic_pressure(
                section.GJ, g.half_span_m, g.chord_m, torque_arm, slope,
                aileron.down_delta_cl if down else aileron.up_delta_cl, aileron.down_delta_cm if down else aileron.up_delta_cm,
                aileron.span_start_m, min(aileron.span_end_m, g.half_span_m))
    return Aeroelastic(
        divergence_dynamic_pressure_Pa=q_divergence,
        divergence_speed_m_s=None if q_divergence is None else equivalent_airspeed(q_divergence),
        reversal_dynamic_pressure_Pa=q_reversal,
        reversal_speed_m_s=None if q_reversal is None else equivalent_airspeed(q_reversal),
        dive_speed_m_s=dive, needs=tuple(needs))


def analyze_wing(wing: Wing, envelope: FlightEnvelope, stations: int = 51) -> WingResult:
    """Run every load case the envelope states on the wing, at `stations` equally spaced stations from root to tip."""
    started = time.perf_counter()
    if stations < 3:
        raise ValueError("The calculation needs at least three stations")
    for layup in (wing.skin, wing.spar):
        check_criterion(layup.plies(), envelope.criterion, envelope.f12_star)
    g = wing.geometry
    section = box_section(wing)
    cases, not_run = flight_cases(envelope, g.chord_m)
    y = np.linspace(0.0, g.half_span_m, stations)
    aeroelastic = aeroelastic_checks(wing, envelope, section)
    if not cases:
        return WingResult(wing, envelope, section, (), tuple(not_run), time.perf_counter() - started, aeroelastic)

    torque_arm = section.shear_center_m - wing.aerodynamics.aerodynamic_center * g.chord_m
    loads = span_loads(y, g.half_span_m, g.chord_m, cases, envelope, torque_arm, wing.aerodynamics.pitching_moment_coefficient)
    curvature = loads.moment / section.EI  # (cases, stations)
    shear_flow = loads.torque / (2 * section.enclosed_area_m2)
    criterion, f12_star = envelope.criterion, envelope.f12_star

    # Skins: bending as an in-plane load at the skin's height, with the box's torsion shear flow.
    skin = section.skin
    skin_z = np.array(section.skin_z_m)[:, None, None]  # (2, 1, 1)
    skin_load = -curvature * skin_z * skin.Ex * skin.thickness_m  # (2, cases, stations)
    skin_ratio, skin_weakest, skin_modes = _ply_ratios(skin, skin_load, np.broadcast_to(shear_flow, skin_load.shape), criterion, f12_star)
    compression = np.clip(-skin_load, 0, None).max(axis=0)  # the larger of the two skins
    with np.errstate(divide="ignore"):
        buckling_ratio = np.where(compression > 0, section.skin_buckling_load / compression, math.inf)

    # Webs: each web's share of the vertical shear plus the torsion flow, added whatever their signs, with the bending
    # strain at the web's top and at its bottom.
    spar = section.spar
    shares = np.array(section.shear_shares)[:, None, None]
    heights = np.array(section.spar_heights_m)[:, None, None]
    web_flow = shares * np.abs(loads.shear) / heights + np.abs(shear_flow)  # (2, cases, stations)
    web_z = np.array([section.spar_top_z_m, section.spar_bottom_z_m])[:, :, None, None]  # (top/bottom, 2, 1, 1)
    web_load = -curvature * web_z * spar.Ex * spar.thickness_m  # (2, 2, cases, stations)
    edge_ratio, edge_weakest, edge_modes = _ply_ratios(spar, web_load, np.broadcast_to(web_flow, web_load.shape), criterion, f12_star)
    worse = np.argmin(edge_ratio, axis=0)[None]
    spar_ratio, spar_weakest, spar_modes = (np.take_along_axis(a, worse, axis=0)[0] for a in (edge_ratio, edge_weakest, edge_modes))

    # Webs in shear buckling: the bay's buckling shear flow over the web's shear flow, the same flow the ply check uses.
    with np.errstate(divide="ignore"):
        web_buckling_ratio = np.where(web_flow > 0, np.array(section.web_buckling_loads)[:, None, None] / web_flow, math.inf)

    deflection = cumulative_trapezoid(cumulative_trapezoid(curvature, y), y)
    twist = cumulative_trapezoid(loads.torque / section.GJ, y)

    results = []
    for c, case in enumerate(cases):
        buckling = float(buckling_ratio[c].min())
        if math.isfinite(buckling):
            s = int(np.argmin(buckling_ratio[c]))
            member = SKINS[int(np.argmax(-skin_load[:, c, s]))]
            buckling_check = Check("skin buckling", buckling, *_margins(buckling, envelope), float(y[s]), member, None, "compression buckling")
        else:
            buckling_check = Check("skin buckling", math.inf, *_margins(math.inf, envelope), None, None, None, None)
        web = float(web_buckling_ratio[:, c].min())
        if math.isfinite(web):
            w, s = np.unravel_index(int(np.argmin(web_buckling_ratio[:, c])), web_buckling_ratio[:, c].shape)
            web_check = Check("web buckling", web, *_margins(web, envelope), float(y[s]), SPARS[int(w)], None, "shear buckling")
        else:
            web_check = Check("web buckling", math.inf, *_margins(math.inf, envelope), None, None, None, None)
        checks = (
            _ply_check("skin plies", SKINS, skin, skin_ratio[:, c], skin_weakest[:, c], skin_modes[:, c], y, envelope),
            _ply_check("spar plies", SPARS, spar, spar_ratio[:, c], spar_weakest[:, c], spar_modes[:, c], y, envelope),
            buckling_check,
            web_check,
        )
        span = SpanStations(y=y, running_lift=loads.running_lift[c], shear=loads.shear[c], moment=loads.moment[c], torque=loads.torque[c],
                            deflection=deflection[c], twist=twist[c], skin_load=skin_load[:, c], shear_flow=shear_flow[c],
                            web_shear_flow=web_flow[:, c], skin_ratio=skin_ratio[:, c], spar_ratio=spar_ratio[:, c],
                            buckling_ratio=buckling_ratio[c], web_buckling_ratio=web_buckling_ratio[:, c])
        results.append(CaseResult(case=case, root_shear=float(loads.shear[c, 0]), root_moment=float(loads.moment[c, 0]),
                                  root_torque=float(loads.torque[c, 0]), tip_deflection=float(deflection[c, -1]),
                                  tip_twist=float(twist[c, -1]), checks=checks, stations=span))
    return WingResult(wing, envelope, section, tuple(results), tuple(not_run), time.perf_counter() - started, aeroelastic)
