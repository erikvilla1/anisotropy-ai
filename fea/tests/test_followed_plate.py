"""A plate solved with its shape followed, the Analysis step's switch (ADR-0142, step 2): the row and the spec key, what the solver that
follows the shape takes, the whole plate read from what CalculiX prints, and that reading held to our own kernel under a small load, to
the applied load at every level and to the published plate of step 1."""

import json
import re
from pathlib import Path

import numpy as np
import pytest

from anisotropy_fea import followed_plate, paths
from anisotropy_fea.calculix import ENV_VARIABLE, CalculixError, find_ccx
from anisotropy_fea.checks import setup_checklist
from anisotropy_fea.explain import explanation
from anisotropy_fea.femodel import build_model
from anisotropy_fea.fields import FOLLOW_FROM, field_data, run_answer
from anisotropy_fea.followed_plate import (LEVELS, MOST_BRICKS, FollowedError, Stopped, crossing, follow_plate, followed_fields, frame_of,
                                           loads_on_held_nodes, midplane_slopes, printed_blocks, read_plate, serendipity_derivatives,
                                           shell_solution, through_the_height, why_not, write_followed)
from anisotropy_fea.intake import (FOLLOWED_KEY, FOLLOWED_LABEL, FORM_VERSION, IntakeError, build_specs, check_form, designation_for, read_values,
                                   spec_from_values, values_of_spec)
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.large_displacement import eight_node_twin, load_case, under
from anisotropy_fea.spec import Analysis, SpecError, follows_shape, load_spec, parse_spec
from anisotropy_fea.tension_input import FOLLOWED_BRICKS, complete_plate
from anisotropy_fea.write_calculix import LargeDisplacement, write_calculix

needs_ccx = pytest.mark.skipif(find_ccx() is None, reason=f"CalculiX not found: set {ENV_VARIABLE} or put ccx on PATH (docs/installation-fea-tools.md)")
CLAMPED = [{"region": f"Edge-{side}", "dofs": [1, 2, 3, 4, 5, 6]} for side in ("Bottom", "Top", "Left", "Right")]
PLATE = {"input": "plate", "test": "plate", "library": "im7-8552", "angles": [45, 0, -45, 90], "symmetric": "yes", "length": 200, "width": 200,
         "supports": CLAMPED, "loads": [{"region": "Face", "pressure": 0.03}]}
COARSE = {"element_size": 25}  # 64 elements of 8 plies: a followed solve of a few seconds
D3039 = paths.CHECKS / "d3039-im7-8552" / "d3039-im7-8552.toml"
TOOLS = {"ccx": lambda: Path("ccx"), "tectonic": lambda: "tectonic", "gmsh": lambda: "4"}


@pytest.fixture(autouse=True)
def versions(monkeypatch):
    monkeypatch.setattr("anisotropy_fea.checks.ccx_version", lambda ccx: "2.22" if ccx is not None else None)  # as tests/test_checks.py


def values_file(folder: Path, **changes) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "values.json"
    path.write_text(json.dumps({"form_version": FORM_VERSION, **PLATE, **changes}), encoding="utf-8")
    return path


def spec_of(folder: Path, **changes):
    """The plate's spec in SI, as a run builds it from the page's rows."""
    form = read_values(values_file(folder, **changes))
    checked = check_form(form)
    return spec_from_values(checked, designation_for(checked, folder / "none"), form.path.name)


# --- the switch: a row of the plate, a key of its spec ------------------------------------------------


def test_the_switch_is_a_row_of_the_plate_that_reaches_both_specs_and_comes_back(tmp_path):
    form = read_values(values_file(tmp_path, **{FOLLOWED_KEY: True}))
    assert form.followed is True
    checked = check_form(form)
    main, twin = build_specs(checked, designation_for(checked, tmp_path / "none"), form.path.name)
    for text in (main, twin):
        assert re.search(r"^\[analysis\]\n(#.*\n)*large_displacement = true", text, flags=re.M)
    spec = parse_spec(main, "plate.toml")
    assert follows_shape(spec) and values_of_spec(spec)[FOLLOWED_KEY] is True  # a past run reopens with the switch on
    for said in ("yes", "Yes"):
        assert read_values(values_file(tmp_path / said, **{FOLLOWED_KEY: said})).followed is True
    for said in (False, "no", None):
        off = read_values(values_file(tmp_path / f"off-{said}", **({} if said is None else {FOLLOWED_KEY: said})))
        assert off.followed is False
        checked = check_form(off)
        plain = build_specs(checked, designation_for(checked, tmp_path / "none"), off.path.name)[0]
        assert "[analysis]" not in plain and FOLLOWED_KEY not in values_of_spec(parse_spec(plain, "plate.toml"))  # off is the spec it always was


@pytest.mark.parametrize("said", [3, "on", [True]])
def test_a_switch_that_is_neither_on_nor_off_is_refused_by_its_row(tmp_path, said):
    with pytest.raises(IntakeError, match="nonlinear_geometry is true or false"):
        read_values(values_file(tmp_path, **{FOLLOWED_KEY: said}))


def test_a_coupon_pulled_along_its_length_is_told_in_one_line_why_it_is_not_followed(tmp_path):
    values = {**values_of_spec(load_spec(D3039)), FOLLOWED_KEY: True}
    path = tmp_path / "values.json"
    path.write_text(json.dumps({"form_version": FORM_VERSION, **values}), encoding="utf-8")
    with pytest.raises(IntakeError, match="Nonlinear geometry: offered on a plate only: a coupon pulled along its length keeps its shape"):
        check_form(read_values(path))
    checklist = setup_checklist(read_values(path), tmp_path / "none", **TOOLS)[0]
    solver = next(item for item in checklist.items if item.id == "solver")
    assert checklist.state == "blocked" and solver.state == "fail" and FOLLOWED_LABEL in solver.rows
    assert "offered on a plate only" in solver.message and "abaqus" not in solver.message.lower() and "ADR" not in solver.message
    # the spec holds the same rule for a file written by hand
    text = D3039.read_text(encoding="utf-8") + "\n[analysis]\nlarge_displacement = true\n"
    with pytest.raises(SpecError, match="analysis.large_displacement belongs to the plate kind only"):
        parse_spec(text, "coupon.toml")
    assert not follows_shape(load_spec(D3039))


def test_a_followed_plate_is_given_a_mesh_its_solve_takes_in_a_short_time():
    asked = {key: value for key, value in PLATE.items() if key != "input"}
    linear, _ = complete_plate(asked)
    values, built = complete_plate(asked, followed=True)
    assert (linear["element_size"], values["element_size"]) == (4.0, 8.0)  # 2,500 elements; 625 of 8 plies, 5,000 solid elements
    assert 200 * 200 / values["element_size"] ** 2 * 8 <= FOLLOWED_BRICKS < MOST_BRICKS  # the size chosen never trips the limit of the check
    reason = next(b.reason for b in built if b.row == "element_size")
    assert "nonlinear geometry" in reason and "calculix" not in reason.lower()
    assert complete_plate({**asked, "element_size": 5}, followed=True)[0]["element_size"] == 5  # a size the engineer gave is kept
    thin, _ = complete_plate({**asked, "angles": [0, 90], "symmetric": "no"}, followed=True)
    assert thin["element_size"] == 4.0  # two plies: the linear plate's 2,500 elements are 5,000 solid elements, no coarser mesh needed


def test_the_setup_check_says_what_the_solver_that_follows_the_shape_takes(tmp_path):
    def solver(**changes):
        checklist = setup_checklist(read_values(values_file(tmp_path / str(len(changes)) / "-".join(changes), **{FOLLOWED_KEY: True}, **changes)),
                                    tmp_path / "none", **TOOLS)[0]
        return checklist, [item for item in checklist.items if item.id == "solver"][0]

    ready, item = solver()
    assert ready.state == "ready" and item.state == "pass" and "the plate's shape is followed as the load rises, in 10 levels" in item.message
    fine, item = solver(element_size=2)
    assert fine.state == "blocked" and item.state == "fail" and FOLLOWED_LABEL in item.rows
    assert "about 10,000 elements of 8 plies" in item.message and "at most 1,250 elements of this laminate: use an element size of 5.7 mm or more" in item.message
    thick, item = solver(angles=[0, 45, -45, 90, 0, 45, -45], symmetric="yes")
    assert thick.state == "blocked" and "the laminate has 14 plies" in item.message and "turn nonlinear geometry off to solve this plate" in item.message
    off = setup_checklist(read_values(values_file(tmp_path / "off", element_size=2)), tmp_path / "none", **TOOLS)[0]
    assert off.state == "ready" and "nonlinear" not in next(i for i in off.items if i.id == "solver").message  # the linear plate is judged as before
    # no report is written of a followed run: the check says so, and never warns that a report cannot be written
    report = lambda checklist: next(i for i in checklist.items if i.id == "document")  # noqa: E731
    assert report(ready).state == "pass" and report(ready).message == "no report is written of a run with nonlinear geometry; its results are on the page"
    assert report(off).message == "the report is written as a PDF"
    bare = setup_checklist(read_values(values_file(tmp_path / "bare", **{FOLLOWED_KEY: True})), tmp_path / "none", **{**TOOLS, "tectonic": lambda: None})[0]
    assert report(bare).state == "pass" and "nonlinear geometry" in report(bare).message


def test_a_plate_is_judged_from_its_counts_before_any_mesh(tmp_path):
    spec = spec_of(tmp_path, **{FOLLOWED_KEY: True})
    assert why_not(spec) is None and spec.analysis == Analysis(large_displacement=True)
    assert "use an element size of 5.7 mm or more" in why_not(spec_of(tmp_path / "fine", element_size=2, **{FOLLOWED_KEY: True}))
    with pytest.raises(FollowedError, match="does not ask for its shape to be followed"):
        frame_of(spec_of(tmp_path / "off"))
    with pytest.raises(FollowedError, match="use an element size of"):
        frame_of(spec_of(tmp_path / "finer", element_size=2, **{FOLLOWED_KEY: True}))


# --- what is asked of CalculiX and what it prints ---------------------------------------------------------


def test_the_whole_plate_is_printed_and_no_results_file_is_written(tmp_path):
    spec = spec_of(tmp_path, **COARSE, **{FOLLOWED_KEY: True})
    model = build_model(eight_node_twin(spec))
    deck = write_calculix(model, large=LargeDisplacement(first=0.1, at=LEVELS, whole=True))
    assert "*STEP, NLGEOM, INC=200\n*STATIC\n0.1, 1.\n" in deck
    assert "*NODE PRINT, NSET=Nall, TIME POINTS=Printed\nU\n" in deck
    assert f"*EL PRINT, ELSET={model.section.elset}, GLOBAL=YES, TIME POINTS=Printed\nE, COORD\n" in deck
    assert "*NODE FILE" not in deck and "*EL FILE" not in deck  # ten levels of every layer would be hundreds of megabytes nobody opens
    assert all(f"NSET={name}" in deck for name in model.support_sets)  # every held node's own reaction
    probes = write_calculix(model, large=LargeDisplacement(first=0.1, at=LEVELS))
    assert "*NODE PRINT, NSET=Nall" not in probes and "*NODE FILE" in probes  # step 1's reading at probes is what it was


DAT = """
 displacements (vx,vy,vz) for set NALL and time  0.5000000E+00

         1  1.000000E-03  0.000000E+00 -2.000000E-01
         2  2.000000E-03  0.000000E+00 -4.000000E-01

 forces (fx,fy,fz) for set EDGE-LEFT and time  0.5000000E+00

         1  0.000000E+00  0.000000E+00  5.000000E+00

 strains (elem, integ.pnt.,exx,eyy,ezz,exy,exz,eyz) for set COUPON and time  0.5000000E+00

         1   1  1.0E-03  2.0E-03  0.0E+00  3.0E-03  0.0E+00  0.0E+00
         1   2  1.0E-03  2.0E-03  0.0E+00  3.0E-03  0.0E+00  0.0E+00

 displacements (vx,vy,vz) for set NALL and time  0.1000000E+01

         1  2.000000E-03  0.000000E+00 -3.000000E-01
         2  4.000000E-03  0.000000E+00 -6.0000
"""


def test_a_printed_file_is_read_a_block_at_a_time_and_a_block_cut_short_ends_it(tmp_path):
    path = tmp_path / "followed.dat"
    path.write_text(DAT, encoding="utf-8")
    blocks = list(printed_blocks(path))
    assert [(what, name, fraction, rows.shape) for what, name, fraction, rows in blocks] == [
        ("displacements", "NALL", 0.5, (2, 4)), ("forces", "EDGE-LEFT", 0.5, (1, 4)), ("strains", "COUPON", 0.5, (2, 8)), ("displacements", "NALL", 1.0, (2, 4))]
    assert blocks[0][3][1].tolist() == [2.0, 2e-3, 0.0, -0.4]
    path.write_text(DAT.rstrip()[: DAT.rstrip().rindex(" -6.0000")] + "\n", encoding="utf-8")  # the solver was stopped inside its last row
    assert [fraction for _, _, fraction, _ in printed_blocks(path)] == [0.5, 0.5, 0.5]


def test_the_strains_of_an_elements_points_reduce_to_a_line_in_the_height():
    """Two elements of two plies (0.2 and 0.3 mm), two heights in each ply and four points at each: a strain that is straight in the height
    comes back as its value at the middle and its slope, the in-plane spread of the points averaged away, and each ply's shear as its mean."""
    thickness = np.array([0.2e-3, 0.3e-3])
    heights = np.array([-0.25 + 0.2 * 0.2113, -0.25 + 0.2 * 0.7887, -0.05 + 0.3 * 0.2113, -0.05 + 0.3 * 0.7887])  # mm, from the bottom face up
    middle = np.array([[1e-3, -2e-3, 4e-4], [3e-3, 5e-4, -6e-4]])  # exx, eyy and the tensor shear exy of each element
    slope = np.array([[2.0, -1.0, 0.5], [-3.0, 0.25, 1.0]])  # per metre
    spread = np.array([1e-4, -1e-4, 3e-4, -3e-4])  # across the four points of a height: no part of the line
    ply_shear = np.array([[[1e-4, 2e-4], [3e-4, -1e-4]], [[-2e-4, 0.0], [5e-5, 6e-5]]])  # (element, ply, exz and eyz)
    strains, places = [], []
    for e in range(2):
        point = 0
        for h, z in enumerate(heights):
            for p in range(4):
                point += 1
                exx, eyy, exy = middle[e] + slope[e] * z * 1e-3 + spread[p]
                exz, eyz = ply_shear[e, h // 2] + (1e-5 if p % 2 else -1e-5)
                strains.append([e + 1, point, exx, eyy, 0.0, exy, exz, eyz])
                places.append([e + 1, point, 10.0 * p, 5.0, z])
    order = np.random.default_rng(3).permutation(len(strains))  # the reduction does not lean on the order of the rows
    strain0, curvature, shear, fit = through_the_height(np.array(strains)[order], np.array(places), 2, thickness, 1e-3)
    assert strain0 == pytest.approx(middle * [1, 1, 2], rel=1e-9) and curvature == pytest.approx(slope * [1, 1, 2], rel=1e-9)  # the shear as gamma
    assert shear == pytest.approx(2.0 * ply_shear, rel=1e-9) and fit < 1e-9
    bent = np.array(strains)
    bent[bent[:, 1] > 12, 2] += 5e-4  # the top ply's upper points leave the line
    assert through_the_height(bent, np.array(places), 2, thickness, 1e-3)[3] > 0.02
    with pytest.raises(FollowedError, match="strain rows"):
        through_the_height(np.array(strains)[:-1], np.array(places), 2, thickness, 1e-3)
    with pytest.raises(FollowedError, match="do not name the same points"):
        through_the_height(np.array(strains), np.array(places)[:, [0, 1, 2, 3, 4]] + [0, 1, 0, 0, 0], 2, thickness, 1e-3)


def test_the_eight_node_elements_derivatives_give_a_planes_slope_at_every_corner():
    nodes = np.array([(-1, -1), (1, -1), (1, 1), (-1, 1), (0, -1), (1, 0), (0, 1), (-1, 0)], dtype=float)
    for xi, eta in ((-1.0, -1.0), (1.0, 1.0), (0.3, -0.7)):
        d = serendipity_derivatives(xi, eta)
        assert d.sum(axis=1) == pytest.approx([0.0, 0.0], abs=1e-12)  # a constant has no slope
        assert d @ nodes == pytest.approx(np.eye(2), abs=1e-12)  # xi and eta are their own coordinates
        curved = nodes[:, 0] ** 2 * nodes[:, 1]  # xi^2 eta is in the element's space
        assert d @ curved == pytest.approx([2 * xi * eta, xi * xi], abs=1e-12)


def test_the_load_put_straight_onto_held_nodes_is_the_share_of_the_edge_elements(tmp_path):
    """A clamped plate of 4 by 4 eight-node elements under a pressure: 28 element corners and 16 midside nodes lie on the held edges, so
    28 x (-1/12) + 16 x (1/3) = 3 element areas of the 16 go straight onto held nodes, 0.1875 of the load, and no reaction CalculiX
    prints holds it."""
    spec = spec_of(tmp_path, element_size=50, **{FOLLOWED_KEY: True})
    frame = frame_of(spec)
    direct = loads_on_held_nodes(frame.twin)
    whole = -0.03e6 * 0.2 * 0.2  # N: the pressure presses down
    assert direct[:, 2].sum() == pytest.approx(0.1875 * whole, rel=1e-12) and not direct[:, :2].any()
    inside = np.all((frame.twin.mesh.xy > 1e-9) & (frame.twin.mesh.xy < 0.2 - 1e-9), axis=1)
    assert not direct[inside].any()
    assert frame.mesh.element_count == 16 and frame.between.shape == (40, 3) and frame.ply_shear.shape == (8, 2, 2)
    # the slopes of a plane w = a x + b y at every corner node: theta_x = dw/dy, theta_y = -dw/dx
    xy = frame.twin.mesh.xy
    assert midplane_slopes(frame, 0.02 * xy[:, 0] - 0.05 * xy[:, 1]) == pytest.approx(np.tile([-0.05, -0.02], (25, 1)), abs=1e-12)


def test_where_a_rising_failure_index_reaches_one():
    assert crossing([0.5, 1.0], [0.2, 0.6]) is None
    assert crossing([0.5, 1.0], [0.5, 1.5]) == pytest.approx((0.75, 0.5, 1.0))
    assert crossing([0.1, 0.2], [2.0, 5.0]) == pytest.approx((0.05, 0.0, 0.1))  # before the first level: from nothing at no load
    assert crossing([0.5, 1.0], [0.4, 1.0]) == pytest.approx((1.0, 0.5, 1.0))


# --- CalculiX follows the plate and our composite layer reads it ---------------------------------------


@pytest.fixture(scope="module")
def solved(tmp_path_factory):
    """The clamped laminate plate under its pressure on the coarse mesh, followed once for the tests below."""
    folder = tmp_path_factory.mktemp("followed")
    return follow_plate(spec_of(folder, **COARSE, **{FOLLOWED_KEY: True}), folder / "run")


@needs_ccx
def test_under_a_small_load_the_followed_plate_is_our_kernels_linear_plate(tmp_path):
    """An unsymmetric laminate, so that bending and stretching are coupled, under a thousandth of the load: what our composite layer
    reads from CalculiX's strains is what our own shell solves, the displacement, the curvature, the moments and the membrane forces."""
    spec = under(spec_of(tmp_path, angles=[0, 45, 90, -45], symmetric="no", element_size=12.5, **{FOLLOWED_KEY: True}), 0.001)
    followed = follow_plate(spec, tmp_path / "run")
    assert [level.fraction for level in followed.levels] == pytest.approx(LEVELS)
    read = shell_solution(followed.frame, followed.levels[-1])
    ours = solve_deck(followed.frame.deck)
    largest = lambda field: np.abs(field).max()  # noqa: E731
    assert largest(read.displacement[:, 2] - ours.displacement[:, 2]) < 0.02 * largest(ours.displacement[:, 2])
    assert largest(read.displacement[:, 3:] - ours.displacement[:, 3:]) < 0.06 * largest(ours.displacement[:, 3:])  # the slopes against our rotations
    for name, within in (("curvature", 0.05), ("moment", 0.04), ("section_force", 0.12)):  # the largest difference anywhere, 256 elements
        assert largest(getattr(read, name) - getattr(ours, name)) < within * largest(getattr(ours, name)), name
    whole = 0.03e6 * 0.001 * 0.2 * 0.2  # N: the supports push up against the pressure
    assert read.reaction[:, 2].sum() == pytest.approx(whole, rel=1e-4) and ours.reaction[:, 2].sum() == pytest.approx(whole, rel=1e-6)
    assert max(level.fit for level in followed.levels) < 1e-3  # the strain is straight in the height


def test_a_linear_plate_says_how_far_it_leaves_its_plane_against_its_thickness(tmp_path):
    """What says whether the shape is worth following: the largest displacement out of the plane over the laminate's thickness, in every
    plate's summary; past about half, the linear result's own sentences name the switch. No solver but ours is needed for it."""
    coupon = {"designation": "plate", "test": "plate", "layup": "[45/0/-45/90]s"}
    for share, past in ((1.0, True), (0.1, False)):  # the linear deflection is 2.5 thicknesses under the pressure, a quarter under a tenth of it
        frame = frame_of(under(spec_of(tmp_path / str(share), **COARSE, **{FOLLOWED_KEY: True}), share))
        data = field_data(frame.deck, solve_deck(frame.deck), frame.units, coupon=coupon)
        told = data["summary"]["deflection"]
        assert told["thickness"] == pytest.approx(8 * 0.18288) and told["value"] == pytest.approx(abs(data["summary"]["max_displacement"]["components"][2]))
        assert told["ratio"] == pytest.approx(told["value"] / told["thickness"]) == pytest.approx(share * 2.483, rel=1e-3)
        assert told["past_linear"] is past is (told["ratio"] > FOLLOW_FROM)
        words = " ".join(explanation(data["summary"], data["coupon"], frame.units, data["labels"])["sentences"])
        assert ("That is 2.483 times the plate's thickness of 1.463 mm." in words) is past
        assert ("nonlinear geometry, in the Analysis step, follows the shape" in words) is past


@needs_ccx
def test_the_supports_carry_the_load_applied_at_every_level_and_the_plate_stiffens(solved):
    whole = 0.03e6 * 0.2 * 0.2  # N: the supports push up against the pressure
    assert [level.fraction for level in solved.levels] == pytest.approx(LEVELS) and solved.version and solved.deck_path.name == "followed.inp"
    for level in solved.levels:
        carried = shell_solution(solved.frame, level).reaction[:, 2].sum()
        assert carried == pytest.approx(level.fraction * whole, rel=2e-3)
        printed = level.reaction[:, 2].sum()  # what CalculiX prints leaves out the load on the held nodes themselves
        assert abs(printed) < abs(level.fraction * whole) * 0.99
    centre = [abs(level.displacement[:, 2]).max() for level in solved.levels]
    steps = np.diff([0.0, *centre])
    assert np.all(steps > 0) and np.all(np.diff(steps) < 0)  # every tenth of the load moves it less than the one before
    membrane = [np.abs(shell_solution(solved.frame, level).section_force).max() for level in solved.levels]
    assert membrane[-1] > 50 * membrane[0] / 10  # the stretch of the middle grows with the square of the deflection, not with the load


@needs_ccx
def test_the_fields_of_a_followed_plate_say_what_only_a_followed_solve_has(solved, tmp_path):
    data = followed_fields(solved)
    summary = data["summary"]
    told = summary["followed"]
    assert data["solver"] == "calculix-followed" and told["solver"].startswith("CalculiX 2.") and told["fractions"] == pytest.approx(LEVELS)
    curve = told["curve"]
    assert curve["axis"] == "z" and curve["unit"] == "mm" and len(curve["values"]) == len(curve["linear"]) == 10
    assert curve["values"][-1] == pytest.approx(summary["max_displacement"]["components"][2], rel=1e-9)
    assert curve["linear"][-1] == pytest.approx(told["linear"]["value"]) and curve["linear"][0] == pytest.approx(0.1 * told["linear"]["value"])
    assert 0.3 < told["linear"]["ratio"] < 0.7 and abs(curve["values"][0]) < abs(curve["linear"][0])  # a plate held all round stiffens as it bends
    assert told["reaction"] == pytest.approx([f * told["reaction"][-1] for f in LEVELS], rel=2e-3) and abs(told["reaction"][-1]) == pytest.approx(1200.0, rel=2e-3)
    assert set(told["index"]) == set(summary["fpf"]) and all(len(values) == 10 for values in told["index"].values())
    for criterion, entry in summary["fpf"].items():
        assert entry["at_failure"] is None and entry["factor"] > 1.0  # no ply reaches its limit: nothing is said of a load at failure
        assert told["index"][criterion][-1] == pytest.approx(1.0 / entry["factor"], rel=1e-9)
        assert np.all(np.diff(told["index"][criterion]) > 0)
    for worked in summary["working"]["criteria"].values():
        assert worked["steps"] and all(step["id"] != "loading" for step in worked["steps"])  # R times the loads is not where a followed plate fails
    assert run_answer(summary)["followed"] is True
    assert summary["deflection"]["value"] == pytest.approx(abs(curve["values"][-1])) and summary["deflection"]["past_linear"] is True
    words = " ".join(explanation(summary, data["coupon"], solved.frame.units, data["labels"])["sentences"])
    assert "times the plate's thickness" not in words  # the followed result needs no pointer to the switch that made it
    assert "(nonlinear geometry), in 10 levels of the load, by the reference solver alone" in words and "following the shape makes it" in words
    assert "% smaller" in words and "times the applied" not in words and "calculix" not in words.lower()  # the page shows these sentences
    written = write_followed(solved, tmp_path, "plate")
    assert json.loads(written["fields"].read_text(encoding="utf-8"))["summary"]["followed"]["fractions"] == told["fractions"]
    assert json.loads(written["explanation"].read_text(encoding="utf-8"))["sentences"]


@needs_ccx
def test_a_ply_that_reaches_its_limit_on_the_way_is_placed_between_two_levels(tmp_path):
    followed = follow_plate(spec_of(tmp_path, loads=[{"region": "Face", "pressure": 1.5}], **COARSE, **{FOLLOWED_KEY: True}), tmp_path / "run")
    data = followed_fields(followed)
    summary = data["summary"]
    criterion = summary["verdict"]["earliest"]
    index = summary["followed"]["index"][criterion]
    at = summary["fpf"][criterion]["at_failure"]
    assert index[0] < 1.0 < index[-1] and summary["fpf"][criterion]["factor"] < 1.0
    low, high = at["between"]
    assert low < at["fraction"] < high and high - low == pytest.approx(0.1) and index[LEVELS.index(high)] >= 1.0 > index[LEVELS.index(high) - 1]
    assert at["applied"] == pytest.approx(at["fraction"] * summary["applied"]["value"]) and at["every_load"] is True
    assert abs(at["reaction"]) == pytest.approx(at["fraction"] * 1.5 * 200 * 200, rel=5e-3)
    assert at["fraction"] != pytest.approx(summary["fpf"][criterion]["factor"], rel=0.02)  # not the linear rule's R times the load
    assert all(entry["at_failure"] is None for entry in summary["fpf_gauge"].values())
    words = " ".join(explanation(summary, data["coupon"], followed.frame.units, data["labels"])["sentences"])
    assert f"at about {at['fraction'] * 100:.4g} % of the applied loading (between the levels at {low * 100:.0f} % and {high * 100:.0f} %)" in words
    assert "fails before the applied loading is reached" in words and "No ply damage is modelled" in words


@needs_ccx
def test_the_published_plate_of_step_1_is_the_same_plate_through_the_whole_plate_reading(tmp_path):
    """NACA Report 740's clamped square plate (`fea/checks/large_displacement_cases/`): the centre deflection at the last pressure of
    the table, read from every node's displacement, and the reaction with the load on the held nodes."""
    case = load_case(next(path for path in paths.LARGE_CASES.glob("*.toml") if "naca" in path.name))
    followed = follow_plate(case.spec.model_copy(update={"analysis": Analysis(large_displacement=True)}), tmp_path)
    reading = case.readings[0]
    last = followed.levels[-1]
    centre = int(np.argmin(np.linalg.norm(followed.frame.twin.mesh.xy - 0.1, axis=1)))
    assert abs(last.displacement[centre, 2]) / 0.002 == pytest.approx(reading.values[-1], rel=reading.tolerance)
    whole = case.spec.loads[0].pressure * 0.2 * 0.2
    assert shell_solution(followed.frame, last).reaction[:, 2].sum() == pytest.approx(whole, rel=1e-3)
    data = followed_fields(followed)  # an isotropic plate: no criterion, the curve and the linear answer all the same
    assert data["summary"]["fpf"] == {} and 0.3 < data["summary"]["followed"]["linear"]["ratio"] < 0.4


# --- a solve that stops ---------------------------------------------------------------------------------


@needs_ccx
def test_a_solve_stopped_before_its_first_level_says_so(tmp_path):
    with pytest.raises(Stopped, match="stopped before its first level, a tenth of the load") as stopped:
        follow_plate(spec_of(tmp_path, **{FOLLOWED_KEY: True}), tmp_path / "run", timeout_s=0.2)
    assert stopped.value.reached == 0.0 and "it ran past 0.2 s" in str(stopped.value) and "CalculiX" in stopped.value.detail
    assert "calculix" not in str(stopped.value).lower()  # the page shows the message; the program's own words go to the log


@needs_ccx
def test_a_solve_that_stops_on_the_way_says_how_far_it_came(solved, tmp_path, monkeypatch):
    """What CalculiX had printed when it stopped is read: the levels that are whole. The file of the solved plate is cut inside its
    sixth level, as a run that no longer finds a balance of forces, or is stopped by the clock, leaves it."""
    text = (solved.deck_path.parent / "followed.dat").read_text(encoding="utf-8")
    cut = text.index("for set", text.index("and time  0.6000000E+00")) + 4000
    partial = tmp_path / "run" / "followed.dat"
    partial.parent.mkdir()
    partial.write_text(text[:cut], encoding="utf-8")
    assert [level.fraction for level in read_plate(solved.frame.twin, partial)] == pytest.approx(LEVELS[:5])

    def stopped(reason):
        def run(deck, **_):
            raise CalculixError(reason)
        monkeypatch.setattr(followed_plate, "run_calculix", run)
        with pytest.raises(Stopped) as caught:
            follow_plate(solved.frame.spec, partial.parent)
        return caught.value

    diverged = stopped("followed.inp: CalculiX ended with an error: *ERROR: too many cutbacks")
    assert diverged.reached == 0.5 and "reached 50 % of the load and stopped there, the largest displacement" in str(diverged)
    assert re.search(r"largest displacement \d\.\d+ mm: no balance of forces was found past it", str(diverged)) and "a smaller load runs to its end" in str(diverged)
    late = stopped("followed.inp: CalculiX did not finish in 480 s")
    assert late.reached == 0.5 and "it ran past 480 s; a coarser mesh follows the whole load" in str(late)
    assert "too many cutbacks" in diverged.detail and "calculix" not in (str(diverged) + str(late)).lower()
    partial.unlink()
    nothing = stopped("followed.inp: CalculiX ended with an error: *ERROR: nonpositive jacobian")
    assert nothing.reached == 0.0 and "stopped before its first level, a tenth of the load: no balance of forces was found" in str(nothing)


# --- the file for another program states the same step (ADR-0129, ADR-0142) -----------------------------


def test_a_downloaded_model_of_a_followed_plate_has_nonlinear_geometry_on_and_the_kernels_deck_never(tmp_path):
    from anisotropy_fea.abaqus_reader import DeckError, parse_deck
    from anisotropy_fea.write_abaqus import FOLLOWED_NOTE, write_abaqus, write_abaqus_download
    from anisotropy_fea.write_ansys import write_ansys

    on = build_model(spec_of(tmp_path / "on", **COARSE, **{FOLLOWED_KEY: True}))
    off = build_model(spec_of(tmp_path / "off", **COARSE))
    deck = write_abaqus_download(on)
    assert "*Step, name=Step-1, nlgeom=YES, inc=200\n*Static\n0.1, 1., 1e-06, 0.1\n" in deck and "nlgeom=NO" not in deck
    assert "** " + FOLLOWED_NOTE[:60] in deck and deck.index("File > Import > Model") < deck.index("nlgeom=YES") < deck.index("*Dload")
    linear = write_abaqus_download(off)
    assert "*Step, name=Step-1, nlgeom=NO\n*Static\n1., 1., 1e-05, 1.\n" in linear and "nlgeom=YES" not in linear
    # nothing else of the file changes with the switch: the note, the step's three lines and the heading's own words on the coupon
    body = lambda text: [line for line in text.splitlines() if not line.startswith("**") and "nlgeom" not in line.lower()]  # noqa: E731
    assert [line for line in body(deck) if line != "0.1, 1., 1e-06, 0.1"] == [line for line in body(linear) if line != "1., 1., 1e-05, 1."]
    # the deck our kernel reads of the same plate stays linear, and the reader still refuses a followed step: the kernel is linear
    assert "nlgeom=NO" in write_abaqus(on) and "nlgeom=YES" not in write_abaqus(on)
    with pytest.raises(DeckError, match="nlgeom=YES"):
        parse_deck(deck)
    apdl = write_ansys(on)
    assert "\n/SOLU\nANTYPE,STATIC\nNLGEOM,ON\nAUTOTS,ON\nNSUBST,10,200,10\nKBC,0\nOUTRES,ALL,ALL\nSOLVE\nFINISH\n" in apdl and "NLGEOM,OFF" not in apdl
    assert "follows the plate's shape as the load rises" in apdl and apdl.isascii()
    plain = write_ansys(off)
    assert "\n/SOLU\nANTYPE,STATIC\nNLGEOM,OFF\nOUTRES,ALL,ALL\nSOLVE\nFINISH\n" in plain and "NSUBST" not in plain and "linear static load step" in plain


def test_the_file_for_another_program_is_written_for_a_plate_our_own_followed_solve_does_not_take(tmp_path):
    """A mesh too fine, or more plies than the solver that follows the shape takes here: the setup check stops a run and names the
    row, and the file for Abaqus or Ansys is still written, with nonlinear geometry on, for the engineer's own machine."""
    for changes in ({"element_size": 2}, {"angles": [0, 45, -45, 90, 0, 45, -45], "symmetric": "yes", **COARSE}):
        form = read_values(values_file(tmp_path / str(len(changes)), **{FOLLOWED_KEY: True}, **changes))
        ours = setup_checklist(form, tmp_path / "none", **TOOLS)[0]
        assert ours.state == "blocked" and any(FOLLOWED_LABEL in problem for problem in ours.problems)
        theirs, model, _ = setup_checklist(form, tmp_path / "none", element_limit=None, **TOOLS)
        assert theirs.state == "ready" and model is not None and follows_shape(model.spec)
