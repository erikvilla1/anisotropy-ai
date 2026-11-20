"""The wing's CalculiX model (ADR-0117): its loads, its ply axes and its answers against a thin-walled beam worked here without it.

Tests that build the shape skip with a reason when Gmsh is missing, and those that solve skip when CalculiX is missing.
"""

import math
import tomllib
from pathlib import Path

import numpy as np
import pytest

from anisotropy_engine.laminate import abd_matrices
from anisotropy_engine.wing import analyze_wing, wing_from_dict
from anisotropy_engine.wing.flutter import TypicalSection, flutter_speed
from anisotropy_engine.wing.section import box_section
from anisotropy_fea.calculix import find_ccx
from anisotropy_fea.mesher import gmsh_available
from anisotropy_fea.wing_model import (
    MAX_LAYERS, PATTERNS, SKINS, WEBS, WingModelError, build_wing_model, buckling_cases, case_factors, check_describable, element_loads,
    fe_cases, fe_section, layers, panel_buckling, read_modes, run_modes, run_wing_model, schrenk_lift, serendipity,
    strip_pressure, typical_section,
)
from anisotropy_fea.wing_shape import mid_surface_section

EXAMPLE = Path(__file__).parents[2] / "engine" / "examples" / "example-wing.toml"
COARSE = 0.06  # m: a mesh coarse enough for every change's test run; the mesh study is in the ADR
needs_gmsh = pytest.mark.skipif(gmsh_available() is None,
                                reason="Gmsh is not available: from fea/ run `uv sync --extra mesh` (on Linux also apt install libglu1-mesa)")
needs_ccx = pytest.mark.skipif(find_ccx() is None, reason="CalculiX not found: set ANISOTROPY_CCX or put ccx on PATH (docs/installation-fea-tools.md)")


def example(**changes):
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
    return wing_from_dict(data)


# ----------------------------------------------------------------------------------------------- loads, no mesh

def test_the_lift_shape_carries_one_newton_and_the_strip_its_lift_and_moment():
    y = np.linspace(0, 2.0, 200001)
    assert np.trapezoid(schrenk_lift(y, 2.0), y) == pytest.approx(1.0, rel=1e-6)
    x = np.linspace(0.02, 0.4, 100001)
    p = strip_pressure(x, np.full_like(x, 3.0), np.full_like(x, -0.4), 0.02, 0.4, 0.1)
    assert np.trapezoid(p, x) == pytest.approx(3.0, rel=1e-9)
    assert -np.trapezoid(p * (x - 0.1), x) == pytest.approx(-0.4, rel=1e-9)  # nose up positive about the aerodynamic center


def test_serendipity_shape_functions_sum_to_one_and_their_slopes_to_zero():
    for xi, eta in ((0.0, 0.0), (0.3, -0.7), (-1.0, 1.0)):
        n, dxi, deta = serendipity(xi, eta)
        assert n.sum() == pytest.approx(1.0) and dxi.sum() == pytest.approx(0.0, abs=1e-12) and deta.sum() == pytest.approx(0.0, abs=1e-12)


def test_a_layup_becomes_its_face_the_core_and_the_face_mirrored():
    wing, _ = example()
    stack = layers(wing.skin)
    angles = [layer.angle_deg for layer in stack if layer.material == "PLY"]
    assert angles == list(wing.skin.half_stack_deg) + list(wing.skin.half_stack_deg)[::-1]
    assert [layer.material for layer in stack].count("CORE") == 1
    assert sum(layer.thickness_m for layer in stack) == pytest.approx(wing.skin.fiber_thickness_m + wing.skin.core_thickness_m)


def test_the_case_factors_are_the_hand_calculations_running_loads():
    wing, envelope = example()
    result = analyze_wing(wing, envelope)
    case = result.cases[5].case
    factors = case_factors(case, wing, envelope)
    assert factors["lift"] == pytest.approx(case.load_factor * envelope.gross_weight_N / 2)
    assert factors["moment"] == pytest.approx(case.dynamic_pressure_Pa * wing.geometry.chord_m**2 * wing.aerodynamics.pitching_moment_coefficient)


def test_a_core_without_its_stiffness_and_ribs_without_a_layup_are_refused():
    with pytest.raises(WingModelError, match="skin core's stiffness"):
        check_describable(example(**{"skin.core": None, "skin.core_density": 48.0})[0])
    with pytest.raises(WingModelError, match="no rib layup"):
        check_describable(example(rib=None)[0])


CAPS = {"front_width": 0.045, "rear_width": 0.045, "half_stack": [0, 0, 45, -45, 0]}


@pytest.mark.parametrize("changes", [{"spar_caps": CAPS}, {"skin.zones": [{"start": 0, "end": 0.4, "half_stack": [0, 0, 45, -45, 0]}]}])
def test_spar_caps_and_zones_along_the_span_are_refused_until_the_model_builds_them(changes):
    with pytest.raises(WingModelError, match="does not take spar caps or zones along the span yet"):
        check_describable(example(**changes)[0])


WEB_14 = [45, -45, 45, -45, 45, -45, 0]  # fourteen plies through the web: one more layer than CalculiX solves, the middle pair at 0


def test_past_the_solvers_limit_plies_of_one_angle_side_by_side_are_one_layer():
    wing, _ = example(**{"spar.half_stack": WEB_14})
    stack, ply = layers(wing.spar), wing.spar.material.ply_thickness_m
    assert len(stack) == MAX_LAYERS == 13
    assert [layer.angle_deg for layer in stack] == [45, -45, 45, -45, 45, -45, 0, -45, 45, -45, 45, -45, 45]
    assert stack[6].thickness_m == pytest.approx(2 * ply) and sum(layer.thickness_m for layer in stack) == pytest.approx(14 * ply)
    assert len(layers(example()[0].spar)) == 8, "within the limit every ply stays a layer, the middle pair too"
    check_describable(wing)
    with pytest.raises(WingModelError, match="at most 13 layers through a part.*the spar layup makes 15"):
        check_describable(example(**{"spar.half_stack": [*WEB_14, 90]})[0])


# ----------------------------------------------------------------------------------------------- the model, Gmsh only

@pytest.fixture(scope="module")
def box_model():
    if gmsh_available() is None:
        pytest.skip("Gmsh is not available")
    wing, envelope = example()
    return build_wing_model(wing, envelope, COARSE, skins="box")


@needs_gmsh
def test_each_load_pattern_carries_what_it_says(box_model):
    model = box_model
    x, y = model.mesh.nodes[:, 0], model.mesh.nodes[:, 1]
    x_ac = model.wing.aerodynamics.aerodynamic_center * model.wing.geometry.chord_m
    aileron = model.envelope.aileron
    span = aileron.span_end_m - aileron.span_start_m
    expected = {"lift": (1.0, 0.0), "moment": (0.0, model.wing.geometry.half_span_m), "aileron lift": (span, 0.0), "aileron moment": (0.0, span)}
    assert tuple(model.patterns) == PATTERNS
    for name, (force, moment) in expected.items():
        f = model.patterns[name]
        assert f.sum() == pytest.approx(force, abs=1e-3 * max(force, 1))
        assert -(f * (x - x_ac)).sum() == pytest.approx(moment, abs=1e-3 * max(moment, 1))
    yy = np.linspace(0, 2.0, 200001)
    assert model.patterns["lift"] @ y == pytest.approx(np.trapezoid(schrenk_lift(yy, 2.0) * yy, yy), rel=1e-4)


@needs_gmsh
def test_the_box_keeps_only_what_lies_between_the_spars(box_model):
    model = box_model
    x_front, x_rear = model.section.spar_x_m
    centre = model.mesh.nodes[model.mesh.elements[:, :4]].mean(axis=1)
    skins = np.isin(model.part_of, SKINS)
    assert ((centre[skins, 0] > x_front) & (centre[skins, 0] < x_rear)).all()
    assert np.unique(model.mesh.elements).size == model.mesh.nodes.shape[0]  # no node is left without an element
    assert set(WEBS) <= set(model.part_of)


@needs_gmsh
def test_every_group_holds_one_layup_whose_elements_face_its_normal(box_model):
    model = box_model
    corners = model.mesh.nodes[model.mesh.elements[:, :4]]
    normals = np.cross(corners[:, 2] - corners[:, 0], corners[:, 3] - corners[:, 1])
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    for group in model.groups:
        assert abs(group.normal @ group.reference) < 1e-12
        assert (normals[group.members] @ group.normal).min() > math.cos(math.radians(1.01 + 2.0))  # half a step, plus the tilt allowed


# ----------------------------------------------------------------------------------------------- solved, Gmsh and CalculiX

def thin_walled_box(wing):
    """The box at the skins' mid-surface as a thin-walled beam, written here without the model: its bending stiffness for a
    vertical load (with the section's product of inertia) and its Bredt torsion stiffness."""
    section = mid_surface_section(wing)
    x_front, x_rear = section.spar_x_m

    def stiffness(layup):
        A, _, _ = abd_matrices(layup.plies())
        a = np.linalg.inv(A)
        extra = (layup.core.modulus_Pa * layup.core_thickness_m, layup.core.shear_modulus_Pa * layup.core_thickness_m) if layup.core else (0, 0)
        return 1 / a[0, 0] + extra[0], 1 / a[2, 2] + extra[1]
    skin_E, skin_G = stiffness(wing.skin)
    spar_E, spar_G = stiffness(wing.spar)
    walls = []
    for curve in (section.upper, section.lower):
        inside = curve[(curve[:, 0] >= x_front - 1e-12) & (curve[:, 0] <= x_rear + 1e-12)]
        walls += [(p, q, skin_E, skin_G) for p, q in zip(inside[:-1], inside[1:])]
    walls += [(np.array([x, top]), np.array([x, bottom]), spar_E, spar_G)
              for x, top, bottom in zip(section.spar_x_m, section.spar_top_m, section.spar_bottom_m)]
    EA = sum(E * np.linalg.norm(q - p) for p, q, E, _ in walls)
    xc = sum(E * np.linalg.norm(q - p) * (p[0] + q[0]) / 2 for p, q, E, _ in walls) / EA
    zc = sum(E * np.linalg.norm(q - p) * (p[1] + q[1]) / 2 for p, q, E, _ in walls) / EA
    Izz = Ixx = Ixz = 0.0
    for p, q, E, _ in walls:
        d, s, a = q - p, np.linalg.norm(q - p), p - (xc, zc)
        Izz += E * s * (a[1] ** 2 + a[1] * d[1] + d[1] ** 2 / 3)
        Ixx += E * s * (a[0] ** 2 + a[0] * d[0] + d[0] ** 2 / 3)
        Ixz += E * s * (a[0] * a[1] + (a[0] * d[1] + a[1] * d[0]) / 2 + d[0] * d[1] / 3)
    xs = np.linspace(x_front, x_rear, 20001)
    enclosed = np.trapezoid(np.interp(xs, *section.upper.T) - np.interp(xs, *section.lower.T), xs)
    flexibility = sum(np.linalg.norm(q - p) / G for p, q, _, G in walls)
    return Izz - Ixz**2 / Ixx, 4 * enclosed**2 / flexibility


@pytest.fixture(scope="module")
def solved(box_model, tmp_path_factory):
    if find_ccx() is None:
        pytest.skip("CalculiX not found")
    return run_wing_model(box_model, tmp_path_factory.mktemp("wing"))


@needs_gmsh
@needs_ccx
def test_a_fourteen_ply_web_is_solved_as_thirteen_layers(tmp_path):
    """CalculiX stops on a section of 14 layers (MAX_LAYERS); the joined pair keeps the web's stiffness and the solve goes through."""
    wing, envelope = example(**{"spar.half_stack": WEB_14})
    model = build_wing_model(wing, envelope, COARSE, skins="box")
    sections = model.deck.split("*SHELL SECTION")[1:]
    assert max(sum(", PLY, " in line or ", CORE_" in line for line in block.splitlines()[1:]) for block in sections) == MAX_LAYERS
    results = run_wing_model(model, tmp_path)
    assert results.point_layer.max() == MAX_LAYERS - 1 and np.isfinite(results.displacement["lift"]).all()


@needs_gmsh
@needs_ccx
def test_the_box_bends_and_twists_as_a_thin_walled_beam_of_the_same_walls(box_model, solved):
    model, results = box_model, solved
    EI, GJ = thin_walled_box(model.wing)
    L = model.wing.geometry.half_span_m
    y = np.linspace(0, L, 2001)
    lift = schrenk_lift(y, L)
    moment = np.array([np.trapezoid(np.where(y >= s, lift * (y - s), 0), y) for s in y])
    section = fe_section(model, results)
    front, rear = (np.unique(model.mesh.elements[model.mesh.element_sets[name]]) for name in WEBS)
    tip = np.abs(model.mesh.nodes[:, 1] - L) < 1e-9
    w = results.displacement["lift"][np.r_[front[tip[front]], rear[tip[rear]]], 2].mean()
    assert np.trapezoid(moment * (L - y), y) / w == pytest.approx(EI, rel=0.05)  # 1.5 % at 40 mm; the clamped root stiffens a little
    assert section.torsion_stiffness == pytest.approx(GJ, rel=0.07)  # 4 % at 40 mm, the root's warping held
    assert model.section.spar_x_m[0] < section.shear_center_m < model.section.spar_x_m[1]
    # The hand calculation works the same thin-walled box (ADR-0115 amendment 3), without the core's own small stiffness.
    hand = box_section(model.wing)
    assert hand.EI == pytest.approx(EI, rel=0.01) and hand.GJ == pytest.approx(GJ, rel=0.01)
    assert section.shear_center_m == pytest.approx(hand.shear_center_m, rel=0.02)  # 0.2 % at 40 mm


@needs_gmsh
@needs_ccx
def test_the_cases_and_their_checks_follow_the_hand_calculation_in_kind(box_model, solved):
    model, results = box_model, solved
    hand = analyze_wing(model.wing, model.envelope)
    fe = fe_cases(model, results, box_section(model.wing).shear_center_m)
    assert [c.case.number for c in fe] == [c.case.number for c in hand.cases]
    for c, h in zip(fe, hand.cases):
        assert c.applied_lift_N == pytest.approx(c.factors["lift"] + c.factors.get("aileron lift", 0.0)
                                                 * (model.envelope.aileron.span_end_m - model.envelope.aileron.span_start_m), rel=1e-3)
        assert np.sign(c.tip_deflection_m) == np.sign(h.tip_deflection)
        assert c.tip_deflection_m == pytest.approx(h.tip_deflection, rel=0.1)  # 2 % at 40 mm: both at mid-thickness
        assert {check.name for check in c.checks} == {"skin plies", "spar plies", "rib plies", "core shear"}
        assert min(check.margin_ultimate for check in c.root_checks) <= c.governing.margin_ultimate


@needs_gmsh
@needs_ccx
def test_panel_buckling_takes_each_bays_own_loads(box_model, solved):
    model, results = box_model, solved
    cases = buckling_cases(model)
    assert [c.number for c in cases] == [6, 7, 8, 9]  # the maneuver corners, two at each load factor with the same root moment
    found = panel_buckling(model, results, cases)
    assert [b.case.number for b in found] == [6, 7, 8, 9]
    up, down = found[0], found[2]
    assert up.part == "Upper skin" and down.part == "Lower skin"
    assert all(b.loads[0] < 0 for b in found)  # the bay that buckles is the one in compression
    hand = analyze_wing(model.wing, model.envelope).cases[5]
    skin = next(check for check in hand.checks if check.name == "skin buckling")
    assert up.factor == pytest.approx(skin.strength_ratio, rel=0.35)
    loads = element_loads(model, results.stress["lift"], results)
    upper = model.part_of == "Upper skin"
    assert loads[upper, 0].mean() < 0 < loads[model.part_of == "Lower skin", 0].mean()


@needs_gmsh
@needs_ccx
def test_the_first_modes_and_the_flutter_strip(box_model, solved, tmp_path):
    model = box_model
    modes = run_modes(model, tmp_path)
    assert modes.modes[0].kind == "bending"
    hand = box_section(model.wing).first_bending_frequency_Hz
    assert modes.modes[0].frequency_Hz == pytest.approx(hand, rel=0.05)  # 0.3 % at 40 mm; the model has the ribs' mass too
    assert any(mode.kind == "torsion" for mode in modes.modes)
    strip = typical_section(model, fe_section(model, solved), modes)
    assert isinstance(strip, TypicalSection) and -1 < strip.elastic_axis < 1
    assert flutter_speed(strip, 1.225).speed_m_s > model.envelope.speeds.flutter
    assert read_modes(model, (tmp_path / "wing-modes.dat").read_text(), modes.solve_seconds).modes == modes.modes


def test_the_k_method_meets_a_p_k_solution_with_theodorsens_exact_function():
    """An independent check of wing/flutter.py: the p-k method, written here, with C(k) from the Hankel functions. Both find
    the speed at which the damping is zero, where the two methods are the same equations; only C(k) differs."""
    from scipy.special import hankel2

    def exact(k):
        return hankel2(1, k) / (hankel2(1, k) + 1j * hankel2(0, k))

    for k, value in ((0.1, 0.8319 - 0.1723j), (0.3, 0.6650 - 0.1793j), (1.0, 0.5394 - 0.1003j)):
        assert abs(exact(k) - value) < 6e-5  # the values the engine's test keeps

    a, x, r2, sigma, mu = -0.2, 0.1, 6 / 25, 0.4, 20.0
    M, K = np.array([[1, x], [x, r2]]), np.diag([sigma**2, r2])

    def roots(U):
        out = []
        for guess in (sigma, 1.0):
            w = guess
            for _ in range(300):
                k = w / U
                C = exact(k)
                Q = np.array([[1 - 2j * C / k, -(a + 1j / k + 2 * C / k**2 + 1j * C * (1 - 2 * a) / k)],
                              [-a + 2j * (a + 0.5) * C / k, 0.125 + a * a - 1j * (0.5 - a) / k + 2 * (a + 0.5) * C / k**2
                               + 1j * (a + 0.5) * (1 - 2 * a) * C / k]])
                p = np.sqrt(np.linalg.eigvals(-np.linalg.solve(M, K - (k * U) ** 2 / mu * Q)).astype(complex))
                p = np.where(p.imag < 0, -p, p)
                j = int(np.argmin(np.abs(p.imag - w)))
                if abs(p[j].imag - w) < 1e-12:
                    break
                w = (w + p[j].imag) / 2
            out.append(p[j])
        return out
    speeds = np.linspace(1.5, 2.6, 221)
    damping = np.array([[root.real for root in roots(U)] for U in speeds])
    crossing = next(i for i in range(1, len(speeds)) if (damping[i - 1] < 0).all() and (damping[i] >= 0).any())
    branch = int(np.argmax(damping[crossing]))
    t = -damping[crossing - 1, branch] / (damping[crossing, branch] - damping[crossing - 1, branch])
    pk = speeds[crossing - 1] + t * (speeds[crossing] - speeds[crossing - 1])
    strip = TypicalSection(1.0, a, x, math.sqrt(r2), mu * math.pi, sigma / (2 * math.pi), 1 / (2 * math.pi))
    assert flutter_speed(strip, 1.0).speed_m_s == pytest.approx(pk, rel=0.01)  # 2.170 against 2.184
