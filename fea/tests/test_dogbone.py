"""A plastic dog-bone (ADR-0075, part 1): the outline is the one ASTM D638 draws for each type, the structured mesh follows it, an isotropic
material with no plies is stated by E, nu and a thickness and written as a homogeneous shell section, the spec refuses what this version does
not build, the public Type I check reads the material's modulus back through its extensometer, and the D638 profile judges a coupon as its
clauses ask. Nothing here touches .local/."""

import dataclasses
import math
import re
import tomllib

import numpy as np
import pytest

from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.dogbone import OutlineError, dogbone_outline
from anisotropy_fea.femodel import build_model, mesh_for_spec
from anisotropy_fea.fields import field_data
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.mesher import structured_dogbone
from anisotropy_fea.spec import SpecError, load_spec, parse_spec, section_width, spec_material
from anisotropy_fea.standards import PROFILES
from anisotropy_fea.standards.astm_d3039 import PROFILE as D3039
from anisotropy_fea.standards.astm_d638 import FIG1, PROFILE as D638, TYPES, VARIANTS
from anisotropy_fea.standards.conformance import judge, subject_of
from anisotropy_fea.standards.profile import LEVELS, MM
from anisotropy_fea.test_quantities import method_inputs
from anisotropy_fea.units import deck_units_of
from anisotropy_fea.write_abaqus import write_abaqus
from anisotropy_fea.write_calculix import write_calculix

CHECK = paths.CHECKS / "d638-type-i-plastic" / "d638-type-i-plastic.toml"
TEXT = CHECK.read_text(encoding="utf-8")
E, NU, THICKNESS, W = 3000.0, 0.35, 3.2, 13.0  # the check's material and narrow section, mm-MPa


@pytest.fixture(scope="module", autouse=True)
def local_untouched():
    before = sorted(p.name for p in paths.LOCAL.iterdir()) if paths.LOCAL.is_dir() else None
    yield
    after = sorted(p.name for p in paths.LOCAL.iterdir()) if paths.LOCAL.is_dir() else None
    assert before == after, "the dog-bone tests must not write under .local/"


def outline_of_type(key: str):
    f = FIG1[key]
    return dogbone_outline(f["W"], f["L"], f["R"], f["RO"], f["WO"], f["LO"])


# --- the outline -----------------------------------------------------------------------------------


@pytest.mark.parametrize("key", TYPES)
def test_every_type_of_fig_1_makes_an_outline_narrow_at_mid_length_and_full_at_the_ends(key):
    o, f = outline_of_type(key), FIG1[key]
    assert o.width_at(f["LO"] / 2) == pytest.approx(f["W"]) and o.width_at(0.0) == pytest.approx(f["WO"]) and o.width_at(f["LO"]) == pytest.approx(f["WO"])
    assert o.width_at(f["LO"] / 2 + f["L"] / 2) == pytest.approx(f["W"])  # the narrow section runs its whole length L
    ys = np.linspace(0.0, f["LO"], 2001)
    widths = np.array([o.width_at(y) for y in ys])
    half = widths[: len(ys) // 2 + 1]
    assert np.all(np.diff(half) <= 1e-12), "the width never grows towards mid-length"
    assert np.allclose(widths, widths[::-1]), "the outline is symmetric about mid-length"
    # tangent to the narrow section where the fillet starts: the width barely moves over the first hundredth of a millimetre
    assert o.half_width(o.l + 1e-7) - o.a < 1e-9
    # the grips start beyond the narrow section, so the gage length lies inside it
    assert (f["LO"] - f["D"]) / 2 < f["LO"] / 2 - f["L"] / 2 and f["G"] < f["L"]


def test_type_iv_has_two_arcs_that_meet_without_a_corner():
    o = outline_of_type("IV")
    eps = 1e-9
    before, at, after = o.half_width(o.s_tangent - eps), o.half_width(o.s_tangent), o.half_width(o.s_tangent + eps)
    assert before == pytest.approx(at, abs=1e-8) and after == pytest.approx(at, abs=1e-8)
    slope_in = (at - o.half_width(o.s_tangent - 1e-7)) / 1e-7
    slope_out = (o.half_width(o.s_tangent + 1e-7) - at) / 1e-7
    assert slope_in == pytest.approx(slope_out, rel=1e-4), "the fillet and the outer arc share their tangent where they meet"
    assert (o.half_width(o.s_full - 1e-7) - o.b) == pytest.approx(0.0, abs=1e-9), "the outer arc is tangent to the full width"
    assert set(o.lines()) == {"Narrow-Bottom", "Narrow-Top", "Arcs-Bottom", "Arcs-Top", "Full-Bottom", "Full-Top"}


def test_type_i_fillet_meets_the_full_width_where_the_circle_says():
    o = outline_of_type("I")  # step 3 mm on a 76 mm radius: the fillet runs sqrt(76^2 - 73^2) = sqrt(447) mm along the coupon
    assert o.s_full - o.l == pytest.approx(math.sqrt(447.0) * MM)
    assert o.lines()["Full-Bottom"] == pytest.approx((82.5 - 28.5 - math.sqrt(447.0)) * MM)


@pytest.mark.parametrize("args, words", [
    ((19.0, 57.0, 76.0, None, 19.0, 165.0), "must be less than the overall width"),
    ((13.0, 170.0, 76.0, None, 19.0, 165.0), "must be less than the overall length"),
    ((3.0, 57.0, 5.0, None, 19.0, 165.0), "cannot step the half-width out"),
    ((13.0, 57.0, 76.0, None, 19.0, 95.0), "the coupon must be longer than"),
])
def test_sizes_that_make_no_dog_bone_are_refused(args, words):
    with pytest.raises(OutlineError, match=words):
        dogbone_outline(*args)


# --- the mesh --------------------------------------------------------------------------------------


def test_the_mesh_follows_the_outline_row_by_row():
    o = outline_of_type("I")
    length, width = 165 * MM, 19 * MM
    mesh = structured_dogbone(width, length, o.width_at, 12, 165, node_rows={"Narrow": o.lines()["Narrow-Bottom"]})
    rows = np.round(mesh.xy[:, 1] / length * 165).astype(int)
    for row in range(166):
        x = mesh.xy[rows == row, 0]
        y = mesh.xy[rows == row, 1][0]
        assert x.min() == pytest.approx(width / 2 - o.width_at(y) / 2) and x.max() == pytest.approx(width / 2 + o.width_at(y) / 2)
    exact = sum(o.width_at(y) for y in np.linspace(0.0, length, 200001)) * length / 200000  # the outline's area, by the rectangle rule
    p = mesh.xy[mesh.corners]
    area = 0.5 * np.abs(sum(p[:, i, 0] * p[:, (i + 1) % 4, 1] - p[:, (i + 1) % 4, 0] * p[:, i, 1] for i in range(4))).sum()
    assert area == pytest.approx(exact, rel=1e-4), "the chords between rows cut the fillets by less than a ten-thousandth of the area"
    left = mesh.xy[mesh.node_sets["Edge-Left"]]
    assert len(left) == 166 and np.allclose(left[:, 0], [width / 2 - o.width_at(y) / 2 for y in left[:, 1]])


def test_the_mesh_at_order_two_keeps_its_midside_nodes_on_the_chords_and_the_sides_whole():
    o = outline_of_type("V")
    mesh = structured_dogbone(9.53 * MM, 63.5 * MM, o.width_at, 4, 40, order=2)
    assert mesh.midside is not None and mesh.node_sets["Edge-Right"].size == 2 * 40 + 1


# --- the spec --------------------------------------------------------------------------------------


def test_the_check_states_a_plastic_without_plies_and_the_model_writes_it_as_one():
    spec = load_spec(CHECK)
    material = spec_material(spec)
    assert material.isotropic and material.E1 == material.E2 == material.E3 == pytest.approx(E * 1e6)
    assert material.G12 == material.G13 == material.G23 == pytest.approx(E * 1e6 / (2 * (1 + NU))) and material.nu13 == material.nu23 == NU
    assert section_width(spec) == pytest.approx(W * MM) and spec.layup is None
    model = build_model(spec)
    abaqus = write_abaqus(model)
    assert "*Shell Section, elset=All, material=EXPLICIT, orientation=Ori-1\n3.2, 3\n" in abaqus and "*Elastic\n3000., 0.35\n" in abaqus
    assert "composite" not in abaqus.split("*End Part")[0].split("*Shell Section")[1] and "LAMINA" not in abaqus
    order2 = spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"element_order": 2})})
    ccx = write_calculix(build_model(order2))
    assert "*ELASTIC, TYPE=ISO\n3000., 0.35, 293.\n" in ccx and "*SHELL SECTION, ELSET=All, MATERIAL=EXPLICIT, ORIENTATION=Ori-0\n3.2\n" in ccx
    assert "no layup: one isotropic material, 0.0032 m thick" in abaqus and "dog-bone: narrow section 0.013 m wide" in abaqus


def edited(old: str, new: str, text: str = TEXT) -> str:
    assert old in text, old
    return text.replace(old, new, 1)


@pytest.mark.parametrize("old, new, words", [
    ("\nnu = 0.35\n", "\n", "needs both material.E and material.nu"),
    ("\nnu = 0.35\n", "\nnu = 0.5\n", "strictly between -1 and 0.5"),
    ("E = 3000.0", "E = 3000.0\nlibrary = \"im7-8552\"", "give no library"),
    ("\nthickness = 3.2\n", "\n", "give geometry.thickness and no [layup]"),
    ("[material]", "[layup]\nangles = [0]\nangles_from = \"length\"\nsymmetric = false\nply_thickness = 3.2\n\n[material]", "no [layup]"),
    ("\nnu = 0.35\n", "\nnu = 0.35\n[material.transverse]\nG13 = 1.0\nG23 = 1.0\nplane_stress = true\ntransverse_isotropy = true\n", "takes no [material.transverse]"),
    ("fpf_criteria = []", "fpf_criteria = [\"max_stress\"]", "an isotropic material takes none"),
    ("mesher = \"structured\"", "mesher = \"gmsh\"", "mesh.mesher = \"gmsh\" goes with open_hole_tension"),
    ("radius = 76.0", "radius = 2.0", "geometry.dogbone: a fillet of radius 2 cannot step"),
    ("kind = \"unnotched_tension\"", "kind = \"compression\"", "geometry.dogbone belongs to unnotched_tension only"),
])
def test_the_spec_refuses_what_this_version_does_not_build(old, new, words):
    text = edited(old, new)
    if "compression" in new:
        text = text.replace("value = 0.5", "value = -0.5").replace("PLASTIC-UNT-L1", "PLASTIC-UNC-L1").replace("unnotched tension:", "unnotched compression:")
    with pytest.raises(SpecError, match=re.escape(words)):
        parse_spec(text)


def test_a_laminate_still_needs_its_layup_and_its_transverse_table():
    unnotched = (paths.CHECKS / "unnotched-im7-8552" / "unnotched-im7-8552-nodal.toml").read_text(encoding="utf-8")
    start = unnotched.index("[material.transverse]")
    end = unnotched.index("\n[", start + 1)
    with pytest.raises(SpecError, match="needs a \\[material.transverse\\]"):
        parse_spec(unnotched[:start] + unnotched[end + 1:])
    with pytest.raises(SpecError, match="geometry.thickness belongs to an isotropic material"):
        parse_spec(unnotched.replace("[geometry]\n", "[geometry]\nthickness = 1.0\n", 1))


# --- the check solved --------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def solved(tmp_path_factory):
    spec = load_spec(CHECK)
    path = tmp_path_factory.mktemp("d638") / "deck.inp"
    path.write_text(write_abaqus(build_model(spec)), encoding="utf-8")
    deck = read_deck(path, deck_units_of(spec.units))
    return spec, field_data(deck, solve_deck(deck), spec.units, criteria=(), method=method_inputs(spec),
                            coupon={"designation": "PLASTIC-UNT-L1", "test": "unnotched tension", "layup": "isotropic"})


def test_the_extensometer_reads_the_materials_modulus_over_the_narrow_section(solved):
    """The closed form: in the narrow section the stress is the force over W t, uniform, so the extensometer reads E and the narrow section's
    contraction nu. The fillets 3.5 mm beyond the gage length's ends move both by less than 0.05 %."""
    spec, data = solved
    block = data["summary"]["test_method"]
    assert block["width"] == pytest.approx(W) and block["thickness"] == pytest.approx(THICKNESS) and block["area"] == pytest.approx(W * THICKNESS)
    assert block["strain"]["chord"]["modulus"] * 1000 == pytest.approx(E, rel=5e-4)
    assert block["strain"]["poisson"] == pytest.approx(NU, rel=1e-3)
    assert block["laminate_theory"]["modulus"] * 1000 == pytest.approx(E) and block["laminate_theory"]["poisson"] == pytest.approx(NU)
    assert block["stress"] == pytest.approx(block["force"] / (W * THICKNESS))


def test_the_record_agrees_with_the_closed_form_too():
    record = tomllib.loads((CHECK.parent / "records" / "d638-type-i-plastic-calculix.toml").read_text(encoding="utf-8"))
    force = record["expected"]["rf"]["Grip-Top"][1]
    bottom, top = (record["expected"]["u"][name][1] for name in ("Coupon-1.540", "Coupon-1.1190"))
    modulus = force / (W * THICKNESS) / ((top - bottom) / 50.0)
    assert modulus == pytest.approx(E, rel=5e-4), "CalculiX's extensometer reads the material's modulus too"


def test_the_hand_check_shares_the_pull_along_the_dog_bone_by_each_widths_compliance(tmp_path):
    """Laminate theory for a coupon that narrows: a bar of varying width stretches by R a22 times the integral of dy / w(y), so the pull
    sets N_y over the narrowest width. The chords between rows make that integral the outline's within 0.01 %, and the kernel's reaction
    and gauge strain lie within 0.1 % of it. The Summary's laminate-theory column carries the reaction over the narrow width too."""
    from anisotropy_fea.report import laminate_check
    from anisotropy_fea.spec import outline_of

    spec = load_spec(CHECK)
    path = tmp_path / "deck.inp"
    path.write_text(write_abaqus(build_model(spec)), encoding="utf-8")
    deck = read_deck(path, deck_units_of(spec.units))
    solution = solve_deck(deck)
    check = laminate_check(deck, solution)
    assert check.narrowed and check.width_m == pytest.approx(W * MM) and check.free_length_m == pytest.approx(115 * MM)
    outline = outline_of(spec)
    ys = np.linspace(25 * MM, 140 * MM, 200001)
    exact = W * MM * float(np.trapezoid(1.0 / np.array([outline.width_at(y) for y in ys]), ys))
    assert check.compliance_length_m == pytest.approx(exact, rel=1e-4)
    assert check.reaction_N == pytest.approx(0.5 * MM * E * 1e6 * THICKNESS * MM * W * MM / exact, rel=1e-4), "R = pull E t w_n / compliance"
    assert check.kernel_reaction_N == pytest.approx(check.reaction_N, rel=1e-3)
    assert check.kernel_strain[1] == pytest.approx(check.strain[1], rel=1e-3)
    clt = field_data(deck, solution, spec.units, criteria=(), method=method_inputs(spec),
                     coupon={"designation": "PLASTIC-UNT-L1", "test": "unnotched tension", "layup": "isotropic"})["summary"]["clt"]
    assert clt["width"] == pytest.approx(W) and clt["strain"][1] == pytest.approx(check.kernel_strain[1], rel=1e-3)


def test_the_mesh_of_the_check_has_rows_where_the_outline_turns():
    spec = load_spec(CHECK)
    mesh = mesh_for_spec(spec)
    ys = np.unique(np.round(mesh.xy[:, 1] * 1e9)) / 1e9
    for y in (54.0, 111.0, 82.5 - 28.5 - math.sqrt(447.0), 82.5 + 28.5 + math.sqrt(447.0)):
        assert np.min(np.abs(ys - y * MM)) < 1e-9, y


# --- the D638 profile --------------------------------------------------------------------------------


def subject(text: str = TEXT, **changes):
    return dataclasses.replace(subject_of(load_spec_text(text)), **changes)


def load_spec_text(text: str):
    from anisotropy_fea.spec import to_si
    return to_si(parse_spec(text))


def states(s) -> dict[str, str]:
    return {r.id: judge(r, s).state for r in D638.requirements}


def test_the_profile_names_each_clause_level_and_rule_and_waits_for_the_form():
    ids = [r.id for r in D638.requirements]
    assert len(ids) == len(set(ids)) and D638.id not in PROFILES, "D638 joins the registry with the form's rows (ADR-0075 part 2)"
    assert D638.catalog_url.startswith("https://store.astm.org/") and D638.rights == "licensed-reference" and "D638-22" in D638.edition_note and "D638-14" in D638.edition_note
    for r in D638.requirements:
        assert r.clause and r.text.endswith(".") and r.level in LEVELS and (r.rule is None) == (r.level == "lab"), r.id
    assert [v.key for v in VARIANTS] == list(TYPES) == list(D638.variant_words) and D638.variant_noun == "Type"
    for preset in VARIANTS:
        f = FIG1[preset.key]
        assert preset.si["tab_length"] == pytest.approx((f["LO"] - f["D"]) / 2) and preset.si["strain_length"] == f["G"]
        assert ("outer_radius" in preset.si) == (preset.key == "IV")


def test_the_type_i_check_meets_every_requirement_a_model_can_meet():
    s = subject(variant="I")
    found = states(s)
    assert {k for k, v in found.items() if v == "deviation"} == set() and {k for k, v in found.items() if v == "advisory"} == set()
    assert found["composite-type"] == "na" and found["anisotropy"] == "na"
    assert sum(1 for v in found.values() if v == "met") == 15 and sum(1 for v in found.values() if v == "lab") == 16


def test_the_profile_finds_each_miss_by_its_clause():
    s = subject(variant="I")
    assert states(dataclasses.replace(s, narrow_width=None, narrow_length=None, fillet_radius=None))["shape"] == "deviation"
    assert states(dataclasses.replace(s, narrow_width=13.6 * MM))["narrow-width"] == "deviation"
    assert states(dataclasses.replace(s, narrow_width=13.5 * MM))["narrow-width"] == "met"
    assert states(dataclasses.replace(s, width=26 * MM))["overall-width"] == "deviation"
    assert states(dataclasses.replace(s, tab_length=27.5 * MM))["grip-distance"] == "met"  # 110 mm, within 5 of 115
    assert states(dataclasses.replace(s, tab_length=28 * MM))["grip-distance"] == "deviation"  # 109 mm
    assert states(dataclasses.replace(s, outer_radius=25 * MM))["outer-radius"] == "deviation"
    assert states(dataclasses.replace(s, ply_thickness=8 * MM))["type-thickness"] == "deviation"
    assert states(dataclasses.replace(s, ply_thickness=15 * MM))["scope-thickness"] == "deviation"
    assert states(dataclasses.replace(s, ply_thickness=0.5 * MM))["thin-sheet"] == "advisory"
    assert states(dataclasses.replace(s, ply_thickness=4 * MM))["molded-thickness"] == "advisory"
    assert states(dataclasses.replace(s, strain_length=25 * MM))["gauge-length"] == "advisory"
    v = dataclasses.replace(s, variant="V")
    assert states(v)["preferred-type"] == "advisory" and states(v)["narrow-width"] == "deviation" and states(v)["molded-thickness"] == "na"
    iii = dataclasses.replace(s, variant="III", ply_thickness=10 * MM)  # Type III's thickness range, whatever its outline
    assert states(iii)["type-thickness"] == "met" and states(iii)["narrow-width"] == "deviation" and states(iii)["preferred-type"] == "na"


def test_a_fibre_laminate_lies_outside_d638_and_is_judged_as_type_i():
    s = subject(variant="II", isotropic=False, family="Carbon / epoxy", architecture="Unidirectional tape", angles=(0.0, 90.0, 90.0, 0.0),
                ply_thickness=0.8 * MM)
    found = states(s)
    assert found["scope-material"] == "deviation" and found["composite-type"] == "deviation" and found["anisotropy"] == "note"
    reason = judge(next(r for r in D638.requirements if r.id == "scope-material"), s).value
    assert "D3039" in reason


def test_d3039_says_a_dog_bone_and_a_plastic_are_not_its_specimen():
    s = subject()
    by_id = {r.id: judge(r, s) for r in D3039.requirements}
    assert by_id["section"].state == "deviation" and by_id["section"].value == "a dog-bone"
    assert by_id["scope-matrix"].state == "deviation" and "D638" in by_id["scope-matrix"].value


def test_an_inch_coupon_is_held_to_the_millimetre_values_converted():
    s = subject(variant="I", units="in-psi")
    found = judge(next(r for r in D638.requirements if r.id == "narrow-width"), s)
    assert found.state == "met" and found.limit == f"{13 / 25.4:.4g} in ± {0.5 / 25.4:.4g} in for Type I"
