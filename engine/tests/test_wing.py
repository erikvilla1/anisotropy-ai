"""The wing calculation (ADR-0115): airfoil, atmosphere, load cases, span loads, section and the checks, against closed
forms, the engine's own laminate functions and each other. The constructed wing worked by hand is test_wing_validation.py."""

import math
import tomllib
from pathlib import Path

import numpy as np
import pytest

from anisotropy_engine.failure import first_ply_failure
from anisotropy_engine.response import Loads
from anisotropy_engine.units import FOOT, LBF
from anisotropy_engine.wing import (
    Airfoil, analyze_wing, box_section, flight_cases, load_wing, naca4, span_loads, wing_from_dict, wing_report, wing_views,
)
from anisotropy_engine.wing.atmosphere import SEA_LEVEL_DENSITY, air_density, density_ratio
from anisotropy_engine.wing.loads import CASE_TABLE, gust_load_factor_increment
from anisotropy_engine.wing.section import long_plate_buckling_load
from anisotropy_engine.wing.wing_file import KNOT

EXAMPLE = Path(__file__).parents[1] / "examples" / "example-wing.toml"


def example(**changes) -> dict:
    """The example wing file's contents, with `section.key = value` changes ("envelope.speeds.dive": None removes a key)."""
    data = tomllib.loads(EXAMPLE.read_text(encoding="utf-8"))
    for path, value in changes.items():
        *tables, key = path.split(".")
        table = data
        for name in tables:
            table = table[name]
        if value is None:
            table.pop(key)
        else:
            table[key] = value
    return data


def run(stations=51, **changes):
    wing, envelope = wing_from_dict(example(**changes))
    return analyze_wing(wing, envelope, stations=stations)


# ------------------------------------------------------------------------------------------------- airfoil

def test_naca_symmetric_thickness_follows_the_formula():
    upper, lower = naca4("0012").surface_heights(0.3)
    assert upper == pytest.approx(0.0600172, abs=1e-7)  # 5 t (0.2969 sqrt(x) - 0.126 x - 0.3516 x^2 + 0.2843 x^3 - 0.1015 x^4)
    assert lower == -upper


def test_naca_camber_peaks_where_its_second_digit_says():
    upper, lower = naca4("2412").surface_heights(0.4)  # the camber line is level there, so the thickness is laid off straight up
    assert (upper + lower) / 2 == pytest.approx(0.02, abs=1e-12)
    assert upper - lower == pytest.approx(2 * naca4("0012").surface_heights(0.4)[0], abs=1e-12)


def test_naca_cambered_surface_points_lie_on_the_normals_of_the_camber_line():
    # A point of the upper surface built the textbook way, x_u = x - y_t sin(theta), y_u = y_c + y_t cos(theta), is found again.
    x, m, p, t = 0.2, 0.04, 0.4, 0.15
    yt = 5 * t * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1015 * x**4)
    yc, slope = m / p**2 * (2 * p * x - x**2), 2 * m / p**2 * (p - x)
    theta = math.atan(slope)
    upper, _ = naca4("4415").surface_heights(x - yt * math.sin(theta))
    assert upper == pytest.approx(yc + yt * math.cos(theta), abs=1e-12)


def test_an_airfoil_from_points_is_read_between_them():
    airfoil = Airfoil(name="wedge", upper=((0, 0), (0.5, 0.06), (1, 0)), lower=((0, 0), (1, -0.02)))
    assert airfoil.surface_heights(0.25) == pytest.approx((0.03, -0.005))
    with pytest.raises(ValueError, match="x must increase"):
        Airfoil(name="bad", upper=((0, 0), (0.5, 0.06), (0.5, 0.05)), lower=((0, 0), (1, 0)))
    with pytest.raises(ValueError, match="four digits"):
        naca4("24")
    with pytest.raises(ValueError, match="not both"):
        Airfoil(name="two", naca="0012", upper=((0, 0), (1, 0)), lower=((0, 0), (1, 0)))


# ---------------------------------------------------------------------------------------------- atmosphere

def test_standard_atmosphere_density():
    assert SEA_LEVEL_DENSITY == pytest.approx(1.2250, abs=5e-5)
    assert density_ratio(0) == 1
    assert density_ratio(10000 * FOOT) == pytest.approx(0.7385, abs=5e-5)  # U.S. Standard Atmosphere 1976, 10 000 ft
    assert air_density(11000) == pytest.approx(0.3639, abs=5e-5)  # the tropopause
    with pytest.raises(ValueError, match="between 0 and 11000"):
        density_ratio(12000)


# ---------------------------------------------------------------------------------------------- load cases

def test_seventeen_cases_at_each_altitude():
    result = run()
    assert [case.case.number for case in result.cases] == list(range(1, 18)) * 2
    assert [case.case.altitude_m for case in result.cases] == [0.0] * 17 + [3000.0] * 17
    assert not result.not_run
    by_number = {r.case.number: r.case for r in result.cases[:17]}
    assert by_number[6].load_factor == 3.8 and by_number[9].load_factor == -1.52
    assert by_number[16].load_factor == pytest.approx(0.6667 * 3.8)
    assert [by_number[n].aileron for n in (14, 15, 16, 17)] == ["down", "up", "down", "up"]
    assert all(case.load_factor == 1 for n, case in by_number.items() if n <= 5 or n in (14, 15))


def test_a_missing_entry_leaves_its_cases_out_and_says_what_each_needs():
    result = run(**{"envelope.speeds.dive": None, "envelope.gust": None, "envelope.aileron": None})
    needs = {(n.number, n.altitude_m): n.needs for n in result.not_run}
    assert needs[(4, 0.0)] == "the dive speed"
    assert needs[(10, 0.0)] == "the gust load factors or the gust speeds"
    assert needs[(12, 3000.0)] == "the dive speed and the gust load factors or the gust speeds"
    assert needs[(14, 0.0)] == "the aileron"
    assert sorted({r.case.number for r in result.cases}) == [1, 2, 3, 5, 6, 8]
    assert len(result.cases) + len(result.not_run) == 2 * len(CASE_TABLE)


def test_no_case_at_all_is_a_result_that_judges_nothing():
    result = run(**{"envelope.speeds": {}, "envelope.gust": None, "envelope.aileron": None})
    assert result.cases == () and len(result.not_run) == 34
    assert result.passes is None and result.governing is None
    assert result.section.EI > 0  # the design summary needs no load case


def test_equivalent_airspeeds_load_the_wing_alike_at_every_altitude_and_true_airspeeds_do_not():
    equivalent = run()
    assert equivalent.cases[5].case.dynamic_pressure_Pa == equivalent.cases[22].case.dynamic_pressure_Pa == pytest.approx(0.5 * SEA_LEVEL_DENSITY * 44.8**2)
    true = run(**{"envelope.airspeed": "true"})
    assert true.cases[22].case.dynamic_pressure_Pa / true.cases[5].case.dynamic_pressure_Pa == pytest.approx(density_ratio(3000.0))


def test_gust_load_factor_agrees_with_the_regulations_printed_form():
    # 14 CFR 23.341(c) prints n = 1 + K_g U_de V a / (498 W/S) with V in knots, U_de in ft/s and W/S in lb/ft^2;
    # 498 is 2 / (rho_0 * 1.6878 ft/s per knot) rounded, so the two agree to the rounding.
    wing, envelope = wing_from_dict(example())
    gust, weight, chord, altitude = envelope.gust, envelope.gross_weight_N, wing.geometry.chord_m, 3000.0
    increment = gust_load_factor_increment(gust, gust.cruise_gust_speed_m_s, envelope.speeds.cruise, altitude, "equivalent", weight, chord)
    slug_per_ft3 = air_density(altitude) / (LBF / FOOT**4)  # 1 slug/ft^3 = 1 lbf s^2/ft^4
    loading_psf = weight / gust.wing_area_m2 / (LBF / FOOT**2)
    mu = 2 * loading_psf / (slug_per_ft3 * chord / FOOT * gust.lift_curve_slope_per_rad * 32.174)
    printed = 0.88 * mu / (5.3 + mu) * (gust.cruise_gust_speed_m_s / FOOT) * (envelope.speeds.cruise / KNOT) * gust.lift_curve_slope_per_rad / (498 * loading_psf)
    assert increment == pytest.approx(printed, rel=2e-3)
    cases, _ = flight_cases(envelope, chord)
    up, down = (next(c for c in cases if c.number == n and c.altitude_m == altitude) for n in (10, 11))
    assert up.load_factor == pytest.approx(1 + increment) and down.load_factor == pytest.approx(1 - increment)


def test_stated_gust_load_factors_are_used_as_given():
    result = run(**{"envelope.gust": {"cruise_positive": 3.1, "cruise_negative": -1.1, "dive_positive": 2.2, "dive_negative": -0.2}})
    assert [r.case.load_factor for r in result.cases[9:13]] == [3.1, -1.1, 2.2, -0.2]


# ---------------------------------------------------------------------------------------------- span loads

def loads_of(numbers=(6, 14, 15), stations=2001):
    wing, envelope = wing_from_dict(example())
    cases = [c for c in flight_cases(envelope, wing.geometry.chord_m)[0] if c.altitude_m == 0 and c.number in numbers]
    y = np.linspace(0, wing.geometry.half_span_m, stations)
    return wing, envelope, cases, span_loads(y, wing.geometry.half_span_m, wing.geometry.chord_m, cases, envelope, 0.05, -0.05)


def test_the_lift_of_one_side_is_half_the_weight_times_the_load_factor():
    _, envelope, cases, loads = loads_of()
    assert loads.shear[0, 0] == pytest.approx(3.8 * envelope.gross_weight_N / 2)
    np.testing.assert_allclose(loads.shear[:, -1], 0, atol=1e-9)
    np.testing.assert_allclose(loads.moment[:, -1], 0, atol=1e-9)
    L = 2.0
    assert loads.moment[0, 0] == pytest.approx(loads.shear[0, 0] * L * (1 / 4 + 2 / (3 * math.pi)))  # mean of L/2 and 4L/(3 pi)
    assert loads.running_lift[0, 0] == pytest.approx(0.5 * (4 / math.pi + 1) * loads.shear[0, 0] / L)  # Schrenk at the root
    assert loads.running_lift[0, -1] == pytest.approx(0.5 * loads.shear[0, 0] / L)  # and at the tip, half the uniform load


def test_shear_and_moment_are_the_integrals_of_the_running_lift():
    _, _, _, loads = loads_of()
    y = loads.y
    for c in range(3):
        outboard = np.trapezoid(loads.running_lift[c], y) - np.concatenate([[0], np.cumsum((loads.running_lift[c, 1:] + loads.running_lift[c, :-1]) / 2 * np.diff(y))])
        np.testing.assert_allclose(loads.shear[c], outboard, atol=2e-4 * abs(loads.shear[c, 0]))  # the trapezoid rule's error at the tip's square root and the aileron's steps
        np.testing.assert_allclose(np.gradient(loads.moment[c], y)[5:-5], -loads.shear[c][5:-5], atol=2e-3 * abs(loads.shear[c, 0]))


def test_an_aileron_adds_its_lift_over_its_span_only():
    wing, envelope, cases, loads = loads_of()
    aileron, q, c = envelope.aileron, cases[1].dynamic_pressure_Pa, wing.geometry.chord_m
    level = envelope.gross_weight_N / 2
    extra = q * c * aileron.down_delta_cl
    assert loads.shear[1, 0] == pytest.approx(level + extra * 0.7) and loads.shear[2, 0] == pytest.approx(level - extra * 0.7)
    assert loads.moment[1, 0] - loads.moment[2, 0] == pytest.approx(2 * extra * (1.9**2 - 1.2**2) / 2)
    inboard, on, outboard = (int(np.argmin(np.abs(loads.y - y))) for y in (0.6, 1.5, 1.95))
    assert loads.running_lift[1, on] - loads.running_lift[2, on] == pytest.approx(2 * extra)
    assert loads.running_lift[1, inboard] == loads.running_lift[2, inboard] and loads.running_lift[1, outboard] == loads.running_lift[2, outboard]
    # torque at the root: arm * shear + q c^2 (cm L + delta_cm * aileron span)
    assert loads.torque[1, 0] == pytest.approx(0.05 * loads.shear[1, 0] + q * c**2 * (-0.05 * 2.0 + aileron.down_delta_cm * 0.7))


def test_an_aileron_past_the_tip_is_refused():
    with pytest.raises(ValueError, match="outboard of the wing tip"):
        run(**{"envelope.aileron.span_end": 2.2})


# ------------------------------------------------------------------------------------------------- section

def flat_sided(upper_front=0.06, upper_rear=0.06) -> dict:
    """An airfoil of straight lines (fractions of the chord), symmetric about the chord line, straight from 15 % to 75 % of the
    chord, so the box between the spars at 25 % and 65 % has flat skins and its section can be worked by hand."""
    slope = (upper_rear - upper_front) / 0.4
    upper = [[0.0, 0.0], [0.15, upper_front - 0.1 * slope], [0.75, upper_rear + 0.1 * slope], [1.0, 0.0]]
    return {"name": "flat sided", "upper": upper, "lower": [[x, -z] for x, z in upper]}


def along_walls(walls, f, g):
    """The integral along each of two walls of f times g, both given at its points and linear along each straight piece
    between them, so the rule is exact."""
    length = np.hypot(np.diff(walls.x_m), np.diff(walls.z_m))
    a0, a1, b0, b1 = f[:, :-1], f[:, 1:], g[:, :-1], g[:, 1:]
    return (length * (2 * a0 * b0 + a0 * b1 + a1 * b0 + 2 * a1 * b1) / 6).sum(axis=1)


def flow_resultant(walls, flow):
    """The force (x, z) of a shear flow on each of two walls, and its moment about the leading edge's chord point, by the
    trapezoid rule on each piece (the flow is quadratic along a piece, so this is close, not exact)."""
    dx, dz = np.diff(walls.x_m), np.diff(walls.z_m)
    mean = (flow[:, 1:] + flow[:, :-1]) / 2
    return (mean * dx).sum(axis=1), (mean * dz).sum(axis=1), float((mean * (walls.z_m[:, :-1] * dx - walls.x_m[:, :-1] * dz)).sum())


def test_a_symmetric_airfoil_puts_the_centroid_on_the_chord_line():
    wing, _ = wing_from_dict(example(**{"geometry.airfoil": "naca-0012"}))
    section = box_section(wing)
    assert section.centroid_m == pytest.approx(0, abs=1e-12) and section.EI_product == pytest.approx(0, abs=1e-12 * section.EI)
    assert section.skins.z_m[0][::-1] == pytest.approx(-section.skins.z_m[1])  # the upper skin's points run aft to fore
    assert section.shear_shares[0] > section.shear_shares[1]  # the front web is the taller one
    assert 0.8 < sum(section.shear_shares) < 1  # the curved skins carry the rest of the shear
    assert section.spar_x_m[0] < section.shear_center_m < section.spar_x_m[1]


def test_the_skins_sit_at_their_mid_thickness_inside_the_airfoil():
    wing, _ = wing_from_dict(example(**{"geometry.airfoil": flat_sided()}))
    section = box_section(wing)
    half = (wing.skin.fiber_thickness_m + wing.skin.core_thickness_m) / 2
    assert section.skins.z_m == pytest.approx(np.array([[0.06 * 0.45 - half] * 33, [-0.06 * 0.45 + half] * 33]), rel=1e-12)
    assert section.spar_heights_m == pytest.approx((0.12 * 0.45 - 2 * half,) * 2, rel=1e-12)
    curved_wing, _ = wing_from_dict(example())
    curved = box_section(curved_wing)
    top = np.array([0.45 * curved_wing.geometry.airfoil.surface_heights(x / 0.45)[0] for x in curved.skins.x_m[0]])
    # Moved half the thickness along the normal: a little more than half straight down where the surface slopes.
    assert np.all(top - curved.skins.z_m[0] > half * 0.9999) and np.all(top - curved.skins.z_m[0] < half * 1.05)


def test_a_rectangular_box_shares_the_shear_between_its_webs_and_twists_by_bredt():
    wing, _ = wing_from_dict(example(**{"geometry.airfoil": flat_sided()}))
    section = box_section(wing)
    assert section.shear_shares == pytest.approx((0.5, 0.5), rel=1e-12)  # flat skins carry no vertical shear
    assert section.shear_center_m == pytest.approx(0.45 * 0.45, rel=1e-12)  # midway between the spars
    b, h = 0.4 * 0.45, section.spar_heights_m[0]
    skin_gt, web_gt = section.skin.Gxy * section.skin.thickness_m, section.spar.Gxy * section.spar.thickness_m
    assert section.enclosed_area_m2 == pytest.approx(b * h, rel=1e-12)
    assert section.GJ == pytest.approx(4 * (b * h) ** 2 / (2 * b / skin_gt + 2 * h / web_gt), rel=1e-12)
    skin_et, web_et = section.skin.Ex * section.skin.thickness_m, section.spar.Ex * section.spar.thickness_m
    assert section.EI == pytest.approx(2 * skin_et * b * (h / 2) ** 2 + 2 * web_et * h**3 / 12, rel=1e-12)
    # Bending strains the skin's outer face more than its mid-surface: the upper skin's outward normal points up.
    assert section.skins.curvature_per_moment == pytest.approx(np.array([[-1.0], [1.0]]) / section.EI * np.ones((2, 33)), rel=1e-12)
    assert section.webs.curvature_per_moment == pytest.approx(np.zeros((2, 9)), abs=1e-12 / section.EI)


def test_a_tapered_box_puts_the_shear_center_toward_the_taller_web():
    section = box_section(wing_from_dict(example(**{"geometry.airfoil": flat_sided(0.07, 0.05)}))[0])
    assert section.shear_shares[0] > section.shear_shares[1]
    assert 0.25 * 0.45 < section.shear_center_m < 0.45 * 0.45


@pytest.mark.parametrize("airfoil", ["naca-2412", "naca-0012"])
def test_the_shear_flow_carries_the_shear_at_the_shear_center_and_the_torque_round_the_box(airfoil):
    section = box_section(wing_from_dict(example(**{"geometry.airfoil": airfoil}))[0])
    skins, webs = (flow_resultant(walls, walls.flow_per_shear) for walls in (section.skins, section.webs))
    # The trapezoid rule on a flow that is quadratic along each piece: about 0.1 % here.
    assert skins[0].sum() + webs[0].sum() == pytest.approx(0.0, abs=2e-3)
    assert skins[1].sum() + webs[1].sum() == pytest.approx(1.0, abs=2e-3)
    assert -(skins[2] + webs[2]) == pytest.approx(section.shear_center_m, rel=2e-3)  # a unit upward force there
    assert tuple(webs[1]) == pytest.approx(section.shear_shares, rel=2e-3)
    assert section.flow_per_torque * -2 * section.enclosed_area_m2 == pytest.approx(1.0)


@pytest.mark.parametrize("airfoil", ["naca-2412", "naca-0012"])
def test_the_bending_load_sums_to_the_moment_and_to_no_force(airfoil):
    section = box_section(wing_from_dict(example(**{"geometry.airfoil": airfoil}))[0])
    force = moment_z = moment_x = 0.0
    for walls in (section.skins, section.webs):
        load, one = walls.load_per_moment, np.ones_like(walls.x_m)
        force += along_walls(walls, load, one).sum()
        moment_z += along_walls(walls, load, walls.z_m - section.centroid_m).sum()
        moment_x += along_walls(walls, load, walls.x_m - section.centroid_x_m).sum()
    assert force == pytest.approx(0, abs=1e-9)
    assert moment_z == pytest.approx(-1, rel=1e-12)  # the upper skin in compression under a positive moment
    assert moment_x == pytest.approx(0, abs=1e-12)  # no chordwise moment: the neutral axis tilts instead


def test_ribs_raise_the_skins_buckling_load_and_far_apart_they_leave_the_long_panel():
    long_panel = box_section(wing_from_dict(example(**{"geometry.rib_spacing": None, "rib": None}))[0])
    for load, width in zip(long_panel.skin_buckling_loads, long_panel.skin_widths_m):
        assert load == pytest.approx(long_plate_buckling_load(long_panel.skin.D, width))
    assert 0.4 * 0.45 < min(long_panel.skin_widths_m)  # each skin's width is its length round the curve
    close = box_section(wing_from_dict(example(**{"geometry.rib_spacing": 0.1}))[0])
    far = box_section(wing_from_dict(example(**{"geometry.rib_spacing": 2.0}))[0])
    assert close.skin_buckling_load > 1.2 * long_panel.skin_buckling_load
    assert long_panel.skin_buckling_load <= far.skin_buckling_load < 1.02 * long_panel.skin_buckling_load


def test_a_core_adds_buckling_load_and_core_mass_and_moves_the_skins_inward():
    solid = box_section(wing_from_dict(example(**{"skin.core_thickness": None, "skin.core": None}))[0])
    cored = box_section(wing_from_dict(example())[0])
    assert 0.7 * solid.EI < cored.EI < solid.EI and 0.7 * solid.GJ < cored.GJ < solid.GJ  # the skins' mid-surface is 3 mm further in
    assert solid.mass_core_kg_m == 0 and cored.mass_core_kg_m == pytest.approx(sum(cored.skin_widths_m) * 0.006 * 48.0)  # per metre
    assert cored.skin_buckling_load > 50 * solid.skin_buckling_load


# ------------------------------------------------------------------------------------------------ analysis

@pytest.mark.parametrize("cored", [False, True])
def test_the_ply_check_is_the_engines_first_ply_failure_of_the_whole_laminate(cored):
    # The calculation checks one stress state per ply angle on each side at each point; the engine's laminate functions check
    # every face of every ply under the wall's in-plane loads and its own spanwise moment. At the root of the pull-up case, every
    # point of every wall.
    from anisotropy_engine.laminate import abd_matrices
    from anisotropy_engine.sandwich import sandwich_abd
    result = run() if cored else run(**{"skin.core_thickness": None, "skin.core": None})
    case, section = result.cases[5], result.section
    st = case.stations
    for layup, walls, ratios in ((result.wing.skin, section.skins, st.skin_ratio), (result.wing.spar, section.webs, st.spar_ratio)):
        D = sandwich_abd(layup.face(), layup.core_thickness_m, layup.face()[::-1])[2] if layup.core_thickness_m else abd_matrices(layup.plies())[2]
        stiffness = 1 / np.linalg.inv(D)[0, 0]  # moment per unit spanwise curvature, the other moments free
        for k in range(2):
            loads = [Loads(Nx=float(walls.load_per_moment[k, j] * st.moment[0]),
                           Nxy=float(walls.flow_per_shear[k, j] * st.shear[0] + st.shear_flow[0]),
                           Mx=float(walls.curvature_per_moment[k, j] * st.moment[0] * stiffness)) for j in range(walls.x_m.shape[1])]
            if layup.core_thickness_m:  # the faces with the core between them: a sandwich's plies, by their own z
                whole = [sandwich_ratio(layup, load) for load in loads]
            else:
                whole = [first_ply_failure(layup.plies(), load, "max_stress").strength_ratio for load in loads]
            assert ratios[k, 0] == pytest.approx(min(whole), rel=1e-12)
    check = case.checks[0]
    assert check.strength_ratio == pytest.approx(st.skin_ratio.min())
    assert check.station_m == 0.0 and check.member in ("upper skin", "lower skin")
    k = ("upper skin", "lower skin").index(check.member)
    assert check.point_m in list(zip(section.skins.x_m[k], section.skins.z_m[k]))


def sandwich_ratio(layup, loads: Loads) -> float:
    """Maximum stress ratio of the weakest face of any ply of a sandwich under in-plane loads and moments, worked ply by ply."""
    from anisotropy_engine.failure import max_stress_ratio
    from anisotropy_engine.rotation import stress_transformation, transformed_reduced_stiffness
    from anisotropy_engine.sandwich import sandwich_abd, sandwich_interfaces
    face = layup.face()
    lower, upper = face[::-1], face
    A, _, D = sandwich_abd(lower, layup.core_thickness_m, upper)
    strain = np.linalg.solve(A, [loads.Nx, loads.Ny, loads.Nxy])
    curvature = np.linalg.solve(D, [loads.Mx, loads.My, loads.Mxy])
    z_lower, z_upper = sandwich_interfaces(lower, layup.core_thickness_m, upper)
    ratios = []
    for plies, z in ((lower, z_lower), (upper, z_upper)):
        for i, ply in enumerate(plies):
            for zeta in (z[i], z[i + 1]):
                stress = stress_transformation(ply.angle_deg) @ transformed_reduced_stiffness(ply.material, ply.angle_deg) @ (strain + zeta * curvature)
                ratios.append(max_stress_ratio(stress, ply.material.strengths)[0])
    return min(ratios)


def test_the_skin_buckling_check_divides_each_skins_load_by_its_mean_compression():
    result = run()
    section = result.section
    case = result.cases[5]
    mean = section.skins.mean_load_per_moment[:, None] * case.stations.moment
    assert case.stations.skin_load == pytest.approx(mean)
    assert case.stations.buckling_ratio[0] == pytest.approx(section.skin_buckling_loads[0] / -mean[0, 0])
    assert mean[0, 0] < 0 < mean[1, 0]  # pull-up: the upper skin in compression, the lower in tension


def test_margins_follow_the_strength_ratio_and_the_two_factors():
    for case in run().cases:
        for check in case.checks:
            assert check.margin_ultimate == pytest.approx(check.strength_ratio / 1.5 - 1)
            assert check.margin_proof == pytest.approx(check.strength_ratio / 1.25 - 1)
    assert all(check.margin_proof is None for case in run(**{"envelope.proof_factor": None}).cases for check in case.checks)


def test_the_calculation_is_linear_in_the_weight_for_the_maneuver_cases():
    light, heavy = run(), run(**{"envelope.gross_weight": 5400.0})  # twice the example's 2700 N
    a, b = light.cases[7], heavy.cases[7]  # the negative maneuver corner: no gust, no aileron
    assert b.root_moment == pytest.approx(2 * a.root_moment)
    assert b.tip_deflection == pytest.approx(2 * a.tip_deflection)
    assert b.checks[2].strength_ratio == pytest.approx(a.checks[2].strength_ratio / 2)


def test_positive_bending_compresses_the_upper_skin_and_negative_the_lower():
    result = run()
    assert result.cases[5].checks[2].member == "upper skin" and result.cases[5].tip_deflection > 0
    assert result.cases[7].checks[2].member == "lower skin" and result.cases[7].tip_deflection < 0


def test_the_tip_deflection_converges_and_the_loads_do_not_depend_on_the_stations():
    coarse, fine = run(stations=21), run(stations=401)
    assert coarse.cases[5].root_moment == fine.cases[5].root_moment
    assert coarse.cases[5].tip_deflection == pytest.approx(fine.cases[5].tip_deflection, rel=2e-3)
    with pytest.raises(ValueError, match="three stations"):
        run(stations=2)


@pytest.mark.parametrize("changes", [
    {"envelope.criterion": "tsai_hill"},
    {"envelope.criterion": "tsai_wu", "envelope.f12_star": -0.5},
    {"envelope.criterion": "max_strain", "envelope.strain_limits": "from-strengths"},
])
def test_every_criterion_of_the_engine_can_judge_the_plies(changes):
    result, reference = run(**changes), run()
    ratio, by_max_stress = result.cases[5].checks[0].strength_ratio, reference.cases[5].checks[0].strength_ratio
    assert 0.5 * by_max_stress < ratio < 1.5 * by_max_stress
    assert result.cases[5].checks[2].strength_ratio == reference.cases[5].checks[2].strength_ratio  # buckling does not use it


def test_a_criterion_the_inputs_cannot_support_is_refused():
    with pytest.raises(ValueError, match="f12_star"):
        run(**{"envelope.criterion": "tsai_wu"})
    with pytest.raises(ValueError, match="strain limits"):
        run(**{"envelope.criterion": "max_strain"})


def test_thirty_four_cases_take_a_fraction_of_a_second():
    result = run()
    assert len(result.cases) == 34
    assert result.seconds < 0.25  # about 0.015 s on a laptop; the page reruns it on every change


# ----------------------------------------------------------------------------------------------- wing file

def test_the_example_wing_passes_and_reports_in_its_own_units():
    data, wing, envelope = load_wing(EXAMPLE)
    result = analyze_wing(wing, envelope)
    assert result.passes is True
    report = wing_report(result, "SI", "m/s")
    assert report["units"]["moment"] == "N*m" and report["units"]["deflection"] == "mm"
    assert report["cases"][5]["speed"] == pytest.approx(44.8) and report["cases"][5]["root_shear"] == pytest.approx(5130.0)  # 3.8 x 2700 N / 2
    assert report["governing"]["case"] == 6 and report["governing"]["margin_ultimate"] > 0
    us = wing_report(result, "US", "mph")
    assert us["design"]["mass"] == pytest.approx(report["design"]["mass"] / 0.45359237)
    assert us["cases"][5]["root_moment"] == pytest.approx(report["cases"][5]["root_moment"] / (LBF * 0.0254))
    assert us["cases"][5]["tip_deflection"] == pytest.approx(report["cases"][5]["tip_deflection"] / 25.4)


def test_the_page_draws_the_engines_section_ribs_and_margins_rounded_only_for_drawing():
    result = run()
    views = wing_views(result, "SI")
    section, case = result.section, result.cases[5]
    assert views["ribs"] == pytest.approx([0.0, 0.5, 1.0, 1.5, 2.0]) and views["shear_center"] == section.shear_center_m
    assert views["walls"][0]["x"] == pytest.approx(section.skins.x_m[0], rel=1e-3)
    assert views["walls"][3]["z"] == pytest.approx(section.webs.z_m[1], rel=1e-3)
    upper, lower = result.wing.geometry.airfoil.surface_heights(0.3)
    x = np.array(views["airfoil"]["x"])
    assert np.interp(0.3 * 0.45, x, views["airfoil"]["upper"]) == pytest.approx(upper * 0.45, rel=2e-3)
    assert np.interp(0.3 * 0.45, x, views["airfoil"]["lower"]) == pytest.approx(lower * 0.45, rel=2e-3)
    drawn = views["cases"][5]
    assert drawn["number"] == case.case.number
    lowest = min(min(v for v in values if v is not None) for values in drawn["margins"].values())
    assert lowest == pytest.approx(case.governing.margin_ultimate, rel=1e-3), "the margins along the span hold the case's governing one"
    assert drawn["deflection"][-1] == pytest.approx(case.tip_deflection * 1e3, rel=1e-3)
    moment, shear = case.stations.moment[0], case.stations.shear[0]
    flow = section.skins.flow_per_shear[1] * shear + case.stations.shear_flow[0]
    assert drawn["root"][1]["shear_flow"] == pytest.approx(flow, rel=1e-3)
    assert drawn["root"][0]["load"] == pytest.approx(section.skins.load_per_moment[0] * moment, rel=1e-3)
    us = wing_views(result, "US")
    assert us["half_span"] == pytest.approx(2.0 / 0.0254) and us["cases"][5]["deflection"][-1] == pytest.approx(case.tip_deflection / 0.0254, rel=1e-3)
    with pytest.raises(ValueError, match="units must be one of"):
        wing_views(result, "imperial")


def test_a_wing_without_ribs_draws_none_and_the_last_bay_ends_at_the_tip():
    assert wing_views(run(**{"geometry.rib_spacing": None, "rib": None}), "SI")["ribs"] == []
    assert wing_views(run(**{"geometry.rib_spacing": 0.6}), "SI")["ribs"] == pytest.approx([0.0, 0.6, 1.2, 1.8, 2.0])


def test_a_wing_in_us_units_is_the_same_wing():
    si = run()
    data = example(**{"units": "US", "geometry.half_span": 2.0 / 0.0254, "geometry.chord": 0.45 / 0.0254, "geometry.rib_spacing": 0.5 / 0.0254,
                      "skin.core_thickness": 6.0 / 25.4,
                      "envelope.gross_weight": 2700.0 / LBF,
                      "envelope.altitudes": [0.0, 3000.0 / FOOT], "envelope.aileron.span_start": 1.2 / 0.0254,
                      "envelope.aileron.span_end": 1.9 / 0.0254, "envelope.gust.wing_area": 1.8 / 0.0254**2})
    us = analyze_wing(*wing_from_dict(data))
    assert us.section.EI == pytest.approx(si.section.EI, rel=1e-12)
    assert [c.governing.margin_ultimate for c in us.cases] == pytest.approx([c.governing.margin_ultimate for c in si.cases], rel=1e-9)


@pytest.mark.parametrize("changes, message", [
    ({"geometry.sweep": 10.0}, r"\[geometry\] has unknown keys sweep"),
    ({"geometry.chord": None}, r"\[geometry\] is missing chord"),
    ({"units": "imperial"}, "units must be one of"),
    ({"envelope.speed_unit": "knots"}, "speed_unit must be one of"),
    ({"geometry.rear_spar": 0.2}, "0 < front < rear < 1"),
    ({"geometry.airfoil": "clark-y"}, "NACA four-digit"),
    ({"envelope.negative_load_factor": 0.5}, "below zero"),
    ({"envelope.altitudes": [20000.0]}, "between 0 and 11000"),
    ({"envelope.proof_factor": 1.6}, "between 1 and the ultimate factor"),
    ({"skin.core": None}, "A core needs its density"),
    ({"skin.core_density": 48.0}, "core names a library core, which gives its stiffness and density; remove core_density or the core"),
    ({"skin.core": "im7-8552"}, "is not a sandwich core in the library"),
    ({"skin.core": None, "skin.core_density": 48.0, "skin.core_modulus": 50.0}, "a typed core needs both core_modulus and core_shear_modulus"),
    ({"spar.core": "divinycell-h45"}, "A core material was given without a core thickness"),
    ({"skin.half_stack": []}, "at least one ply"),
    ({"material.library": "no-such-material"}, "unknown library material"),
    ({"material.strengths": "A-basis"}, 'strengths must be "mean" or "B-basis"'),
    ({"material.dataset": "ncamp-im7-8552-2019-rtd-measured-v1"}, "give dataset or strengths, not both"),
    ({"material.library": "as4-8552", "material.ply_thickness": 0.18, "material.density": 1580.0}, r"holds no B-basis strengths for 'as4-8552'; materials with them: \['im7-8552'\]"),
    ({"envelope.speeds.cruise": -50.0}, "greater than 0"),
    ({"envelope.speeds.climb": 30.0}, r"\[envelope.speeds\] has unknown keys climb"),
])
def test_a_wing_file_that_is_wrong_is_refused_by_name(changes, message):
    with pytest.raises(ValueError, match=message):
        wing_from_dict(example(**changes))


def test_a_core_comes_from_the_library_or_is_typed_in_the_stress_unit():
    wing, _ = wing_from_dict(example())
    core = wing.skin.core
    assert (core.name, core.modulus_Pa, core.shear_modulus_Pa, core.shear_strength_Pa) == ("Divinycell H45", 50e6, 15e6, 0.56e6)
    assert wing.skin.core_density_kg_m3 == 48.0  # the library's, which the hand calculation reads
    typed, _ = wing_from_dict(example(**{"skin.core": None, "skin.core_density": 48.0, "skin.core_modulus": 50.0, "skin.core_shear_modulus": 15.0}))
    assert (typed.skin.core.name, typed.skin.core.modulus_Pa, typed.skin.core.shear_modulus_Pa, typed.skin.core.shear_strength_Pa) == (
        "skin core", 50e6, 15e6, None)
    bare, _ = wing_from_dict(example(**{"skin.core": None, "skin.core_density": 48.0}))
    assert bare.skin.core is None and box_section(bare).EI == box_section(wing).EI  # the hand calculation does not read the core's stiffness


def test_a_library_material_without_a_ply_thickness_asks_for_one():
    with pytest.raises(ValueError, match="no ply thickness; give ply_thickness"):
        wing_from_dict(example(**{"material.library": "as4-8552"}))
    wing, _ = wing_from_dict(example(**{"material": {"library": "as4-8552", "ply_thickness": 0.19}}))
    assert wing.skin.material.ply_thickness_m == pytest.approx(0.19e-3)


# ----------------------------------------------------------------------------------------------- web buckling

def test_a_web_bay_buckles_in_shear_as_a_plate_and_the_weaker_direction_counts():
    from anisotropy_engine.buckling import ritz_buckling
    from anisotropy_engine.wing.section import WEB_PANEL_ASPECT, WEB_RITZ_TERMS, web_shear_buckling_load
    E, nu, t, b = 70e9, 0.3, 1e-3, 0.1
    D0 = E * t**3 / (12 * (1 - nu**2))
    isotropic = np.array([[D0, nu * D0, 0], [nu * D0, D0, 0], [0, 0, (1 - nu) / 2 * D0]])
    k_s = web_shear_buckling_load(isotropic, 3 * b, b) * b**2 / (math.pi**2 * D0)
    assert k_s == pytest.approx(5.35 + 4 / 3**2, rel=0.02)  # Timoshenko and Gere's fit for a simply supported plate in shear
    assert web_shear_buckling_load(isotropic, 50 * b, b) == web_shear_buckling_load(isotropic, WEB_PANEL_ASPECT * b, b)
    web = run().section.spar.D
    both = [ritz_buckling(web, 0.25, 0.05, [0, 0, sign], WEB_RITZ_TERMS).load_factor for sign in (1.0, -1.0)]
    assert max(both) > 1.3 * min(both)  # a [45/-45/0/0]s web is not alike in the two directions
    assert web_shear_buckling_load(web, 0.25, 0.05) == min(both)


def test_the_web_buckling_check_divides_the_bays_load_by_the_webs_shear_flow():
    result = run()
    section = result.section
    for case in result.cases:
        check = case.checks[3]
        assert check.name == "web buckling" and check.mode == "shear buckling"
        stations = case.stations
        with np.errstate(divide="ignore"):  # no shear flow at the tip: the ratio is infinite there
            expected = np.array(section.web_buckling_loads)[:, None] / stations.web_shear_flow
        assert stations.web_buckling_ratio == pytest.approx(expected)
        assert check.strength_ratio == pytest.approx(stations.web_buckling_ratio.min())
    thin = run(**{"spar.half_stack": [45, -45, 0]})
    assert thin.section.web_buckling_loads[0] < 0.5 * section.web_buckling_loads[0]  # bending stiffness grows as the cube of thickness


def test_the_example_wing_takes_its_strengths_at_b_basis_from_the_statistical_report_and_says_so():
    """ADR-0126: the strengths are the library's B-basis dataset's, each with its basis and page; stiffness, ply and density stay the
    means', so only the margins move."""
    from anisotropy_engine.library import library_material, strength_dataset
    from anisotropy_engine.wing.wing_file import wing_material

    basis_id = strength_dataset("im7-8552", "B-basis")
    assert basis_id == "ncamp-im7-8552-2019-rtd-bbasis-v1"
    b_wing, envelope = wing_from_dict(example())
    m_wing, _ = wing_from_dict(example(**{"material.strengths": "mean"}))
    plain_wing, _ = wing_from_dict(example(**{"material.strengths": None}))
    assert plain_wing.skin.material == m_wing.skin.material  # "mean" is the default
    b, m = b_wing.skin.material, m_wing.skin.material
    assert b.strength_basis == "B-basis" and m.strength_basis == "mean"
    assert b.lamina.strengths == library_material("im7-8552", basis_id).lamina.strengths
    assert b.lamina.model_copy(update={"strengths": None}) == m.lamina.model_copy(update={"strengths": None})
    assert (b.ply_thickness_m, b.density_kg_m3) == (m.ply_thickness_m, m.density_kg_m3)
    for role in ("F1t", "F1c", "F2t", "F2c", "F6"):
        assert getattr(b.lamina.strengths, role) < getattr(m.lamina.strengths, role), role

    shown = wing_material(b, "US")
    assert shown["strength_basis"] == "B-basis" and shown["dataset"] == "NCAMP 2019 · B-basis"
    assert "NCP-RP-2009-028" in shown["source"]
    rows = {row["role"]: row for row in shown["strengths"]}
    assert rows["F1t"]["value"] == pytest.approx(323.09) and rows["F1t"]["basis"] == "B-basis" and rows["F1t"]["page"] == 35
    assert rows["F1t"]["url"].endswith("#page=35")
    assert rows["F1c"]["key"] == "F1c-derived" and rows["F1c"]["value"] == pytest.approx(218.20) and rows["F1c"]["page"] == 46
    assert rows["F6"]["key"] == "F12-5pct" and rows["F6"]["value"] == pytest.approx(11.47) and rows["F6"]["page"] == 50
    assert shown["estimates"] == ["F1c", "F6"]
    typed = wing_material(m.model_copy(update={"strength_basis": "typed", "strength_sources": (), "strength_dataset": None,
                                               "strength_citation": None}))
    assert typed["strength_basis"] == "typed" and "basis" not in typed["strengths"][0] and typed["estimates"] == []

    on_b, on_m = analyze_wing(b_wing, envelope), analyze_wing(m_wing, envelope)
    assert on_b.section.EI == on_m.section.EI and on_b.mass_kg() == on_m.mass_kg()
    assert on_b.governing[1].margin_ultimate < on_m.governing[1].margin_ultimate
    assert on_b.passes  # the example carries 2700 N on B-basis strengths

