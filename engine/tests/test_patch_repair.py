"""A stepped patch repair from its description (ADR-0131, and its amendment 1 for a patch bonded on top): every case in validation/patch_repair_cases against the engine, its
expected numbers against the closed form worked without the engine in validation/closed_forms.py (ADR-0007, ADR-0042), the
slice's rectangles against the level-by-level rule and against sums written out here, and what the description refuses."""

import importlib.util
import itertools
import math
import tomllib
from pathlib import Path

import numpy as np
import pytest

from anisotropy_engine.lamina import Lamina
from anisotropy_engine.laminate import Ply, abd_matrices
from anisotropy_engine.repair import (
    Adhesive, Repair, RepairError, RepairMaterial, Step, areas, bond_lengths, check_regions, lap_steps, region_at, regions, repair_from_dict,
    repair_lap, repair_report, shared_stiffnesses, step_lap, stretching_matrix, volumes,
)
from anisotropy_engine.units import UNIT_SYSTEMS

ENGINE = Path(__file__).parents[1]
VALIDATION = ENGINE / "validation"
CASES = sorted((VALIDATION / "patch_repair_cases").glob("*.toml"))
# A real repair of the team's or a course's, with its answers, stays outside the repository (ADR-0042): same format, run when present.
LOCAL = sorted((ENGINE.parent / ".local" / "repair" / "patch-cases").glob("*.toml"))
EXAMPLE = ENGINE / "examples" / "example-patch-repair.toml"
WITH_COVER = VALIDATION / "patch_repair_cases" / "constructed-cross-ply-patch-with-a-cover-ply.toml"

PLY = RepairMaterial("Test ply", Lamina(E1=150e9, E2=9e9, G12=5e9, nu12=0.3), 0.15e-3)
FILM = Adhesive(shear_modulus_pa=900e6, thickness_m=0.1e-3, shear_strength_pa=30e6)
QUASI = (45, 0, -45, 90, 90, -45, 0, 45)


def repair(**changes) -> Repair:
    """Four steps of one ply into an eight-ply laminate, 25 mm of damage, 12 mm steps, in a 400 mm by 300 mm panel."""
    values = dict(parent_material=PLY, parent_angles=QUASI, damage_diameter_m=25e-3, steps=4, step_length_m=12e-3, adhesive=FILM,
                  panel_length_m=0.4, panel_width_m=0.3)
    return Repair(**{**values, **changes})


FAMILY = {
    "four steps": {},
    "four steps and a cover ply": dict(cover_angles=(45,), cover_overlap_m=10e-3),
    "eight steps through, two cover plies": dict(steps=8, cover_angles=(45, -45), cover_overlap_m=10e-3),
    "eight steps through": dict(steps=8),
    "two steps of two plies": dict(steps=2, plies_per_step=2),
    "four steps of two plies, through": dict(steps=4, plies_per_step=2),
    "one step through under cover plies": dict(steps=1, plies_per_step=8, cover_angles=(0, 90), cover_overlap_m=20e-3),
    "one step of one ply": dict(steps=1),
    "a patch of other angles": dict(steps=3, patch_angles=(0, 0, 45)),
}


def closed_forms():
    spec = importlib.util.spec_from_file_location("closed_forms", VALIDATION / "closed_forms.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def flat(value) -> list[float]:
    return [float(v) for v in np.ravel(value)]


def answers(case: dict) -> dict:
    """What the engine says of a case, under the keys an `[expected]` table uses."""
    made, load_ = repair_from_dict({key: value for key, value in case.items() if key != "expected"})
    report = repair_report(made, case["units"], load_)
    lap = report["lap"]
    kinds = ("parent", "adhesive", "patch", "cover")
    bond = report["bond_lengths"]
    got = {
        "cut_radii": report["sizes"]["cut_radii"],
        "areas": [report["areas"][kind] for kind in kinds],
        "volumes": [report["volumes"][kind] for kind in kinds],
        "bond_on_laminate": [sum(value for name, value in bond.items() if name != "cut_faces"), report["sizes"]["depth"]],
        "step_stiffnesses": [[step["patch_modulus"] * step["patch_thickness"], step["laminate_modulus"] * step["laminate_thickness"]]
                             for step in lap["steps"]],
    }
    if "answer" in lap:
        got.update({key: lap["answer"][key] for key in ("boundary_forces", "shear_at_ends", "elastic_limit_load") if key in lap["answer"]})
        got["peak_shear"] = lap["answer"]["peak_shear"]["value"]
    return got


# ------------------------------------------------------------------------------------------------- the cases

def test_there_are_cases_and_each_has_its_closed_form():
    assert len(CASES) >= 4 and sum(load(path).get("kind") == "external" for path in CASES) >= 2
    assert {path.stem for path in CASES} == set(closed_forms().PATCH_REPAIR_CASES)


@pytest.mark.parametrize("path", CASES, ids=[path.stem for path in CASES])
def test_every_expected_value_is_the_closed_form(path):
    case = load(path)
    reference = closed_forms().PATCH_REPAIR_CASES[path.stem](case)
    expected = {key: value for key, value in case["expected"].items() if key != "tolerance"}
    assert set(expected) == set(reference)
    for key, value in expected.items():
        assert flat(value) == pytest.approx(flat(reference[key]), rel=1e-9, abs=1e-12), f"{path.stem}: {key}"


@pytest.mark.parametrize("path", CASES + LOCAL, ids=[path.stem for path in CASES + LOCAL])
def test_the_engine_reproduces_the_case(path):
    case = load(path)
    for field in ("title", "source", "units"):
        assert field in case
    got = answers(case)
    tolerance = case["expected"]["tolerance"]
    count = 0
    for key, value in case["expected"].items():
        if key == "tolerance":
            continue
        assert flat(got[key]) == pytest.approx(flat(value), rel=tolerance, abs=1e-9), f"{path.stem}: {key}"
        count += len(flat(value))
    assert count >= (2 if path in LOCAL else 20)


# ------------------------------------------------------------------------------------------------- the description

def test_steps_are_counted_from_the_top_and_the_deepest_has_the_damages_diameter():
    made = repair()
    assert [made.cut_radius_m(step) for step in (1, 2, 3, 4)] == pytest.approx([48.5e-3, 36.5e-3, 24.5e-3, 12.5e-3])
    assert made.patch_radius_m == pytest.approx(48.5e-3) and made.cover_radius_m == made.patch_radius_m
    assert made.thickness_m == pytest.approx(1.2e-3) and made.depth_m == pytest.approx(0.6e-3) and not made.through
    assert [made.parent_ply_step(ply) for ply in range(1, 9)] == [None, None, None, None, 4, 3, 2, 1]
    # unless said, the patch is the laminate's own material in the angles of the plies removed, deepest first
    assert made.patch_material is PLY and made.patch_angles == (90.0, -45.0, 0.0, 45.0)
    assert [made.patch_group(step) for step in (1, 4)] == [(45.0,), (90.0,)]
    pairs = repair(steps=2, plies_per_step=2)
    assert pairs.patch_group(1) == (0.0, 45.0) and pairs.patch_group(2) == (90.0, -45.0)
    assert [pairs.parent_ply_step(ply) for ply in (4, 5, 6, 7, 8)] == [None, 2, 2, 1, 1]
    assert repair(steps=8).through and repair(steps=4, plies_per_step=2).through


@pytest.mark.parametrize("changes, words", [
    (dict(steps=9), "remove 9 plies, and the laminate has 8"),
    (dict(steps=0), "The number of steps must be a whole number"),
    (dict(steps=2.0), "The number of steps must be a whole number"),
    (dict(parent_angles=()), "at least one ply"),
    (dict(parent_angles=(0, 120)), "from -90 to 90 degrees"),
    (dict(parent_angles="0/90"), "must be a list of ply angles"),
    (dict(damage_diameter_m=0), "The damage's diameter must be a positive"),
    (dict(step_length_m=float("nan")), "The step length must be a positive"),
    (dict(patch_angles=(0, 90)), "The patch needs 4 plies"),
    (dict(patch_material=RepairMaterial("Thicker ply", PLY.lamina, 0.2e-3)), "must be as thick as the laminate's"),
    (dict(cover_overlap_m=5e-3), "no cover ply is listed"),
    (dict(cover_angles=(45,)), "The cover plies' overlap must be a positive"),
    (dict(adhesive=Adhesive(900e6, 0.15e-3)), "must be thinner than the plies of one step"),
    (dict(steps=1, plies_per_step=8), "leaves no ledge to bond to"),
    (dict(panel_width_m=0.09), "so the panel must be longer and wider"),
    (dict(adhesive=None), "needs its adhesive"),
    (dict(parent_material=None), "needs its ply material"),
])
def test_what_is_not_a_repair_is_refused_in_words(changes, words):
    with pytest.raises(RepairError, match=words):
        repair(**changes)


def test_the_bondline_must_fit_in_a_step_and_in_the_damage():
    thick = RepairMaterial("Thick ply", PLY.lamina, 0.5e-3)
    with pytest.raises(RepairError, match="thinner than a step is long"):
        repair(parent_material=thick, step_length_m=0.3e-3, adhesive=Adhesive(900e6, 0.4e-3))
    with pytest.raises(RepairError, match="thinner than a step is long"):
        repair(parent_material=thick, damage_diameter_m=0.6e-3, adhesive=Adhesive(900e6, 0.4e-3))


# ------------------------------------------------------------------------------------------------- the slice

@pytest.mark.parametrize("name", FAMILY)
def test_the_rectangles_do_not_overlap_and_agree_with_the_level_by_level_rule(name):
    made = repair(**FAMILY[name])
    parts = regions(made)
    for a, b in itertools.combinations(parts, 2):
        assert not (min(a.r1, b.r1) - max(a.r0, b.r0) > 1e-12 and min(a.z1, b.z1) - max(a.z0, b.z0) > 1e-12), f"{a.name} overlaps {b.name}"
    check_regions(made)
    for part in parts:
        assert part.r1 > part.r0 >= 0 and part.z1 > part.z0 >= 0
    assert [part.name for part in parts if part.kind == "parent"] == [f"Laminate ply {k} ({angle:g}°)" for k, angle in enumerate(QUASI, 1)]
    assert len([part for part in parts if part.kind == "patch"]) == made.plies_removed
    # and the other way about: a grid of points over the whole slice, each one in a rectangle of the kind its level gives, or in none
    edge, top = made.panel_length_m / 2, made.thickness_m + FILM.thickness_m + made.cover_thickness_m
    for r in np.linspace(0, edge, 173)[1:-1]:
        for z in np.linspace(0, top * 1.05, 61)[1:-1]:
            holders = [part.kind for part in parts if part.r0 < r < part.r1 and part.z0 < z < part.z1]
            on_an_edge = any(min(abs(r - part.r0), abs(r - part.r1)) < 1e-9 or min(abs(z - part.z0), abs(z - part.z1)) < 1e-9 for part in parts)
            if not on_an_edge:
                assert holders == ([region_at(made, r, z)] if region_at(made, r, z) else []), f"r = {r}, z = {z}"


@pytest.mark.parametrize("name", FAMILY)
def test_the_areas_and_volumes_are_the_sums_written_out_from_the_description(name):
    made = repair(**FAMILY[name])
    eta, g, t, h = FILM.thickness_m, made.group_thickness_m, made.ply_thickness_m, made.thickness_m
    radius = [made.damage_diameter_m / 2 + (made.steps - j) * made.step_length_m for j in range(1, made.steps + 1)]
    reach = radius[0] + made.cover_overlap_m
    cover = len(made.cover_angles)
    cavity, patch = sum(r * g for r in radius), sum((r - eta) * g for r in radius)
    proud = eta * (radius[0] - eta)  # the patch stands one bondline above the top face
    above = eta * (reach - radius[0] + eta) if cover else 0.0
    empty = eta * (radius[-1] - eta) if made.through else 0.0
    got = areas(made)
    assert got["parent"] == pytest.approx(made.panel_length_m / 2 * h - cavity, rel=1e-12)
    assert got["patch"] == pytest.approx(patch, rel=1e-12)
    assert got["adhesive"] == pytest.approx(cavity + proud + above - patch - empty, rel=1e-10)
    assert got["cover"] == pytest.approx(reach * cover * t, abs=1e-18)
    disc = lambda r, height: math.pi * r**2 * height  # noqa: E731
    swept = volumes(made)
    assert swept["parent"] == pytest.approx(made.panel_length_m * made.panel_width_m * h - sum(disc(r, g) for r in radius), rel=1e-12)
    assert swept["patch"] == pytest.approx(sum(disc(r - eta, g) for r in radius), rel=1e-12)
    assert swept["cover"] == pytest.approx(disc(reach, cover * t), abs=1e-18)
    expected = (sum(disc(r, g) for r in radius) + disc(radius[0] - eta, eta) - swept["patch"]
                + ((disc(reach, eta) - disc(radius[0] - eta, eta)) if cover else 0.0) - (disc(radius[-1] - eta, eta) if made.through else 0.0))
    assert swept["adhesive"] == pytest.approx(expected, rel=1e-10)
    bond = bond_lengths(made)
    assert bond["ledges"] == pytest.approx((made.steps - 1) * made.step_length_m)
    assert bond["floor"] == (0.0 if made.through else pytest.approx(radius[-1]))
    assert bond["cover"] == pytest.approx(made.cover_overlap_m)
    faces = [part for part in regions(made) if part.name.startswith("Adhesive on the cut face")]
    assert bond["cut_faces"] == pytest.approx(sum(part.z1 - part.z0 for part in faces), rel=1e-12) and len(faces) == made.steps


def test_the_patch_stands_one_bondline_proud_and_a_through_cut_leaves_one_empty_under_it():
    made = repair(steps=8)
    eta, h = FILM.thickness_m, made.thickness_m
    assert region_at(made, 5e-3, h + eta / 2) == "patch" and region_at(made, 5e-3, h + 1.5 * eta) is None
    assert region_at(made, 5e-3, eta / 2) is None and region_at(made, 5e-3, 1.5 * eta) == "patch"
    assert region_at(made, made.cut_radius_m(8) - eta / 2, eta / 2) == "adhesive"  # the cut face's adhesive runs to the bottom face
    partial = repair()
    floor = h - partial.depth_m
    assert region_at(partial, 5e-3, floor + eta / 2) == "adhesive" and region_at(partial, 5e-3, floor - eta / 2) == "parent"
    assert region_at(partial, 0.3, 1e-4) is None and region_at(partial, 5e-3, -1e-6) is None  # outside the half slice


# ------------------------------------------------------------------------------------------------- the lap

def test_two_bonded_stacks_share_the_sections_stiffness():
    """Each stack's E t is its share of the bonded section's: the two add up to 1 / a11 of the section, and the shares are
    the forces the stacks carry when the section is strained by a load along x (worked here from the plies themselves)."""
    over, under = (45.0, 0.0), (45.0, 0.0, -45.0, 90.0, 90.0, -45.0)
    outer, inner = stretching_matrix(PLY, over), stretching_matrix(PLY, under)
    so, si = shared_stiffnesses(outer, inner)
    stack = [Ply(material=PLY.lamina, angle_deg=angle, thickness_m=PLY.ply_thickness_m) for angle in under + over]
    whole, _, _ = abd_matrices(stack)
    strain = np.linalg.solve(whole, [1.0, 0.0, 0.0])  # per unit load along x, free to contract and to shear
    assert so + si == pytest.approx(1 / strain[0], rel=1e-12)
    assert so * strain[0] == pytest.approx((outer @ strain)[0], rel=1e-12) and si * strain[0] == pytest.approx((inner @ strain)[0], rel=1e-12)
    # plies all at 0 degrees share by thickness, each at the ply's own modulus
    zeros = shared_stiffnesses(stretching_matrix(PLY, (0, 0)), stretching_matrix(PLY, (0, 0, 0)))
    assert zeros == pytest.approx((150e9 * 0.3e-3, 150e9 * 0.45e-3), rel=1e-12)
    with pytest.raises(RepairError, match="at least one ply"):
        stretching_matrix(PLY, ())


def test_a_patch_in_the_laminates_own_angles_restores_the_laminates_stiffness_on_every_ledge():
    made = repair()
    steps, names, continues = lap_steps(made)
    assert names == ["Ledge of step 1", "Ledge of step 2", "Ledge of step 3", "Floor"] and continues
    assert [step.length_m for step in steps] == pytest.approx([12e-3, 12e-3, 12e-3, 12.5e-3])
    laminate, _, _ = abd_matrices([Ply(material=PLY.lamina, angle_deg=angle, thickness_m=PLY.ply_thickness_m) for angle in QUASI])
    whole = 1 / np.linalg.inv(laminate)[0, 0]
    for k, step in enumerate(steps, 1):
        assert step.outer_thickness_m == pytest.approx(k * 0.15e-3) and step.inner_thickness_m == pytest.approx((8 - k) * 0.15e-3)
        assert step.outer_modulus_pa * step.outer_thickness_m + step.inner_modulus_pa * step.inner_thickness_m == pytest.approx(whole, rel=1e-12)
    covered, names, _ = lap_steps(repair(cover_angles=(45, -45), cover_overlap_m=10e-3))
    assert names[0] == "Cover overlap" and covered[0].length_m == pytest.approx(10e-3)
    assert covered[0].outer_thickness_m == pytest.approx(0.3e-3) and covered[0].inner_thickness_m == pytest.approx(1.2e-3)
    through, names, continues = lap_steps(repair(steps=8))
    assert names == [f"Ledge of step {k}" for k in range(1, 8)] and not continues
    assert through[-1].inner_thickness_m == pytest.approx(0.15e-3)  # one ply of the laminate is left under the last ledge


def test_a_lap_that_ends_at_a_plane_of_symmetry_has_no_shear_stress_there():
    """One step between uniform adherends, both crossing the plane of symmetry at its end: with P the force the outer one
    carries when the two strain alike, N(L) = P (1 - 1 / cosh(lam L)) and tau(0) = P lam tanh(lam L)."""
    step = Step(15e-3, 1.0e-3, 48e9, 2.0e-3, 55e9)
    load = 200e3
    lap = step_lap([step], FILM, load, inner_continues=True)
    so, si = 48e9 * 1.0e-3, 55e9 * 2.0e-3
    lam = math.sqrt(FILM.shear_modulus_pa / FILM.thickness_m * (1 / so + 1 / si))
    shared = load * so / (so + si)
    assert lap.forces[0] == 0 and lap.forces[1] == pytest.approx(shared * (1 - 1 / math.cosh(lam * 15e-3)), rel=1e-12)
    assert lap.shear_at_ends[0, 0] == pytest.approx(shared * lam * math.tanh(lam * 15e-3), rel=1e-12)
    assert lap.shear_at_ends[0, 1] == pytest.approx(0.0, abs=1e-6)
    # cutting the step in pieces changes nothing, and a long one hands the patch its whole share
    pieces = step_lap([Step(5e-3, 1.0e-3, 48e9, 2.0e-3, 55e9)] * 3, FILM, load, inner_continues=True)
    assert pieces.forces[-1] == pytest.approx(lap.forces[1], rel=1e-12) and pieces.shear_at_ends[0, 0] == pytest.approx(lap.shear_at_ends[0, 0], rel=1e-12)
    long = step_lap([Step(0.5, 1.0e-3, 48e9, 2.0e-3, 55e9)], FILM, load, inner_continues=True)
    assert long.forces[1] == pytest.approx(shared, rel=1e-9)
    # the patch never takes more than the load, and the laminate under it keeps the rest
    assert 0 < lap.forces[1] < shared < load


def test_the_repairs_lap_is_the_stepped_lap_of_its_steps():
    made = repair(cover_angles=(45,), cover_overlap_m=10e-3)
    steps, _, continues = lap_steps(made)
    lap, direct = repair_lap(made, 150e3), step_lap(steps, FILM, 150e3, inner_continues=continues)
    assert flat(lap.forces) == pytest.approx(flat(direct.forces), rel=1e-12)
    assert lap.shear_at_ends[-1, 1] == pytest.approx(0.0, abs=1e-6) and 0 < lap.forces[-1] < 150e3
    x, tau, force = lap.distribution(4001)
    assert np.trapezoid(tau, x) == pytest.approx(lap.forces[-1], rel=1e-6)  # the adhesive hands the patch what it carries at the middle
    through = repair_lap(repair(steps=8), 150e3)
    assert through.forces[-1] == pytest.approx(150e3, rel=1e-12)  # where the laminate ends the patch carries everything


# ------------------------------------------------------------------------------------------------- the file

def test_the_example_reads_and_reports_in_its_own_units():
    case = load(EXAMPLE)
    made, load_ = repair_from_dict(case)
    assert made.steps == 4 and made.cover_angles == (45.0,) and load_ == pytest.approx(100e3)
    assert made.parent_material.name == "IM7 / 8552" and made.patch_angles == (90.0, -45.0, 0.0, 45.0)
    report = repair_report(made, "mm-MPa", load_)
    assert report["sizes"]["cut_radii"] == pytest.approx([50.0, 37.5, 25.0, 12.5]) and report["sizes"]["repair_diameter"] == pytest.approx(125.0)
    assert report["sizes"]["plies_left"] == 4 and not report["sizes"]["through"]
    assert [step["name"] for step in report["lap"]["steps"]] == ["Cover overlap", "Ledge of step 1", "Ledge of step 2", "Ledge of step 3", "Floor"]
    assert len(report["regions"]) == len(regions(made)) == 22
    answer = report["lap"]["answer"]
    assert answer["boundary_forces"][0] == 0 and 0 < answer["boundary_forces"][-1] < 100.0
    assert answer["elastic_limit_load"] == pytest.approx(100.0 * 30.0 / answer["peak_shear"]["value"], rel=1e-12)
    # the same repair reported in inches and psi is the same repair
    us = repair_report(made, "psi", load_)
    inch, psi, lb_in = (UNIT_SYSTEMS["psi"][key][0] for key in ("length", "stress", "N"))
    assert us["sizes"]["patch_diameter"] * inch == pytest.approx(0.1) and us["areas"]["patch"] * inch**2 == pytest.approx(areas(made)["patch"])
    assert us["lap"]["answer"]["peak_shear"]["value"] * psi == pytest.approx(answer["peak_shear"]["value"] * 1e6, rel=1e-12)
    assert us["lap"]["answer"]["elastic_limit_load"] * lb_in == pytest.approx(answer["elastic_limit_load"] * 1e3, rel=1e-12)
    assert "answer" not in repair_report(made, "mm-MPa")["lap"]  # no load, no answer


def test_a_file_states_its_materials_by_the_library_or_in_full_and_a_patch_by_its_angles_alone():
    case = load(WITH_COVER)
    case.pop("expected")
    typed, _ = repair_from_dict(case)
    assert typed.parent_material.name == "Constructed ply" and typed.parent_material.ply_thickness_m == pytest.approx(0.2e-3)
    other = {**case, "patch": {"layup": [0, 0, 90]}}
    made = repair_from_dict(other)[0]
    assert made.patch_angles == (0.0, 0.0, 90.0) and made.patch_material is made.parent_material
    library = {**case, "parent": {"library": "im7-8552", "ply_thickness": 0.2, "layup": case["parent"]["layup"]},
               "patch": {"library": "im7-8552", "ply_thickness": 0.2}}
    made, _ = repair_from_dict(library)
    assert made.patch_material.name == "IM7 / 8552" and made.patch_angles == (0.0, 90.0, 0.0)
    assert "applied" not in case or repair_from_dict({key: value for key, value in case.items() if key != "applied"})[1] is None


@pytest.mark.parametrize("change, words", [
    (lambda case: case.update(units="cgs"), "units must be one of"),
    (lambda case: case.pop("damage"), r"needs \[damage\]"),
    (lambda case: case["steps"].pop("length"), r"\[steps\] is missing: length"),
    (lambda case: case["steps"].update(taper=3), r"\[steps\] has values a repair does not read: taper"),
    (lambda case: case.update(backing={"layup": [0]}), "tables it does not read: backing"),
    (lambda case: case["parent"].update(library="im7-8552"), r"\[parent\] has values a repair does not read"),
    (lambda case: case["parent"].pop("E2"), r"\[parent\] is missing: E2"),
    (lambda case: case["parent"].update(E1=-1.0), r"\[parent\]: the ply constants"),
    (lambda case: case.update(parent={"library": "no-such-ply", "layup": [0, 90]}), "unknown library material"),
    (lambda case: case["cover"].pop("overlap"), r"\[cover\] is missing: overlap"),
    (lambda case: case["adhesive"].update(thickness="thin"), "must be a number"),
    (lambda case: case["adhesive"].update(shear_modulus=0.0), r"\[adhesive\]: The adhesive's shear modulus"),
    (lambda case: case["steps"].update(count=7), "remove 7 plies"),
    (lambda case: case["applied"].update(moment=1.0), r"\[applied\] has values a repair does not read"),
])
def test_a_file_that_does_not_state_a_repair_is_refused_in_words(change, words):
    case = load(WITH_COVER)
    case.pop("expected")
    change(case)
    with pytest.raises(RepairError, match=words):
        repair_from_dict(case)
    with pytest.raises(RepairError, match="units must be one of"):
        repair_report(repair(), "cgs")


# ------------------------------------------------------------------------------------------------- a patch bonded on top

FABRIC = RepairMaterial("Test fabric", Lamina(E1=24e9, E2=24e9, G12=5e9, nu12=0.15), 0.22e-3)
STRIP_CASE = VALIDATION / "patch_repair_cases" / "constructed-external-strip-patch-of-another-material.toml"


def external(**changes) -> Repair:
    """Three steps of two fabric plies bonded on the eight-ply laminate over a 25 mm hole: 12 mm ledges, the shortest plies
    20 mm past the hole's edge, a strip across a panel 400 mm by 80 mm."""
    values = dict(parent_material=PLY, parent_angles=QUASI, damage_diameter_m=25e-3, steps=3, step_length_m=12e-3, adhesive=FILM,
                  panel_length_m=0.4, panel_width_m=0.08, plies_per_step=2, kind="external", patch_material=FABRIC,
                  patch_angles=(0, 45, 0, 45, 0, 0), patch_overlap_m=20e-3, patch_shape="strip")
    return Repair(**{**values, **changes})


EXTERNAL_FAMILY = {
    "a strip of three steps of two plies": {},
    "a round patch": dict(patch_shape="round", panel_width_m=0.3),
    "one step, a plain doubler": dict(steps=1, patch_angles=(0, 90)),
    "the laminate's own ply, one to a step": dict(patch_material=None, plies_per_step=1, steps=4, patch_angles=(0, 45, -45, 0)),
}


def test_an_external_patch_is_counted_from_the_laminate_up_and_cuts_no_step():
    made = external()
    assert [made.cut_radius_m(step) for step in (1, 2, 3)] == pytest.approx([56.5e-3, 44.5e-3, 32.5e-3])  # 12.5 + 20 + (3 - j) 12
    assert made.patch_radius_m == pytest.approx(56.5e-3) == made.cover_radius_m
    assert made.external and made.through and made.depth_m == 0 and made.plies_removed == 0 and made.patch_plies == 6
    assert made.group_thickness_m == pytest.approx(0.44e-3) and made.patch_thickness_m == pytest.approx(1.32e-3)
    assert [made.parent_ply_step(ply) for ply in range(1, 9)] == [None] * 8
    assert [made.patch_group(step) for step in (1, 2, 3)] == [(0.0, 45.0), (0.0, 45.0), (0.0, 0.0)]  # step 1 lies on the laminate
    assert external(patch_material=None).patch_material is PLY
    assert not repair().external and repair().patch_plies == 4


@pytest.mark.parametrize("changes, words", [
    (dict(kind="scarf"), "The kind of repair is one of flush, external"),
    (dict(patch_shape="square"), "The patch's shape is one of round, strip"),
    (dict(patch_angles=None), "needs its plies listed, from the one on the laminate upward"),
    (dict(patch_angles=(0, 0, 0)), "make a patch of 6 plies, and 3 are listed"),
    (dict(cover_angles=(45,), cover_overlap_m=5e-3), "has no cover plies"),
    (dict(patch_overlap_m=0.0), "The patch's overlap past the damage's edge must be a positive"),
    (dict(patch_overlap_m=0.05e-3), "thinner than a step is long and than the patch's overlap"),
    (dict(panel_length_m=0.1), "needs a panel longer than the patch and wider than the hole"),
    (dict(damage_diameter_m=90e-3), "needs a panel longer than the patch and wider than the hole"),
    (dict(patch_shape="round"), "so the panel must be longer and wider"),
])
def test_what_is_not_an_external_repair_is_refused_in_words(changes, words):
    with pytest.raises(RepairError, match=words):
        external(**changes)


def test_a_flush_repair_takes_no_strip_and_no_patch_overlap():
    for changes in (dict(patch_shape="strip"), dict(patch_overlap_m=5e-3)):
        with pytest.raises(RepairError, match="belong to an external repair"):
            repair(**changes)


@pytest.mark.parametrize("name", EXTERNAL_FAMILY)
def test_an_external_patchs_rectangles_do_not_overlap_and_agree_with_the_level_by_level_rule(name):
    made = external(**EXTERNAL_FAMILY[name])
    parts = regions(made)
    check_regions(made)
    for a, b in itertools.combinations(parts, 2):
        assert min(a.r1, b.r1) - max(a.r0, b.r0) <= 1e-15 or min(a.z1, b.z1) - max(a.z0, b.z0) <= 1e-15, (a.name, b.name)
    assert [part.kind for part in parts] == ["parent"] * made.plies + ["adhesive"] + ["patch"] * made.patch_plies
    hole, h, eta = made.damage_diameter_m / 2, made.thickness_m, made.adhesive.thickness_m
    assert all(part.r0 == hole and part.r1 == made.panel_length_m / 2 and not part.round for part in parts[:made.plies])
    glue = parts[made.plies]
    assert (glue.r0, glue.r1, glue.z0, glue.z1) == pytest.approx((hole, made.patch_radius_m, h, h + eta))
    assert all(part.round == (made.patch_shape == "round") for part in parts[made.plies:])
    # the hole is empty under the patch, the patch lies over it, and beyond each step's edge there is nothing at its level
    assert region_at(made, hole / 2, h / 2) is None and region_at(made, hole / 2, h + eta / 2) is None
    assert region_at(made, hole / 2, h + eta + made.patch_thickness_m * 0.99) == "patch"
    assert region_at(made, made.cut_radius_m(made.steps) + 1e-6, h + eta + made.patch_thickness_m * 0.99) is None
    assert region_at(made, made.patch_radius_m - 1e-6, h + eta + 1e-7) == "patch" and region_at(made, made.patch_radius_m + 1e-6, h + eta / 2) is None
    assert region_at(made, made.patch_radius_m + 1e-6, h / 2) == "parent"
    top = max(part.z1 for part in parts)
    assert top == pytest.approx(h + eta + made.patch_thickness_m) and region_at(made, 0.0, top + 1e-9) is None


@pytest.mark.parametrize("name", EXTERNAL_FAMILY)
def test_an_external_patchs_areas_and_volumes_are_the_sums_written_out_from_the_description(name):
    made = external(**EXTERNAL_FAMILY[name])
    hole, h, eta, g, n = made.damage_diameter_m / 2, made.thickness_m, made.adhesive.thickness_m, made.group_thickness_m, made.steps
    radius = [hole + made.patch_overlap_m + (n - j) * made.step_length_m for j in range(1, n + 1)]
    area, volume = areas(made), volumes(made)
    assert area["parent"] == pytest.approx((made.panel_length_m / 2 - hole) * h)
    assert area["adhesive"] == pytest.approx((radius[0] - hole) * eta)
    assert area["patch"] == pytest.approx(sum(r * g for r in radius)) and area["cover"] == 0
    panel, width, disc = made.panel_length_m * made.panel_width_m, made.panel_width_m, math.pi * hole**2
    assert volume["parent"] == pytest.approx((panel - disc) * h) and volume["cover"] == 0
    if made.patch_shape == "strip":
        assert volume["adhesive"] == pytest.approx((2 * radius[0] * width - disc) * eta)
        assert volume["patch"] == pytest.approx(sum(2 * r * width * g for r in radius))
    else:
        assert volume["adhesive"] == pytest.approx(math.pi * (radius[0] ** 2 - hole**2) * eta)
        assert volume["patch"] == pytest.approx(sum(math.pi * r**2 * g for r in radius))
    assert bond_lengths(made) == {"top_face": pytest.approx(made.patch_overlap_m + (n - 1) * made.step_length_m)}


def test_an_external_patchs_lap_runs_from_its_edge_to_the_hole_and_ends_there():
    made = external()
    steps, names, continues = lap_steps(made)
    assert names == ["Ledge of step 1", "Ledge of step 2", "The whole patch"] and not continues
    assert [step.length_m for step in steps] == pytest.approx([12e-3, 12e-3, 20e-3])
    assert [step.outer_thickness_m for step in steps] == pytest.approx([0.44e-3, 0.88e-3, 1.32e-3])
    assert all(step.inner_thickness_m == pytest.approx(made.thickness_m) for step in steps)
    whole = stretching_matrix(PLY, QUASI)
    for groups, step in enumerate(steps, 1):  # each step's two stiffnesses are the shares of its own bonded section
        outer, inner = shared_stiffnesses(stretching_matrix(FABRIC, made.patch_angles[:2 * groups]), whole)
        assert step.outer_modulus_pa * step.outer_thickness_m == pytest.approx(outer)
        assert step.inner_modulus_pa * step.inner_thickness_m == pytest.approx(inner)
    solved = repair_lap(made, 2e5)
    direct = step_lap(steps, made.adhesive, 2e5)
    assert solved.forces == pytest.approx(direct.forces) and solved.forces[0] == 0 and solved.forces[-1] == pytest.approx(2e5)
    assert not solved.inner_continues


def test_two_stacks_of_one_poissons_ratio_share_by_their_own_e_t():
    # A fabric patch on a sheet of the same Poisson's ratio, both at 0: the bonded section's contraction is each one's own,
    # so the shares are the plain E t of each, the stiffnesses a lap worked by hand with moduli and thicknesses uses.
    sheet = RepairMaterial("Sheet", Lamina(E1=29e9, E2=29e9, G12=5e9, nu12=0.15), 1.6e-3)
    made = external(parent_material=sheet, parent_angles=(0,), patch_angles=(0,) * 6, adhesive=Adhesive(900e6, 0.1e-3, 30e6))
    for groups, step in enumerate(lap_steps(made)[0], 1):
        assert step.outer_modulus_pa == pytest.approx(24e9) and step.inner_modulus_pa == pytest.approx(29e9)
        assert step.outer_thickness_m == pytest.approx(groups * 0.44e-3)


def test_an_external_repair_reads_from_a_file_and_reports_in_its_units():
    case = load(STRIP_CASE)
    case.pop("expected")
    made, load_ = repair_from_dict(case)
    assert made.external and made.patch_shape == "strip" and made.patch_material.name == "Constructed patch ply"
    assert made.patch_overlap_m == pytest.approx(25e-3) and made.patch_material.ply_thickness_m == pytest.approx(0.2e-3)
    report = repair_report(made, "mm-MPa", load_)
    assert report["kind"] == "external" and report["patch_shape"] == "strip"
    assert report["sizes"]["patch_thickness"] == pytest.approx(1.2) and report["sizes"]["plies_removed"] == 0
    assert report["bond_lengths"] == {"top_face": pytest.approx(45.0)}
    assert [step["name"] for step in report["lap"]["steps"]] == ["Ledge of step 1", "Ledge of step 2", "The whole patch"]
    assert not report["lap"]["ends_at_the_middle"]
    own = dict(case, patch={"layup": [0, 90, 0, 0, 90, 0], "overlap": 25.0, "shape": "round"}, panel={"length": 240.0, "width": 200.0})
    assert repair_from_dict(own)[0].patch_material.name == "Constructed ply"  # no material said: the laminate's
    assert repair_report(repair(), "mm-MPa")["kind"] == "flush"


@pytest.mark.parametrize("change, words", [
    (lambda case: case.update(kind="scarf"), "kind must be one of flush, external"),
    (lambda case: case.pop("patch"), r"An external repair needs \[patch\]"),
    (lambda case: case["patch"].pop("overlap"), r"\[patch\] is missing: overlap"),
    (lambda case: case["patch"].pop("shape"), r"\[patch\] is missing: shape"),
    (lambda case: case["patch"].update(shape="square"), r"\[patch\]: shape must be one of round, strip"),
    (lambda case: case["patch"].pop("E2"), r"\[patch\] is missing: E2"),
    (lambda case: case["patch"].update(taper=2.0), r"\[patch\] has values a repair does not read: taper"),
    (lambda case: case.update(cover={"layup": [0], "overlap": 5.0}), r"An external patch has no \[cover\]"),
    (lambda case: case["patch"].update(layup=[0, 90]), "make a patch of 6 plies, and 2 are listed"),
    (lambda case: case["patch"].update(overlap="long"), "must be a number"),
])
def test_a_file_that_does_not_state_an_external_repair_is_refused_in_words(change, words):
    case = load(STRIP_CASE)
    case.pop("expected")
    change(case)
    with pytest.raises(RepairError, match=words):
        repair_from_dict(case)


def test_a_flush_file_takes_no_patch_overlap_or_shape():
    case = load(WITH_COVER)
    case.pop("expected")
    case["patch"] = {"layup": [0, 90, 0], "overlap": 5.0}
    with pytest.raises(RepairError, match=r"\[patch\]"):
        repair_from_dict(case)


# ---- what a page draws of a repair, and what a solve of its slice still needs (ADR-0135)

EXTERNAL_EXAMPLE = ENGINE / "examples" / "example-external-patch-repair.toml"


@pytest.mark.parametrize("path", [EXAMPLE, EXTERNAL_EXAMPLE], ids=lambda path: path.stem)
def test_the_curve_a_page_draws_is_the_laps_own_and_ends_on_the_values_the_report_gives(path):
    from anisotropy_engine.repair import repair_views

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    stated, load = repair_from_dict(data)
    report, views = repair_report(stated, data["units"], load), repair_views(stated, data["units"], load, points_per_step=5)
    length = UNIT_SYSTEMS[data["units"]]["length"][0]
    outer = (stated.patch_radius_m if stated.external else stated.cover_radius_m) / length
    assert views["half_length"] == pytest.approx(stated.panel_length_m / 2 / length) and views["outer"] == pytest.approx(outer)
    names = [step["name"] for step in report["lap"]["steps"]]
    assert [b["name"] for b in views["boundaries"]] == ["Edge of the repair", *names]
    reach = np.cumsum([step["length"] for step in report["lap"]["steps"]])
    assert [b["r"] for b in views["boundaries"]] == pytest.approx([outer, *(outer - reach)], abs=1e-9)
    # the lap ends at the hole's edge under a patch bonded on top, and at the repair's middle in a cut that leaves plies under the patch
    assert views["boundaries"][-1]["r"] == pytest.approx(stated.damage_diameter_m / 2 / length if stated.external else 0.0, abs=1e-9)
    lap, answer = views["lap"], report["lap"]["answer"]
    assert len(lap["r"]) == len(lap["shear"]) == len(lap["patch_force"]) == 5 * len(names)
    assert lap["r"][0] == pytest.approx(outer) and all(a >= b - 1e-12 for a, b in zip(lap["r"], lap["r"][1:])), "from the repair's edge inward"
    for k, (start, end) in enumerate(answer["shear_at_ends"]):  # each step's first and last point are the report's two ends
        assert lap["shear"][5 * k] == pytest.approx(start) and lap["shear"][5 * k + 4] == pytest.approx(end)
        assert lap["patch_force"][5 * k] == pytest.approx(answer["boundary_forces"][k], abs=1e-9)
        assert lap["patch_force"][5 * k + 4] == pytest.approx(answer["boundary_forces"][k + 1])
    assert max(abs(value) for value in lap["shear"]) == pytest.approx(abs(answer["peak_shear"]["value"]))


def test_a_repair_with_no_load_is_drawn_without_a_curve_and_an_unknown_unit_system_is_refused():
    from anisotropy_engine.repair import repair_views

    views = repair_views(repair(), "mm-MPa")
    assert "lap" not in views and views["outer"] == pytest.approx(25 / 2 + 3 * 12) and views["half_length"] == pytest.approx(200.0)
    with pytest.raises(RepairError, match="units must be one of"):
        repair_views(repair(), "furlongs")


def test_what_a_solve_still_needs_names_each_missing_value_and_where_it_is_stated():
    from anisotropy_engine.repair import solve_needs, tape_through_thickness

    assert [need["path"] for need in solve_needs(repair())] == ["parent.nu23", "adhesive.poisson", "applied.load"]
    assert [need["path"] for need in solve_needs(repair(), 0.0)][-1] == "applied.load"
    assert solve_needs(repair(), 1e5)[0]["words"].startswith("the laminate ply's constants through the thickness: nu23")
    through = RepairMaterial(PLY.name, PLY.lamina, PLY.ply_thickness_m, tape_through_thickness(PLY.lamina, 0.4))
    film = Adhesive(shear_modulus_pa=900e6, thickness_m=0.1e-3, shear_strength_pa=30e6, poisson_ratio=0.35)
    assert solve_needs(repair(parent_material=through, adhesive=film), 1e5) == []
    # a patch of its own material is asked for its own constants; a patch of the laminate's is not asked twice
    other = RepairMaterial("Other ply", PLY.lamina, PLY.ply_thickness_m)
    needs = solve_needs(repair(parent_material=through, adhesive=film, patch_material=other, patch_angles=(90, -45, 0, 45)), 1e5)
    assert [need["path"] for need in needs] == ["patch.nu23"] and needs[0]["words"].startswith("the patch ply's")
    for path in (EXAMPLE, EXTERNAL_EXAMPLE):  # the two examples a page opens with can be solved as they stand
        assert solve_needs(*repair_from_dict(tomllib.loads(path.read_text(encoding="utf-8")))) == []
