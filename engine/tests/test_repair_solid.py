"""The plies and the adhesive of a repair's slice as solids (ADR-0132): the turned stiffness against the laminate theory's
reduced stiffness and against the closed form of validation/closed_forms.py (no engine code, no matrix inverse, no tensor
rotation), the far field against the laminate theory's response, a ply's own stresses, and what is refused."""

import importlib.util
import tomllib
from pathlib import Path

import numpy as np
import pytest

from anisotropy_engine.lamina import Lamina
from anisotropy_engine.laminate import Ply, abd_matrices
from anisotropy_engine.library import library_material
from anisotropy_engine.repair import (
    Adhesive, Repair, RepairError, RepairMaterial, ThroughThickness, adhesive_stiffness, far_field, plane_stress_stiffness, ply_axis_stress,
    ply_compliance, ply_stiffness, repair_from_dict, tape_through_thickness, turned_stiffness,
)
from anisotropy_engine.rotation import strain_transformation, transformed_reduced_stiffness

ENGINE = Path(__file__).parents[1]
VALIDATION = ENGINE / "validation"
CASES = sorted((VALIDATION / "repair_solid_cases").glob("*.toml"))
EXAMPLE = ENGINE / "examples" / "example-patch-repair.toml"

LAMINA = Lamina(E1=60e9, E2=20e9, G12=5e9, nu12=0.25)
SOLID = RepairMaterial("Test solid ply", LAMINA, 0.2e-3, ThroughThickness(E3=9e9, G13=4e9, G23=3e9, nu13=0.30, nu23=0.35))
FILM = Adhesive(shear_modulus_pa=900e6, thickness_m=0.1e-3, shear_strength_pa=30e6, poisson_ratio=0.35)
ANGLES = (0.0, 17.3, 30.0, -45.0, 60.0, 90.0, -90.0)


def closed_forms():
    spec = importlib.util.spec_from_file_location("closed_forms", VALIDATION / "closed_forms.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def flat(value) -> list[float]:
    return [float(v) for v in np.asarray(value, dtype=float).ravel()]


def answers(case: dict) -> dict:
    """What the engine gives for a solid ply case, in the case's mm, MPa and N/mm, in the case's order."""
    mat, mpa, mm = case["material"], 1e6, 1e-3
    material = RepairMaterial(mat["name"], Lamina(E1=mat["E1"] * mpa, E2=mat["E2"] * mpa, G12=mat["G12"] * mpa, nu12=mat["nu12"]),
                              mat["ply_thickness"] * mm,
                              ThroughThickness(E3=mat["E3"] * mpa, G13=mat["G13"] * mpa, G23=mat["G23"] * mpa, nu13=mat["nu13"], nu23=mat["nu23"]))
    c = ply_stiffness(material, case["ply"]["angle"]) / mpa
    q = plane_stress_stiffness(c)
    repair = Repair(parent_material=material, parent_angles=case["laminate"]["layup"], damage_diameter_m=0.02, steps=1, step_length_m=0.01,
                    adhesive=Adhesive(1e9, 0.1e-3), panel_length_m=0.3, panel_width_m=0.2)
    far = far_field(repair, case["applied"]["load"] * 1e3)
    return {
        "stiffness": [c[i, j] for i, j in ((0, 0), (0, 1), (0, 2), (0, 5), (1, 1), (1, 2), (1, 5), (2, 2), (2, 5), (3, 3), (3, 4), (4, 4), (5, 5))],
        "reduced_stiffness": [q[0, 0], q[0, 1], q[1, 1], q[0, 2], q[1, 2], q[2, 2]],
        "far_field_strains": [far.strain_x, far.strain_width],
        "far_field_ply_stress": [value / mpa for value in far.ply_stress_x],
    }


def test_there_is_a_case_and_it_has_its_closed_form():
    assert CASES and {path.stem for path in CASES} == set(closed_forms().SOLID_CASES)


@pytest.mark.parametrize("path", CASES, ids=[path.stem for path in CASES])
def test_every_expected_value_is_the_closed_form(path):
    case = tomllib.loads(path.read_text(encoding="utf-8"))
    reference = closed_forms().SOLID_CASES[path.stem](case)
    expected = {key: value for key, value in case["expected"].items() if key != "tolerance"}
    assert set(expected) == set(reference)
    for key, value in expected.items():
        assert flat(value) == pytest.approx(flat(reference[key]), rel=1e-9, abs=1e-12), key


@pytest.mark.parametrize("path", CASES, ids=[path.stem for path in CASES])
def test_the_engine_reproduces_the_case(path):
    case = tomllib.loads(path.read_text(encoding="utf-8"))
    got, count = answers(case), 0
    for key, value in case["expected"].items():
        if key == "tolerance":
            continue
        assert flat(got[key]) == pytest.approx(flat(value), rel=case["expected"]["tolerance"], abs=1e-9), key
        count += len(flat(value))
    assert count >= 25


def test_a_ply_in_its_own_axes_has_its_nine_constants():
    s = ply_compliance(LAMINA, SOLID.through)
    assert np.allclose(s, s.T)
    strain = s @ np.array([1.0, 0, 0, 0, 0, 0])  # a stress along the fibres alone
    assert strain[0] == pytest.approx(1 / 60e9) and strain[1] == pytest.approx(-0.25 / 60e9) and strain[2] == pytest.approx(-0.30 / 60e9)
    strain = s @ np.array([0, 1.0, 0, 0, 0, 0])  # across the fibres
    assert strain[1] == pytest.approx(1 / 20e9) and strain[2] == pytest.approx(-0.35 / 20e9)
    assert s[3, 3] == pytest.approx(1 / 3e9) and s[4, 4] == pytest.approx(1 / 4e9) and s[5, 5] == pytest.approx(1 / 5e9)
    assert np.allclose(ply_stiffness(SOLID, 0.0) @ s, np.eye(6), atol=1e-12)


@pytest.mark.parametrize("angle", ANGLES)
def test_a_turned_ply_free_through_its_thickness_is_the_laminate_theorys(angle):
    reduced = plane_stress_stiffness(ply_stiffness(SOLID, angle))
    assert np.allclose(reduced, transformed_reduced_stiffness(LAMINA, angle), rtol=1e-12, atol=1e-3)
    stiffness = ply_stiffness(SOLID, angle)
    assert np.allclose(stiffness, stiffness.T, rtol=1e-12, atol=1e-3) and np.all(np.linalg.eigvalsh(stiffness) > 0)


def test_a_quarter_turn_swaps_the_ply_axes():
    own, turned = ply_stiffness(SOLID, 0.0), ply_stiffness(SOLID, 90.0)
    swap = [1, 0, 2, 4, 3, 5]  # x takes 2's place and y takes 1's: xx <-> yy, yz <-> xz
    assert np.allclose(turned, own[np.ix_(swap, swap)], rtol=1e-12, atol=1e-3)
    assert turned[4, 4] == pytest.approx(3e9) and turned[3, 3] == pytest.approx(4e9)  # along the load the slice shears the ply across its fibres


def test_turning_back_returns_the_stiffness_and_an_isotropic_one_does_not_change():
    own = ply_stiffness(SOLID, 0.0)
    assert np.allclose(turned_stiffness(turned_stiffness(own, 37.0), -37.0), own, rtol=1e-12, atol=1e-3)
    film = adhesive_stiffness(FILM)
    assert np.allclose(turned_stiffness(film, 37.0), film, rtol=1e-12, atol=1e-3)


def test_the_adhesive_is_isotropic_with_its_shear_modulus_and_poissons_ratio():
    film = adhesive_stiffness(FILM)
    strain = np.linalg.solve(film, np.array([1.0, 0, 0, 0, 0, 0]))  # a stress along x alone
    young = 2 * 900e6 * (1 + 0.35)
    assert strain[0] == pytest.approx(1 / young) and strain[1] == pytest.approx(-0.35 / young) == pytest.approx(strain[2])
    assert film[3, 3] == film[4, 4] == film[5, 5] == 900e6


def test_the_far_field_of_a_balanced_symmetric_laminate_is_the_laminate_theorys_response():
    case = tomllib.loads(EXAMPLE.read_text(encoding="utf-8"))
    repair, load = repair_from_dict(case)
    far = far_field(repair, load)
    lamina, t = repair.parent_material.lamina, repair.ply_thickness_m
    a, _, _ = abd_matrices([Ply(material=lamina, angle_deg=angle, thickness_m=t) for angle in repair.parent_angles])
    strain = np.linalg.solve(np.asarray(a), np.array([load, 0.0, 0.0]))  # the load along x alone, free to contract and to shear
    assert strain[2] == pytest.approx(0.0, abs=1e-12)  # a balanced laminate does not shear
    assert far.strain_x == pytest.approx(strain[0], rel=1e-12) and far.strain_width == pytest.approx(strain[1], rel=1e-12)
    for angle, stress in zip(repair.parent_angles, far.ply_stress_x):
        assert stress == pytest.approx(float((transformed_reduced_stiffness(lamina, angle) @ strain)[0]), rel=1e-12)
    assert sum(far.ply_stress_x) * t == pytest.approx(load, rel=1e-12)


def test_the_far_field_of_an_unbalanced_laminate_carries_the_load_without_shearing():
    repair = Repair(parent_material=SOLID, parent_angles=(30, 30, 0), damage_diameter_m=0.02, steps=1, step_length_m=0.01, adhesive=FILM,
                    panel_length_m=0.3, panel_width_m=0.2)
    far = far_field(repair, 1e5)
    qs = [transformed_reduced_stiffness(LAMINA, angle) for angle in (30, 30, 0)]
    width_force = sum(q[1, 0] * far.strain_x + q[1, 1] * far.strain_width for q in qs) * 0.2e-3
    assert sum(far.ply_stress_x) * 0.2e-3 == pytest.approx(1e5, rel=1e-12) and width_force == pytest.approx(0.0, abs=1e-6)
    assert far_field(repair, -1e5).strain_x == pytest.approx(-far.strain_x)


@pytest.mark.parametrize("angle", ANGLES)
def test_a_plys_own_stresses_are_the_laminate_theorys_when_it_is_free_through_its_thickness(angle):
    stiffness = ply_stiffness(SOLID, angle)
    in_plane = np.array([1.2e-3, -0.4e-3, 0.7e-3])  # xx, yy and the engineering shear xy
    kept, free = [0, 1, 5], [2, 3, 4]
    strain = np.zeros(6)
    strain[kept] = in_plane
    strain[free] = -np.linalg.solve(stiffness[np.ix_(free, free)], stiffness[np.ix_(free, kept)] @ in_plane)  # no stress on zz, yz, xz
    own = ply_axis_stress(stiffness, angle, strain)
    q = np.array([[LAMINA.E1, LAMINA.nu12 * LAMINA.E2, 0], [LAMINA.nu12 * LAMINA.E2, LAMINA.E2, 0], [0, 0, 0]]) / (1 - LAMINA.nu12 * LAMINA.nu21)
    q[2, 2] = LAMINA.G12
    expected = q @ (strain_transformation(angle) @ in_plane)
    assert own[[0, 1, 5]] == pytest.approx(expected, rel=1e-10, abs=1e-3)
    assert own[[2, 3, 4]] == pytest.approx(0.0, abs=1e-3)
    many = ply_axis_stress(stiffness, angle, np.vstack([strain, 2 * strain]))
    assert many.shape == (2, 6) and np.allclose(many[1], 2 * own, rtol=1e-12, atol=1e-3)


def test_a_unidirectional_ply_needs_one_number_through_its_thickness():
    through = tape_through_thickness(LAMINA, 0.4)
    assert (through.E3, through.G13, through.nu13, through.nu23) == (LAMINA.E2, LAMINA.G12, LAMINA.nu12, 0.4)
    assert through.G23 == pytest.approx(LAMINA.E2 / (2 * 1.4))
    stiffness = ply_stiffness(RepairMaterial("Tape", LAMINA, 0.2e-3, through), 0.0)
    # such a ply is the same in every direction across its fibres, so there its shear stiffness follows from its direct ones
    assert stiffness[3, 3] == pytest.approx((stiffness[1, 1] - stiffness[1, 2]) / 2)
    assert stiffness[1, 1] == pytest.approx(stiffness[2, 2]) and stiffness[0, 1] == pytest.approx(stiffness[0, 2])
    with pytest.raises(RepairError, match="nu23"):
        tape_through_thickness(LAMINA, 1.0)


def test_what_does_not_make_a_material_or_what_a_solve_lacks_is_refused_in_words():
    with pytest.raises(RepairError, match="do not make a material"):
        RepairMaterial("Bad", LAMINA, 0.2e-3, ThroughThickness(E3=9e9, G13=4e9, G23=3e9, nu13=0.3, nu23=1.6))  # nu23^2 above E2 / E3
    with pytest.raises(RepairError, match="G13"):
        ThroughThickness(E3=9e9, G13=0.0, G23=3e9, nu13=0.3, nu23=0.3)
    with pytest.raises(RepairError, match="through-thickness constants"):
        ply_stiffness(RepairMaterial("Plane", LAMINA, 0.2e-3), 0.0)
    with pytest.raises(RepairError, match="Poisson's ratio"):
        adhesive_stiffness(Adhesive(900e6, 0.1e-3))
    for ratio in (0.5, -1.0, float("nan"), True):
        with pytest.raises(ValueError, match="Poisson's ratio"):
            Adhesive(900e6, 0.1e-3, poisson_ratio=ratio)
    with pytest.raises(ValueError, match="peel strength"):
        Adhesive(900e6, 0.1e-3, peel_strength_pa=0.0)
    repair = Repair(parent_material=SOLID, parent_angles=(0, 90), damage_diameter_m=0.02, steps=1, step_length_m=0.01, adhesive=FILM,
                    panel_length_m=0.3, panel_width_m=0.2)
    with pytest.raises(RepairError, match="load"):
        far_field(repair, float("inf"))


def stated(**changes) -> dict:
    data = tomllib.loads(EXAMPLE.read_text(encoding="utf-8"))
    for where, value in changes.items():
        table, key = where.split(".")
        if value is None:
            data[table].pop(key)
        else:
            data[table][key] = value
    return data


def test_a_repair_file_states_what_the_solve_needs():
    repair, _ = repair_from_dict(stated())
    lamina = library_material("im7-8552").lamina
    assert repair.parent_material.through == tape_through_thickness(lamina, 0.45) and repair.patch_material.through is repair.parent_material.through
    assert repair.adhesive.poisson_ratio == 0.35 and repair.adhesive.peel_strength_pa == pytest.approx(40e6)
    bare, _ = repair_from_dict(stated(**{"parent.nu23": None, "adhesive.poisson": None, "adhesive.peel_strength": None}))
    assert bare.parent_material.through is None and bare.adhesive.poisson_ratio is None  # the hand calculation needs neither
    assert bare.adhesive.peel_strength_pa is None  # nor the peel strength: without it the peel stress is not judged
    five = dict(E3=9000.0, G13=4000.0, G23=3000.0, nu13=0.3, nu23=0.35)
    full, _ = repair_from_dict(stated(**{f"parent.{key}": value for key, value in five.items()}, **{"adhesive.peel_strength": 40.0}))
    assert full.parent_material.through == ThroughThickness(E3=9e9, G13=4e9, G23=3e9, nu13=0.3, nu23=0.35)
    assert full.adhesive.peel_strength_pa == pytest.approx(40e6)
    typed = dict(name="Typed ply", E1=60000.0, E2=20000.0, G12=5000.0, nu12=0.25, ply_thickness=0.2, layup=[0, 90, 90, 0])
    strengths = dict(F1t=900.0, F1c=700.0, F2t=40.0, F2c=150.0, F6=60.0)
    data = stated()
    data["parent"] = {**typed, **strengths, "nu23": 0.4}
    data["steps"] = {"count": 2, "length": 12.5}
    got, _ = repair_from_dict(data)
    assert got.parent_material.lamina.strengths.F2t == pytest.approx(40e6) and got.parent_material.through.nu23 == 0.4


@pytest.mark.parametrize("changes, words", [
    ({"parent.G13": 4000.0}, "nu23 alone"),
    ({"parent.nu23": "0.4"}, "nu23 must be a number"),
    ({"parent.nu23": 1.5}, "nu23 must be above -1 and below 1"),
    ({"parent.F1t": 900.0}, "does not read: F1t"),  # a library material brings its own strengths
    ({"adhesive.poisson": 0.5}, "Poisson's ratio"),
    ({"adhesive.peel_strength": -1.0}, "peel strength"),
    ({"adhesive.peel_energy": 0.0}, "peel energy"),
    ({"adhesive.shear_energy": "2"}, "fracture energy must be a number"),
])
def test_a_repair_file_that_states_them_wrongly_is_refused(changes, words):
    with pytest.raises(RepairError, match=words):
        repair_from_dict(stated(**changes))


def test_a_repair_file_states_what_following_its_bond_needs():
    """The bond followed until it lets go (ADR-0137) needs the adhesive's six numbers whole. A fracture energy is stated in
    the file's force per length: N/mm in "mm-MPa", which is kJ/m^2."""
    from anisotropy_engine.repair import bond_needs

    repair, _ = repair_from_dict(stated())
    assert repair.adhesive.peel_energy_j_m2 == pytest.approx(500.0) and repair.adhesive.shear_energy_j_m2 == pytest.approx(2000.0)
    assert bond_needs(repair) == []  # and no load: the load is what the run finds
    inch = stated(**{"adhesive.peel_energy": 2.855, "adhesive.shear_energy": 11.42})  # lb/in
    inch["units"] = "psi"
    data = inch
    for table, keys in (("damage", ("diameter",)), ("steps", ("length",)), ("cover", ("overlap",)), ("adhesive", ("thickness",)), ("panel", ("length", "width"))):
        for key in keys:
            data[table][key] = data[table][key] / 25.4
    for key in ("shear_modulus", "shear_strength", "peel_strength"):
        data["adhesive"][key] = data["adhesive"][key] * 145.0377
    data.pop("applied")
    us, _ = repair_from_dict(data)
    assert us.adhesive.peel_energy_j_m2 == pytest.approx(500.0, rel=1e-3) and us.adhesive.shear_energy_j_m2 == pytest.approx(2000.0, rel=1e-3)
    bare, _ = repair_from_dict(stated(**{"parent.nu23": None, "adhesive.peel_strength": None, "adhesive.peel_energy": None, "adhesive.shear_energy": None}))
    assert [need["path"] for need in bond_needs(bare)] == ["parent.nu23", "adhesive.peel_strength", "adhesive.peel_energy", "adhesive.shear_energy"]
    assert bond_needs(bare)[-1]["words"] == "the bond's fracture energy in shear"
    with pytest.raises(ValueError, match="shear energy"):
        Adhesive(900e6, 0.1e-3, shear_energy_j_m2=-1.0)


def test_half_a_set_of_typed_strengths_is_refused():
    data = stated()
    data["parent"] = dict(name="Typed ply", E1=60000.0, E2=20000.0, G12=5000.0, nu12=0.25, ply_thickness=0.2, layup=[0, 90, 90, 0], F1t=900.0, F6=60.0)
    data["steps"] = {"count": 2, "length": 12.5}
    with pytest.raises(RepairError, match="all of the ply strengths"):
        repair_from_dict(data)
