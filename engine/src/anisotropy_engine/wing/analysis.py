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
their signs. Every ply angle is checked at every point. A wing whose layups change along the span (ADR-0124) is worked stretch by
stretch, each with its own section: the bending and the twist integrate each stretch's stiffness, and the checks at a change are
made on both sides of it. Not modeled: shear lag, taper, sweep, ribs as load paths, the leading
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
from .description import FlightEnvelope, SpanSegment, Wing, span_segments
from .loads import CaseNotRun, LoadCase, flight_cases, span_loads
from .section import BoxSection, MemberLaminate, PointSet, box_section

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
    """One case along the span, at limit load, SI units; arrays of one value per station. Where a layup changes (ADR-0124) the
    station is listed twice, once with the section inboard of the change and once with the one outboard."""

    y: np.ndarray
    running_lift: np.ndarray
    shear: np.ndarray
    moment: np.ndarray
    torque: np.ndarray  # about each station's shear center
    deflection: np.ndarray  # m, up positive
    twist: np.ndarray  # rad, nose up positive
    skin_load: np.ndarray  # (2, stations): the mean Nx of the upper and lower skin's panel across the chord, N/m, tension positive
    shear_flow: np.ndarray  # the torque's shear flow round the box, N/m, along the walls' axis (section.WallPoints)
    web_shear_flow: np.ndarray  # (2, stations): the size of the front and rear web's mean shear flow, N/m
    skin_ratio: np.ndarray  # (2, stations): strength ratio of the upper and lower skin's plies, its caps' included
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
class Stretch:
    """A stretch of the span over which no layup changes (description.span_segments), with its section."""

    segment: SpanSegment
    section: BoxSection

    @property
    def length_m(self) -> float:
        return self.segment.end_m - self.segment.start_m


@dataclass(frozen=True)
class WingResult:
    wing: Wing
    envelope: FlightEnvelope
    section: BoxSection  # the root's
    cases: tuple[CaseResult, ...]
    not_run: tuple[CaseNotRun, ...]
    seconds: float  # time the calculation took
    aeroelastic: Aeroelastic | None = None  # divergence and aileron reversal
    stretches: tuple[Stretch, ...] = ()  # root to tip; one for a wing whose layups do not change along the span
    first_bending_frequency_Hz: float = math.nan  # of the wing as a cantilever, its stiffness and mass stretch by stretch

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

    def mass_kg(self, part: str | None = None) -> float:
        """One side's mass, kg: of the box's "skins" (between the caps), "caps", "spars" or "core", or all of it."""
        names = ("skins", "caps", "spars", "core") if part is None else (part,)
        return float(sum(getattr(s.section, f"mass_{name}_kg_m") * s.length_m for s in self.stretches for name in names))


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


@dataclass
class _Weakest:
    """The weakest ply of one wall at every case and station: arrays (cases, stations)."""

    ratio: np.ndarray
    label: np.ndarray  # object: the stretch of wall ("upper skin", "upper front spar cap")
    angle: np.ndarray
    mode: np.ndarray  # object
    x: np.ndarray
    z: np.ndarray


def _set_weakest(points: PointSet, moment: np.ndarray, shear: np.ndarray, torsion_flow: np.ndarray, criterion: str,
                 f12_star: float | None) -> _Weakest:
    """The weakest ply over every point of one stretch of wall, at every case and station (arrays (cases, stations)). Every
    state's ratio is found first and only the weakest named."""
    Nx = points.load_per_moment[:, None, None] * moment  # (points, cases, stations)
    Nxy = points.flow_per_shear[:, None, None] * shear + (torsion_flow if points.in_cell else 0.0)
    curvature = points.curvature_per_moment[:, None, None] * moment
    member = points.member
    stress = _ply_stress(member, Nx, Nxy, curvature)  # (points, cases, stations, 2 * angles, 3)
    lamina = member.layup.material.lamina
    ratios, _ = scaled_strength_ratios(criterion, lamina, stress.reshape(-1, 3), f12_star, with_modes=False)
    ratios = ratios.reshape(stress.shape[:-1])
    ply = np.argmin(ratios, axis=-1)
    ratio = np.take_along_axis(ratios, ply[..., None], axis=-1)[..., 0]  # (points, cases, stations)
    point = np.argmin(ratio, axis=0)  # (cases, stations)
    ply = np.take_along_axis(ply, point[None], axis=0)[0]
    cases, stations = np.indices(point.shape)
    weakest = stress[point, cases, stations, ply]
    chosen, modes = scaled_strength_ratios(criterion, lamina, weakest.reshape(-1, 3), f12_star)
    angles = np.array(member.angles_deg)[ply % len(member.angles_deg)]
    return _Weakest(chosen.reshape(point.shape), np.full(point.shape, points.label, dtype=object), angles,
                    np.array(modes, dtype=object).reshape(point.shape), points.x_m[point], points.z_m[point])


def _wall_weakest(section: BoxSection, wall: int, moment, shear, torsion_flow, criterion, f12_star) -> _Weakest:
    """The weakest ply over every stretch of one wall: its plain skin, its caps' halves inside and outside the box, or its web."""
    best = None
    for points in section.point_sets:
        if points.wall != wall:
            continue
        found = _set_weakest(points, moment, shear, torsion_flow, criterion, f12_star)
        if best is None:
            best = found
            continue
        better = found.ratio < best.ratio
        for name in ("ratio", "label", "angle", "mode", "x", "z"):
            getattr(best, name)[better] = getattr(found, name)[better]
    return best


def _ply_check(name: CheckName, walls: tuple[_Weakest, _Weakest], c: int, y, envelope) -> Check:
    """The governing entry of one case over two walls and every station."""
    ratio = np.array([walls[0].ratio[c], walls[1].ratio[c]])
    if not np.isfinite(ratio).any():
        return Check(name, math.inf, *_margins(math.inf, envelope), None, None, None, None)
    k, s = np.unravel_index(np.argmin(ratio), ratio.shape)
    w = walls[k]
    value = float(ratio[k, s])
    return Check(name, value, *_margins(value, envelope), float(y[s]), str(w.label[c, s]), float(w.angle[c, s]), w.mode[c, s],
                 (float(w.x[c, s]), float(w.z[c, s])))


def aeroelastic_checks(wing: Wing, envelope: FlightEnvelope, section: BoxSection) -> Aeroelastic:
    """Divergence and aileron reversal of the uniform wing of this section (aeroelastic.py), with the dive speed they are read against."""
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


def lowest_aeroelastic(wing: Wing, envelope: FlightEnvelope, sections: list[BoxSection]) -> Aeroelastic:
    """Divergence and reversal of a wing whose section changes along the span: each stretch's section is taken as the whole wing's,
    and the lowest dynamic pressure of each is kept (ADR-0124). A uniform wing has one section, and this is its own."""
    found = [aeroelastic_checks(wing, envelope, section) for section in sections]
    if len(found) == 1:
        return found[0]

    def lowest(name: str) -> float | None:
        values = [getattr(a, name) for a in found]
        return None if values[0] is None else min(values)

    q_divergence, q_reversal = lowest("divergence_dynamic_pressure_Pa"), lowest("reversal_dynamic_pressure_Pa")
    return Aeroelastic(
        divergence_dynamic_pressure_Pa=q_divergence,
        divergence_speed_m_s=None if q_divergence is None else equivalent_airspeed(q_divergence),
        reversal_dynamic_pressure_Pa=q_reversal,
        reversal_speed_m_s=None if q_reversal is None else equivalent_airspeed(q_reversal),
        dive_speed_m_s=found[0].dive_speed_m_s, needs=found[0].needs)


BEAM_ELEMENTS = 200  # cubic beam elements over the span for a wing whose stiffness changes along it: 1e-6 of the first frequency


def _beam_nodes(changes: list[float], half_span_m: float) -> np.ndarray:
    """BEAM_ELEMENTS equal elements with a node moved or added at each change, no element shorter than a quarter of the others: a
    sliver would spoil the stiffness matrix. A change within a quarter element of another is left inside an element, which takes
    the stiffness at its middle: a stretch that short hardly moves the frequency."""
    h = half_span_m / BEAM_ELEMENTS
    nodes, fixed = [0.0], [True]  # each kept node, and whether it is the root or a change, which stays
    for x, change in sorted([(x, False) for x in np.linspace(0.0, half_span_m, BEAM_ELEMENTS + 1)[1:-1]] + [(x, True) for x in changes]):
        if half_span_m - x < h / 4:
            continue
        if x - nodes[-1] >= h / 4:
            nodes.append(x)
            fixed.append(change)
        elif change and not fixed[-1]:
            nodes[-1], fixed[-1] = x, True
    return np.array([*nodes, half_span_m])


def bending_frequency(stretches: tuple[Stretch, ...], half_span_m: float) -> float:
    """The first bending frequency of the wing as a clamped-free beam, Hz. A uniform wing's is the closed form of its section; a wing
    whose section changes along the span is cut into about BEAM_ELEMENTS cubic (Hermite) elements with an edge at every change, each
    of its stretch's EI and mass per length, and solved as K v = w^2 M v (Przemieniecki, Theory of Matrix Structural Analysis, 1968,
    Sections 5.3 and 11.3, the consistent mass)."""
    if len(stretches) == 1:
        return stretches[0].section.first_bending_frequency_Hz
    nodes = _beam_nodes([s.segment.end_m for s in stretches[:-1]], half_span_m)
    n = nodes.size
    K = np.zeros((2 * n, 2 * n))
    M = np.zeros((2 * n, 2 * n))
    for e in range(n - 1):
        h = nodes[e + 1] - nodes[e]
        middle = (nodes[e] + nodes[e + 1]) / 2
        stretch = next(s for s in stretches if s.segment.start_m <= middle <= s.segment.end_m)
        EI, m = stretch.section.EI, stretch.section.mass_per_length_kg_m
        k = EI / h**3 * np.array([[12, 6 * h, -12, 6 * h], [6 * h, 4 * h**2, -6 * h, 2 * h**2], [-12, -6 * h, 12, -6 * h],
                                  [6 * h, 2 * h**2, -6 * h, 4 * h**2]])
        mass = m * h / 420 * np.array([[156, 22 * h, 54, -13 * h], [22 * h, 4 * h**2, 13 * h, -3 * h**2], [54, 13 * h, 156, -22 * h],
                                        [-13 * h, -3 * h**2, -22 * h, 4 * h**2]])
        dofs = np.arange(2 * e, 2 * e + 4)
        K[np.ix_(dofs, dofs)] += k
        M[np.ix_(dofs, dofs)] += mass
    free = slice(2, 2 * n)  # the root's deflection and slope are held
    L = np.linalg.cholesky(M[free, free])
    inverse = np.linalg.inv(L)
    lowest = float(np.linalg.eigvalsh(inverse @ K[free, free] @ inverse.T)[0])
    return math.sqrt(lowest) / (2 * math.pi)


def stations_of(stretches: tuple[Stretch, ...], half_span_m: float, stations: int) -> tuple[np.ndarray, np.ndarray]:
    """The stations, `stations` of them equally spaced from root to tip, and every change of layup twice: the y of each and the
    stretch it is worked with, inboard of a change first. A wing without changes has exactly the equally spaced ones."""
    even = np.linspace(0.0, half_span_m, stations)
    tolerance = 1e-9 * half_span_m
    y, which = [], []
    for k, stretch in enumerate(stretches):
        start, end = stretch.segment.start_m, stretch.segment.end_m
        inside = even[(even > start + tolerance) & (even < end - tolerance)]
        ys = np.concatenate([[start], inside, [end]])
        y.append(ys)
        which.append(np.full(ys.size, k))
    return np.concatenate(y), np.concatenate(which)


def analyze_wing(wing: Wing, envelope: FlightEnvelope, stations: int = 51) -> WingResult:
    """Run every load case the envelope states on the wing, at `stations` equally spaced stations from root to tip and at every
    change of layup along the span, on each side of it."""
    started = time.perf_counter()
    if stations < 3:
        raise ValueError("The calculation needs at least three stations")
    g = wing.geometry
    stretches = tuple(Stretch(segment, box_section(wing, segment)) for segment in span_segments(wing))
    for stretch in stretches:
        for layup in (stretch.segment.skin, stretch.segment.spar, stretch.segment.cap):
            if layup is not None:
                check_criterion(layup.plies(), envelope.criterion, envelope.f12_star)
    section = stretches[0].section
    sections = [s.section for s in stretches]
    frequency = bending_frequency(stretches, g.half_span_m)
    cases, not_run = flight_cases(envelope, g.chord_m)
    y, which = stations_of(stretches, g.half_span_m, stations)
    aeroelastic = lowest_aeroelastic(wing, envelope, sections)
    if not cases:
        return WingResult(wing, envelope, section, (), tuple(not_run), time.perf_counter() - started, aeroelastic, stretches, frequency)

    def per_station(name: str) -> np.ndarray:
        return np.array([getattr(sections[k], name) for k in which])

    torque_arm = per_station("shear_center_m") - wing.aerodynamics.aerodynamic_center * g.chord_m
    loads = span_loads(y, g.half_span_m, g.chord_m, cases, envelope, torque_arm, wing.aerodynamics.pitching_moment_coefficient)
    curvature = loads.moment / per_station("EI")  # (cases, stations)
    shear_flow = loads.torque * per_station("flow_per_torque")  # the torque's flow round the box, along the walls' axis
    criterion, f12_star = envelope.criterion, envelope.f12_star

    # A case whose loads repeat another's (the same corner at another altitude in equivalent airspeed) is checked once.
    _, first, again = np.unique(np.concatenate([loads.moment, loads.shear, loads.torque], axis=1), axis=0,
                                return_index=True, return_inverse=True)
    again = again.reshape(-1)
    n_cases, n_stations = loads.moment.shape
    walls = [_Weakest(np.empty((n_cases, n_stations)), np.empty((n_cases, n_stations), dtype=object), np.empty((n_cases, n_stations)),
                      np.empty((n_cases, n_stations), dtype=object), np.empty((n_cases, n_stations)), np.empty((n_cases, n_stations)))
             for _ in range(4)]
    skin_load = np.empty((2, n_cases, n_stations))
    web_flow = np.empty((2, n_cases, n_stations))
    skin_buckling = np.empty((2, n_cases, n_stations))
    web_buckling_ratio = np.empty((2, n_cases, n_stations))
    for k, stretch in enumerate(stretches):
        cols = which == k
        s = stretch.section
        distinct = (loads.moment[first][:, cols], loads.shear[first][:, cols], shear_flow[first][:, cols])
        # Skins and webs: at every point of each stretch of wall, the bending load there and the shear flow of the shear and the torque.
        for wall in range(4):
            found = _wall_weakest(s, wall, *distinct, criterion, f12_star)
            for name in ("ratio", "label", "angle", "mode", "x", "z"):
                getattr(walls[wall], name)[:, cols] = getattr(found, name)[again]
        # Skin buckling: each skin panel's buckling load over its mean compression across the panel.
        load = s.skins.mean_load_per_moment[:, None, None] * loads.moment[:, cols]
        skin_load[:, :, cols] = load
        with np.errstate(divide="ignore"):
            skin_buckling[:, :, cols] = np.where(load < 0, np.array(s.skin_buckling_loads)[:, None, None] / -np.minimum(load, 0), math.inf)
        # Webs in shear buckling: the bay's buckling shear flow over the size of the web's mean shear flow.
        flow = np.abs(s.webs.mean_flow_per_shear[:, None, None] * loads.shear[:, cols] + shear_flow[:, cols])
        web_flow[:, :, cols] = flow
        with np.errstate(divide="ignore"):
            web_buckling_ratio[:, :, cols] = np.where(flow > 0, np.array(s.web_buckling_loads)[:, None, None] / flow, math.inf)
    skin_ratio = np.array([walls[0].ratio, walls[1].ratio])
    spar_ratio = np.array([walls[2].ratio, walls[3].ratio])
    buckling_ratio = skin_buckling.min(axis=0)

    deflection = cumulative_trapezoid(cumulative_trapezoid(curvature, y), y)
    twist = cumulative_trapezoid(loads.torque / per_station("GJ"), y)

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
            _ply_check("skin plies", (walls[0], walls[1]), c, y, envelope),
            _ply_check("spar plies", (walls[2], walls[3]), c, y, envelope),
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
    return WingResult(wing, envelope, section, tuple(results), tuple(not_run), time.perf_counter() - started, aeroelastic, stretches, frequency)
