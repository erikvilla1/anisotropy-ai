"""The wing's hand calculation: every load case, at every station, checked ply by ply and for skin and web buckling.

One call runs the chain an engineer would work by hand for a two-spar composite wing:
section stiffness, the loads of each flight case along the span, the in-plane load in each skin
and web, the stress in every ply angle, the strength ratio by the chosen failure criterion, the
skin's and each web's buckling ratio, deflection, twist and the margins at proof and at ultimate load. It is
written on arrays over cases and stations, so every case of the envelope costs about the same as
one.

Beam theory with the thin-walled section of section.py: plane sections stay plane, so the lift's moment puts an in-plane
load at every point of the skins and webs in proportion to its distance from the inclined neutral axis; the vertical shear,
acting at the shear center, and the torque about it each put a shear flow round the closed box, and the two are added with
their signs. Every ply angle is checked at every point. Not modeled: shear lag, taper, sweep, ribs as load paths, the leading
and trailing edge skins, the interaction of shear with compression in skin buckling and of the web's bending stress with its
shear in web buckling, and everything sandwich.py lists. The finite element model of the same description is the check on
all of these (ADR-0115, ADR-0117).
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
from .section import BoxSection, MemberLaminate, WallPoints, box_section

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
    point_m: tuple[float, float] | None = None  # (x from the leading edge, z up from the chord line) of the governing ply's point


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
    skin_load: np.ndarray  # (2, stations): the mean Nx of the upper and lower skin across the chord, N/m, tension positive
    shear_flow: np.ndarray  # the torque's shear flow round the box, N/m, along the walls' axis (section.WallPoints)
    web_shear_flow: np.ndarray  # (2, stations): the size of the front and rear web's mean shear flow, N/m
    skin_ratio: np.ndarray  # (2, stations): strength ratio of the upper and lower skin's plies
    spar_ratio: np.ndarray  # (2, stations): of the front and rear web's plies
    buckling_ratio: np.ndarray  # (stations,): the lower of the two skins' buckling load over their mean compression
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


def _ply_stress(member: MemberLaminate, Nx: np.ndarray, Nxy: np.ndarray, curvature: np.ndarray) -> np.ndarray:
    """[sigma1, sigma2, tau12] of each ply angle's outermost ply, at its outer face on the outward side and on the inward side, at
    every entry of Nx, Nxy and the wall's own spanwise curvature (same shape): (..., 2 * angles, 3), outward side first."""
    per_load = member.stress_per_load  # (angles, 3, 3)
    stress = Nx[..., None, None] * per_load[:, :, 0] + Nxy[..., None, None] * per_load[:, :, 2]  # (..., angles, 3)
    bending = curvature[..., None, None] * member.stress_per_curvature
    return np.concatenate([stress + bending, stress - bending], axis=-2)


def _margins(ratio: float, envelope: FlightEnvelope) -> tuple[float, float | None]:
    proof = None if envelope.proof_factor is None else ratio / envelope.proof_factor - 1
    return ratio / envelope.ultimate_factor - 1, proof


def _wall_ratios(member: MemberLaminate, walls: WallPoints, moment: np.ndarray, shear: np.ndarray, torsion_flow: np.ndarray,
                 criterion: str, f12_star: float | None):
    """The weakest ply of two walls at every case and station, over every point of each wall: ratio, angle index and mode,
    each (2, cases, stations), and the index of the point. Every state's ratio is found first and only the weakest named."""
    Nx = walls.load_per_moment[:, :, None, None] * moment  # (2, points, cases, stations)
    Nxy = walls.flow_per_shear[:, :, None, None] * shear + torsion_flow
    curvature = walls.curvature_per_moment[:, :, None, None] * moment
    stress = _ply_stress(member, Nx, Nxy, curvature)  # (2, points, cases, stations, 2 * angles, 3)
    lamina = member.layup.material.lamina
    ratios, _ = scaled_strength_ratios(criterion, lamina, stress.reshape(-1, 3), f12_star, with_modes=False)
    ratios = ratios.reshape(stress.shape[:-1])
    ply = np.argmin(ratios, axis=-1)
    ratio = np.take_along_axis(ratios, ply[..., None], axis=-1)[..., 0]  # (2, points, cases, stations)
    point = np.argmin(ratio, axis=1)
    ply = np.take_along_axis(ply, point[:, None], axis=1)[:, 0]  # (2, cases, stations)
    weakest = stress[np.arange(2)[:, None, None], point, np.arange(ratio.shape[2])[:, None], np.arange(ratio.shape[3]), ply]
    chosen, modes = scaled_strength_ratios(criterion, lamina, weakest.reshape(-1, 3), f12_star)
    return chosen.reshape(ply.shape), ply % len(member.angles_deg), np.array(modes, dtype=object).reshape(ply.shape), point


def _ply_check(name: CheckName, labels, member: MemberLaminate, walls: WallPoints, ratio, weakest, modes, point, y, envelope) -> Check:
    """The governing entry of a (members, stations) set of ply ratios for one case."""
    if not np.isfinite(ratio).any():
        return Check(name, math.inf, *_margins(math.inf, envelope), None, None, None, None)
    k, s = np.unravel_index(np.argmin(ratio), ratio.shape)
    value, j = float(ratio[k, s]), int(point[k, s])
    return Check(name, value, *_margins(value, envelope), float(y[s]), labels[k], float(member.angles_deg[weakest[k, s]]), modes[k, s],
                 (float(walls.x_m[k, j]), float(walls.z_m[k, j])))


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
    shear_flow = loads.torque * section.flow_per_torque  # the torque's flow round the box, along the walls' axis
    criterion, f12_star = envelope.criterion, envelope.f12_star

    # Skins and webs: at every point of each wall, the bending load there and the shear flow of the shear and the torque.
    skin, spar = section.skin, section.spar
    # A case whose loads repeat another's (the same corner at another altitude in equivalent airspeed) is checked once.
    _, first, again = np.unique(np.concatenate([loads.moment, loads.shear, loads.torque], axis=1), axis=0,
                                return_index=True, return_inverse=True)
    distinct = (loads.moment[first], loads.shear[first], shear_flow[first])
    skin_ratio, skin_weakest, skin_modes, skin_point = (a[:, again.reshape(-1)] for a in _wall_ratios(
        skin, section.skins, *distinct, criterion, f12_star))
    spar_ratio, spar_weakest, spar_modes, spar_point = (a[:, again.reshape(-1)] for a in _wall_ratios(
        spar, section.webs, *distinct, criterion, f12_star))

    # Skin buckling: each skin panel's buckling load over its mean compression across the chord.
    skin_load = section.skins.mean_load_per_moment[:, None, None] * loads.moment  # (2, cases, stations)
    with np.errstate(divide="ignore"):
        skin_buckling = np.where(skin_load < 0, np.array(section.skin_buckling_loads)[:, None, None] / -np.minimum(skin_load, 0), math.inf)
    buckling_ratio = skin_buckling.min(axis=0)

    # Webs in shear buckling: the bay's buckling shear flow over the size of the web's mean shear flow.
    web_flow = np.abs(section.webs.mean_flow_per_shear[:, None, None] * loads.shear + shear_flow)  # (2, cases, stations)
    with np.errstate(divide="ignore"):
        web_buckling_ratio = np.where(web_flow > 0, np.array(section.web_buckling_loads)[:, None, None] / web_flow, math.inf)

    deflection = cumulative_trapezoid(cumulative_trapezoid(curvature, y), y)
    twist = cumulative_trapezoid(loads.torque / section.GJ, y)

    results = []
    for c, case in enumerate(cases):
        buckling = float(buckling_ratio[c].min())
        if math.isfinite(buckling):
            s = int(np.argmin(buckling_ratio[c]))
            member = SKINS[int(np.argmin(skin_buckling[:, c, s]))]
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
            _ply_check("skin plies", SKINS, skin, section.skins, skin_ratio[:, c], skin_weakest[:, c], skin_modes[:, c], skin_point[:, c], y, envelope),
            _ply_check("spar plies", SPARS, spar, section.webs, spar_ratio[:, c], spar_weakest[:, c], spar_modes[:, c], spar_point[:, c], y, envelope),
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
