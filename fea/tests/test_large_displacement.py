"""A plate followed as its shape changes (ADR-0142): the step the writer adds, the exact answers of
tools/large_deflection_closed_forms.py, and CalculiX held to every case of fea/checks/large_displacement_cases/, with the small-load
check beside each: under a thousandth of its load a followed solve is the linear one, CalculiX's and our kernel's."""

import importlib.util
import math

import numpy as np
import pytest

from anisotropy_fea import paths  # where the files live (ADR-0036)
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.calculix import ENV_VARIABLE, find_ccx, parse_dat, run_calculix
from anisotropy_fea.femodel import build_model
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.large_displacement import (LargeDisplacementError, History, eight_node_twin, follow, load_case, read_history, reading_of,
                                               under)
from anisotropy_fea.spec import load_spec
from anisotropy_fea.units import deck_units_of, unit_factors
from anisotropy_fea.write_abaqus import write_abaqus
from anisotropy_fea.write_calculix import CalculixWriterError, LargeDisplacement, write_calculix

TOOL = paths.FEA / "tools" / "large_deflection_closed_forms.py"
CASES = sorted(paths.LARGE_CASES.glob("*.toml"))
PRESSURE = paths.CHECKS / "plate-pressure-isotropic" / "plate-pressure-isotropic.toml"
needs_ccx = pytest.mark.skipif(find_ccx() is None, reason=f"CalculiX not found: set {ENV_VARIABLE} or put ccx on PATH (docs/installation-fea-tools.md)")


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("large_deflection_closed_forms", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- the step the writer adds -----------------------------------------------------------------------


def test_the_step_follows_the_shape_only_when_asked_and_prints_at_the_fractions_named():
    model = build_model(eight_node_twin(load_spec(PRESSURE)))
    linear = write_calculix(model)
    assert "*STEP\n*STATIC\n" in linear and "NLGEOM" not in linear and "TIME POINTS" not in linear  # every run's checking deck stays linear
    followed = write_calculix(model, large=LargeDisplacement(first=0.02, at=(0.25, 0.5, 1.0)))
    assert "*TIME POINTS, NAME=Printed\n0.25, 0.5, 1.\n*STEP, NLGEOM, INC=200\n*STATIC\n0.02, 1.\n" in followed
    prints = [line for line in followed.splitlines() if line.startswith(("*NODE PRINT", "*EL PRINT"))]
    assert prints and all(line.endswith("TIME POINTS=Printed") for line in prints)
    assert followed.replace("*TIME POINTS, NAME=Printed\n0.25, 0.5, 1.\n", "").replace("*STEP, NLGEOM, INC=200\n*STATIC\n0.02, 1.\n", "*STEP\n*STATIC\n") \
        .replace(", TIME POINTS=Printed", "") == linear  # nothing else of the deck changes
    every = write_calculix(model, large=LargeDisplacement())
    assert "*STEP, NLGEOM, INC=200\n*STATIC\n0.1, 1.\n" in every and "TIME POINTS" not in every  # no fractions named: every increment is printed


@pytest.mark.parametrize("bad", [{"first": 0.0}, {"first": 1.5}, {"most": 0}, {"at": (0.5, 0.25)}, {"at": (0.0, 1.0)}, {"at": (0.5, 0.5)}, {"at": (0.5, 1.2)}])
def test_a_step_that_cannot_be_followed_is_refused(bad):
    with pytest.raises(CalculixWriterError):
        LargeDisplacement(**bad)


def test_the_same_plate_under_a_part_of_its_load():
    case = load_case(next(p for p in CASES if "naca" in p.name))
    small = under(case.spec, 0.001)
    assert small.loads[0].pressure == pytest.approx(case.spec.loads[0].pressure * 0.001) and small.supports == case.spec.supports
    pulled = load_case(next(p for p in CASES if p.name.startswith("strip-isotropic")))
    moved = [s.value for s in under(pulled.spec, 0.5).supports if s.value]
    assert moved == [pytest.approx(1.5e-3)]  # the 3 mm pull, halved, in metres


# --- the exact answers ------------------------------------------------------------------------------


def test_the_elastica_gives_the_printed_tables_and_the_small_deflection_beam(tool):
    """Mattiasson (1981), Table 1, and Bisshopp and Drucker (1945): the tip of the cantilever under P L^2 / EI = 1, 2, 5 and 10."""
    for alpha, deflection, shortening in ((1.0, 0.30172, 0.05643), (2.0, 0.49346, 0.16064), (5.0, 0.71379, 0.38763), (10.0, 0.81061, 0.55500)):
        w, u = tool.tip(alpha)
        assert w == pytest.approx(deflection, abs=0.6e-5) and u == pytest.approx(shortening, abs=0.6e-5)
    w, u = tool.tip(1e-3)
    assert w == pytest.approx(1e-3 / 3, rel=1e-6) and u == pytest.approx(1e-6 / 15, rel=1e-4)  # P L^3 / (3 EI), and the shortening (P L^2 / EI)^2 / 15
    theta, kappa = tool.station(10.0, 0.0)
    w, u = tool.tip(10.0)
    assert theta == 0.0 and kappa == pytest.approx(10.0 * (1.0 - u), rel=1e-6)  # the moment at the clamp is P times the tip's distance out


def test_the_laminate_strip_by_hand_equals_the_engine(tool):
    from anisotropy_engine.lamina import Lamina
    from anisotropy_engine.laminate import Ply, abd_matrices

    m = tool.PLY
    lamina = Lamina(E1=m["E1"] * 1e6, E2=m["E2"] * 1e6, G12=m["G12"] * 1e6, nu12=m["nu12"])
    A, _, D = abd_matrices([Ply(material=lamina, angle_deg=angle, thickness_m=tool.PLY_THICKNESS * 1e-3) for angle in tool.CROSS_PLY])
    stretching, bending = tool.laminate_strip(tool.CROSS_PLY, tool.PLY_THICKNESS, m)
    assert stretching == pytest.approx(1e-3 / np.linalg.inv(A)[0, 0], rel=1e-12)  # N/m to N/mm
    assert bending == pytest.approx(1e3 / np.linalg.inv(D)[0, 0], rel=1e-12)  # N m to N mm


def test_the_stretch_rule_is_the_first_stress_of_the_documented_law(tool):
    """S = E (e + e^2 / 2) on the first area; the force on the end is S times the stretch (1 + e)."""
    for e in (1e-4, 0.014, 0.03, 0.036):
        assert tool.stretch_rule(e) == pytest.approx((e + e * e / 2) * (1 + e) / e, rel=1e-12)
    assert tool.stretch_rule(0.036) == pytest.approx(1.0546, abs=1e-4) and tool.stretch_rule(0.014) == pytest.approx(1.0211, abs=1e-4)
    # a line's force to the second order, which the bent strip's shortening rests on: eps (1 + eps)(1 + eps / 2) = eps + 3 eps^2 / 2 + ...
    eps = 1e-3
    assert eps * tool.stretch_rule(eps) == pytest.approx(eps + 1.5 * eps**2, rel=1e-6)
    assert tool.line_strain(0.01, -0.3) == pytest.approx(0.003 + 0.003**2 / 2) and tool.line_strain(0.0, 0.2, 1e-4) == pytest.approx(1e-4 + 0.5e-8)


def test_the_committed_cases_are_what_the_tool_writes_and_hold_the_reports_table(tool):
    written = tool.build_cases()
    assert sorted(written) == [path.stem for path in CASES] and len(CASES) == 5
    for path in CASES:
        assert path.read_text(encoding="utf-8") == written[path.stem], f"{path.name} is not what tools/large_deflection_closed_forms.py --write gives"
    levy = load_case(next(p for p in CASES if "naca" in p.name))
    top = tool.LEVY[-1][0]
    assert levy.follow.at == pytest.approx([ratio / top for ratio, _ in tool.LEVY]) and levy.readings[0].values == tuple(w for _, w in tool.LEVY)
    side, h, E = 0.2, 0.002, 70e9
    assert -levy.spec.loads[0].pressure * side**4 / (E * h**4) == pytest.approx(top, rel=1e-9)  # the pressure is the table's last row
    assert levy.spec.material.nu12 == tool.LEVY_NU


# --- a case file ------------------------------------------------------------------------------------


def test_a_case_that_cannot_be_checked_is_refused_by_name(tmp_path):
    text = CASES[0].read_text(encoding="utf-8")

    def refused(changed: str, words: str) -> None:
        path = tmp_path / "case.toml"
        path.write_text(changed, encoding="utf-8")
        with pytest.raises(LargeDisplacementError, match=words):
            load_case(path)

    refused(text.replace('what = "displacement"', 'what = "rotation"', 1), "a reading is one of")
    refused(text.replace("at = [0.1, 0.2, 0.5, 1.0]", "at = [0.5, 1.0]"), "4 values for 2 fractions")
    refused(text.replace("component = 3", "component = 4", 1), "component 4")
    refused(text.replace('kind = "plate"', 'kind = "unnotched_tension"'), r"\[plate\]")
    refused(text.replace("[follow]", "[followed]"), "missing follow")
    refused(text.replace("height = ", "depth = ", 1), "depth")
    case = load_case(CASES[0])
    assert case.spec.si and case.units == "mm-MPa" and case.spec.kind == "plate" and case.follow.at[-1] == 1.0


def test_a_history_is_read_by_the_fraction_of_the_load_and_keeps_what_a_stopped_run_reached():
    case = load_case(next(p for p in CASES if p.name.startswith("cantilever-isotropic")))
    model = build_model(eight_node_twin(case.spec))
    dat = parse_dat(
        "\n total force (fx,fy,fz) for set EDGE-BOTTOM and time  0.5000000E+00\n\n        0.000000E+00  0.000000E+00 -2.916667E+01\n"
        "\n displacements (vx,vy,vz) for set PROBE-TIP and time  0.5000000E+00\n\n       163  0.000000E+00 -3.876000E+01  7.138000E+01\n")
    levels = read_history(model, dat)  # a run that reached half the load and stopped
    assert [level.fraction for level in levels] == [0.5]
    assert levels[0].reaction["Edge-Bottom"][2] == pytest.approx(-29.16667) and levels[0].displacement["tip"][2] == pytest.approx(71.38e-3)  # N and metres
    history = History(levels)
    assert history.at(0.5) is levels[0]
    assert reading_of(levels[0], case.readings[0], case.spec, case.units) == pytest.approx(0.7138)  # the tip's deflection over the length
    with pytest.raises(LargeDisplacementError, match="no level at 1 of the load; levels at 0.5"):
        history.at(1.0)
    with pytest.raises(LargeDisplacementError, match="printed no strain"):
        reading_of(levels[0], case.readings[2], case.spec, case.units)


# --- CalculiX held to the cases ---------------------------------------------------------------------


@needs_ccx
@pytest.mark.parametrize("path", CASES, ids=[path.stem for path in CASES])
def test_calculix_follows_the_shape_as_the_case_says(path, tmp_path):
    case = load_case(path)
    history = follow(case.spec, case.follow, tmp_path / "followed")
    assert [level.fraction for level in history.levels] == pytest.approx(list(case.follow.at), abs=1e-6)
    for reading in case.readings:
        for fraction, expected in zip(case.follow.at, reading.values):
            got = reading_of(history.at(fraction), reading, case.spec, case.units)
            assert got == pytest.approx(expected, rel=reading.tolerance), f"{reading.name} at {fraction:g} of the load"


@needs_ccx
@pytest.mark.parametrize("path", CASES, ids=[path.stem for path in CASES])
def test_under_a_small_load_following_the_shape_changes_nothing(path, tmp_path):
    """The other end of the same solve: at a thousandth of the load the followed answer is CalculiX's linear one, and our kernel's."""
    case = load_case(path)
    small = under(case.spec, case.small_load["factor"])
    followed = follow(small, LargeDisplacement(first=1.0), tmp_path / "followed").levels[-1]
    model = build_model(eight_node_twin(small))
    deck = tmp_path / "linear" / "linear.inp"
    deck.parent.mkdir()
    deck.write_text(write_calculix(model), encoding="utf-8")
    linear = read_history(model, parse_dat(run_calculix(deck).dat_text))[-1]
    first_order = build_model(small.model_copy(update={"mesh": small.mesh.model_copy(update={"element_order": 1})}))
    ours_deck = tmp_path / "kernel.inp"
    ours_deck.write_text(write_abaqus(first_order), encoding="utf-8")
    read = read_deck(ours_deck, deck_units_of(small.units))
    ours = solve_deck(read)
    length = unit_factors(case.units)["length"]
    compared = 0
    for reading in case.readings:
        if reading.name not in case.small_load.get("readings", [reading.name]):
            continue  # a reading that is second order in the load, as the tip's coming back is, has no linear answer to equal
        got = reading_of(followed, reading, small, case.units)
        assert got == pytest.approx(reading_of(linear, reading, small, case.units), rel=case.small_load["tolerance"]), reading.name
        if reading.what == "displacement":
            kernel = ours.displacement[first_order.probe_nodes[reading.of], reading.component - 1] / length * reading.scale
            assert got == pytest.approx(kernel, rel=case.small_load["kernel_tolerance"]), reading.name
        elif reading.what == "reaction":
            kernel = ours.reaction_of(read.nsets[reading.of])[reading.component - 1] / unit_factors(case.units)["force"] * reading.scale
            assert got == pytest.approx(kernel, rel=case.small_load["kernel_tolerance"] + case.small_load["tolerance"]), reading.name
        compared += 1
    assert compared


@needs_ccx
def test_the_stretched_strips_force_is_the_linear_one_times_the_rule(tool, tmp_path):
    """The rule itself, read off two runs of one deck: CalculiX with the shape followed over CalculiX without."""
    case = load_case(next(p for p in CASES if p.name.startswith("strip-cross-ply")))
    model = build_model(eight_node_twin(case.spec))
    deck = tmp_path / "linear.inp"
    deck.write_text(write_calculix(model), encoding="utf-8")
    linear = read_history(model, parse_dat(run_calculix(deck).dat_text))[-1].reaction["Edge-Top"][1]
    followed = follow(case.spec, case.follow, tmp_path / "followed")
    for fraction in case.follow.at:
        assert followed.at(fraction).reaction["Edge-Top"][1] / (linear * fraction) == pytest.approx(tool.stretch_rule(0.03 * fraction), rel=1e-5)
    assert math.isclose(tool.stretch_rule(0.03), 1.04545, abs_tol=1e-6)


@needs_ccx
def test_a_pressure_stays_square_to_the_bent_plate_and_a_force_keeps_its_direction(tmp_path):
    """What the loads do once the shape is followed. A pressure on a strip bent far presses square to it where it now lies, so its sum is
    the pressure on the chord from the clamp to the tip, turned a quarter: along the strip p b w, across it p b (L + v), with w and v the
    tip's displacements. A force named along z stays along z: the elastica cases rest on it, and the clamp's reaction shows it here."""
    case = load_case(next(p for p in CASES if p.name.startswith("cantilever-isotropic")))
    pressure, width, length = 0.05e6, 0.010, 0.100  # Pa toward +z, on a strip 10 mm by 100 mm
    load = case.spec.loads[0].model_copy(update={"region": "Face", "dof": None, "total": None, "pressure": -pressure})
    pressed = follow(case.spec.model_copy(update={"loads": [load]}), LargeDisplacement(first=0.02, at=(0.01, 1.0)), tmp_path / "pressed")
    small, far = pressed.at(0.01), pressed.at(1.0)
    assert small.reaction["Edge-Bottom"][2] == pytest.approx(-0.01 * pressure * width * length, rel=0.01) and abs(small.reaction["Edge-Bottom"][1]) < 0.006
    v, w = far.displacement["tip"][1], far.displacement["tip"][2]
    assert w > 0.75 * length and v < -0.5 * length  # bent far: the tip stands at 0.79 of the length and has come back by half of it
    assert far.reaction["Edge-Bottom"][1] == pytest.approx(pressure * width * w, rel=0.01)
    assert far.reaction["Edge-Bottom"][2] == pytest.approx(-pressure * width * (length + v), rel=0.01)
    forced = follow(case.spec, LargeDisplacement(first=0.02, at=(1.0,)), tmp_path / "forced").at(1.0)
    total = case.spec.loads[0].total
    assert forced.reaction["Edge-Bottom"][2] == pytest.approx(-total, rel=1e-6) and abs(forced.reaction["Edge-Bottom"][1]) < 1e-6 * total
