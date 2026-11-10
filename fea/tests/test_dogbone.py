"""A plastic dog-bone (ADR-0075, part 1): the outline is the one ASTM D638 draws for each type, the structured mesh follows it, an isotropic
material with no plies is stated by E, nu and a thickness and written as a homogeneous shell section, the spec refuses what this version does
not build, the public Type I check reads the material's modulus back through its extensometer, and the D638 profile judges a coupon as its
clauses ask. Nothing here touches .local/."""

import dataclasses
import json
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
from anisotropy_fea.standards.astm_c1869 import PROFILE as C1869
from anisotropy_fea.standards.astm_d3039 import PROFILE as D3039, classify
from anisotropy_fea.standards.astm_d638 import FIG1, PROFILE as D638, TYPES, VARIANTS
from anisotropy_fea.standards.conformance import judge, subject_of
from anisotropy_fea.standards.profile import LEVELS, MM
from anisotropy_fea.explain import fact_sheet, numbers_in, result_sentences
from anisotropy_fea.test_quantities import D638_RANGE, method_inputs
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
    ("gauge_length = 50.0", "gauge_length = 60.0", "must lie within the dog-bone's narrow section"),  # 60 over a 57 mm narrow section
])
def test_the_spec_refuses_what_this_version_does_not_build(old, new, words):
    text = edited(old, new)
    if "compression" in new:
        text = text.replace("value = 0.5", "value = -0.5").replace("PLASTIC-UNT-L1", "PLASTIC-UNC-L1").replace("unnotched tension:", "unnotched compression:")
    with pytest.raises(SpecError, match=re.escape(words)):
        parse_spec(text)


def test_grips_that_reach_the_narrow_section_are_refused():
    """Each grip may hold at most (165 - 57) / 2 = 54 mm of a Type I; 56 mm reaches the narrow section, with node rows on its lines."""
    text = edited("tab_length = 25.0", "tab_length = 56.0")
    text = edited("y_partitions = [25.0, 32.857626, 54.0, 57.5, 107.5, 111.0, 132.142374, 140.0]",
                  "y_partitions = [32.857626, 54.0, 56.0, 57.5, 107.5, 109.0, 111.0, 132.142374]", text)
    with pytest.raises(SpecError, match=re.escape("reaches the dog-bone's narrow section")):
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


def test_d638_reads_its_modulus_of_elasticity_over_the_narrow_section_in_its_own_words(solved):
    """D638 reduces the same record by its own clauses: the modulus of elasticity as the slope of the initial straight line, any segment of
    it (§11.4), read between A3.9.8's strains, over the least original cross-section (§11.2), never D3039's chord over the gross area. The
    explanation says the same, and every number it prints is a fact."""
    spec, data = solved
    block = data["summary"]["test_method"]
    words, chord = block["reduction"], block["strain"]["chord"]
    assert block["designation"] == "ASTM D638-22" and spec.test_method.variant == "I"
    assert (words["modulus"], words["modulus_clause"], words["area"]) == ("modulus of elasticity", "D638 §11.4", "area of the narrow section")
    assert words["poisson_clause"] == "D638 A3.10, Eq A3.1" and "D3039" not in " ".join(words.values())
    assert (chord["from"], chord["to"]) == D638_RANGE and chord["stress_from"] == pytest.approx(chord["modulus"] * 1000 * 500e-6)
    assert block["laminate_theory"]["isotropic"] is True and block["fpf"] == {} and block["note_b"] is False
    facts = fact_sheet(data["summary"], data["coupon"], data["units"], data["labels"])
    sentences = result_sentences(facts)
    method = [s for s in sentences if s.startswith(("As ASTM", "The extensometer"))]
    assert method[0].startswith("As ASTM D638-22 reduces a test: the area of the narrow section is 41.6 mm² (13 by 3.2 mm)")
    assert "the modulus of elasticity between 500 and 2500 microstrain is 3.001 GPa (the material's own value gives 3 GPa)" in method[1]
    assert not any(word in sentence for sentence in method for word in ("chord", "gross", "laminate theory"))
    assert data["summary"]["isotropic"] is True and "The material is isotropic: its yield and failure are not modelled yet, so no failure is reported." in sentences
    assert not any("ply" in sentence or "fibre" in sentence for sentence in sentences), "a plastic has no plies and no fibres to name"
    printed = {str(v) for v in facts.values()} | {f"{v:g}" for v in facts.values() if isinstance(v, float)}
    for sentence in sentences:
        for token in numbers_in(sentence):
            assert token in printed or any(token in v for v in printed), (token, sentence)


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


def test_the_profile_names_each_clause_level_and_rule_and_is_on_the_list():
    ids = [r.id for r in D638.requirements]
    assert len(ids) == len(set(ids)) and PROFILES[D638.id] is D638, "D638 is in the registry with the form's rows (ADR-0075 part 2)"
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
    assert found["composite-type"] == "na" and found["anisotropy"] == "na" and found["si-values"] == "na"
    assert found["scope-material"] == "na", "one isotropic material may be a plastic or a metal: the engineer states which"
    assert sum(1 for v in found.values() if v == "met") == 14 and sum(1 for v in found.values() if v == "lab") == 16


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


def test_grips_on_the_end_rows_hold_no_length_whatever_the_tab_length():
    """Grip region "line" holds only the end rows of nodes, so the model's grips are the whole length apart: D638's D, C1869's grip length and
    the free length read that, while the tab length stays the tab's for D3039 Table 2 (review of ADR-0075, 2026-11-09)."""
    s = subject(edited('region = "tabs"', 'region = "line"'))
    assert s.tab_length == pytest.approx(25 * MM) and s.gripped == 0.0 and s.gauge_length == pytest.approx(165 * MM)
    found = judge(next(r for r in D638.requirements if r.id == "grip-distance"), s)
    assert found.state == "deviation" and found.value == "165 mm: the model holds only the end rows"
    held = subject()
    assert held.gripped == pytest.approx(25 * MM) and judge(next(r for r in D638.requirements if r.id == "grip-distance"), held).state == "met"
    c1869 = judge(next(r for r in C1869.requirements if r.id == "grip-length"), dataclasses.replace(s, variant="B"))
    assert c1869.state == "deviation" and c1869.value == "0: the model holds only the end rows"


def test_an_isotropic_material_is_no_d3039_class_no_ceramic_composite_and_d638s_scope_is_the_engineers_to_state():
    s = subject()
    assert classify(s) is None, "one isotropic material has no plies, so no Table 2 class"
    d3039 = {r.id: judge(r, s) for r in D3039.requirements}
    assert d3039["scope-laminate"].state == "na" and "no plies" in d3039["scope-laminate"].value
    c1869 = {r.id: judge(r, s) for r in C1869.requirements if r.id in ("scope-matrix", "architecture")}  # the others need a hole
    assert c1869["scope-matrix"].state == "deviation" and "not a ceramic matrix composite" in c1869["scope-matrix"].value
    assert c1869["architecture"].state == "na"
    d638 = judge(next(r for r in D638.requirements if r.id == "scope-material"), s)
    assert d638.state == "na" and "a plastic or a metal" in d638.value


def test_type_iv_without_its_outer_radius_says_the_fillet_meets_the_width_at_a_corner():
    found = judge(next(r for r in D638.requirements if r.id == "outer-radius"), subject(variant="IV"))
    assert found.state == "deviation" and found.value == "none: the fillet meets the full width at a corner"
    assert found.limit == "25 mm ± 1 mm for Type IV"


def test_an_inch_coupon_is_told_that_the_millimetres_govern():
    note = next(r for r in D638.requirements if r.id == "si-values")
    assert note.level == "note" and note.clause == "§1.5"
    assert judge(note, subject()).state == "na"
    inch = judge(note, subject(units="in-psi"))
    assert inch.state == "note" and "converted exactly" in inch.value


def test_an_isotropic_deck_is_checked_on_e_alone_from_1_mpa(tmp_path):
    """A plastic of 2.5 GPa has G = 0.93 GPa: no warning, as its shear modulus is derived; 0.5 MPa is no plastic and is flagged."""
    import warnings
    deck_text = (CHECK.parent / "decks" / "d638-type-i-plastic-abaqus.inp").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert "*Elastic\n3000., 0.35" in deck_text
    for modulus, flagged in (("2500.", False), ("0.5", True)):
        path = tmp_path / f"plastic-{modulus}.inp"
        path.write_text(deck_text.replace("*Elastic\n3000., 0.35", f"*Elastic\n{modulus}, 0.35"), encoding="utf-8")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            read_deck(path, "mm-MPa")
        said = [str(w.message) for w in caught if "modulus" in str(w.message)]
        assert bool(said) == flagged, (modulus, said)
        if flagged:
            assert "0.001 GPa to 1000 GPa" in said[0]


def test_a_soft_plastic_is_no_unit_slip_on_the_checklist(tmp_path):
    from anisotropy_fea.checks import setup_checklist
    from anisotropy_fea.intake import read_values
    from test_standards import TOOLS
    for modulus, state in ((200, "pass"), (0.5, "warn")):  # 200 MPa, a low-density polyethylene; 0.5 MPa, a slip
        path = tmp_path / f"values-{modulus}.json"
        path.write_text(json.dumps({**PLASTIC, "own_E": modulus}), encoding="utf-8")
        checklist, _, _ = setup_checklist(read_values(path), tmp_path / "none", **TOOLS)
        units = next(item for item in checklist.items if item.id == "units")
        assert units.state == state, (modulus, units.message)


def test_an_inch_coupon_is_held_to_the_millimetre_values_converted():
    s = subject(variant="I", units="in-psi")
    found = judge(next(r for r in D638.requirements if r.id == "narrow-width"), s)
    assert found.state == "met" and found.limit == f"{13 / 25.4:.4g} in ± {0.5 / 25.4:.4g} in for Type I"


# --- the form (ADR-0075, part 2) ---------------------------------------------------------------------

PLASTIC = {"form_version": "0.9", "filled_by": "A. Engineer", "date": "2026-11-10", "units": "mm-MPa", "test": "unnotched tension",
           "standard": "ASTM D638-22", "specimen": "I", "size_from": "ASTM D638-22, Fig. 1: Type I", "length": 165, "width": 19, "tab_length": 25,
           "narrow_width": 13, "narrow_length": 57, "radius": 76, "strain_device": "extensometer", "strain_length": 50, "material_kind": "isotropic",
           "thickness": 3.2, "own_E": 3000, "own_nu": 0.35, "own_name": "PLASTIC", "own_source": "a nominal plastic for a test",
           "control": "displacement", "value": 0.5, "element_size": 1, "grips": "nodal", "region": "tabs"}


def form_values(tmp_path, **changes):
    from anisotropy_fea.intake import check_form, read_values
    path = tmp_path / "values.json"
    path.write_text(json.dumps({k: v for k, v in {**PLASTIC, **changes}.items() if v is not None}), encoding="utf-8")
    return check_form(read_values(path))


def test_the_form_states_a_plastic_dog_bone_and_the_spec_is_the_checks(tmp_path):
    """The rows of form 0.9 make the public check's coupon: one isotropic material with no plies, the dog-bone's sizes, D638 Type I. The
    mesh puts node rows where the outline turns and at the extensometer's ends, the spec builds a model, and D638 judges it met."""
    from anisotropy_fea.intake import designation_for, spec_from_values
    values = form_values(tmp_path)
    assert values.isotropic == {"thickness": 3.2, "E": 3000.0, "nu": 0.35, "name": "PLASTIC", "source": "a nominal plastic for a test"}
    assert values.dogbone == {"narrow_width": 13.0, "narrow_length": 57.0, "radius": 76.0} and values.stacking == () and values.criteria == ()
    designation = designation_for(values, tmp_path / "none")
    assert designation.material_code == "M1"  # an own material, as for own ply constants
    spec = spec_from_values(values, designation, "values.json")
    assert spec.layup is None and spec.material.E == pytest.approx(3e9) and spec.material.nu == pytest.approx(0.35)
    assert spec.geometry.thickness == pytest.approx(3.2e-3) and spec.geometry.dogbone.narrow_width == pytest.approx(13e-3)
    assert spec.test_method.id == "astm-d638" and spec.test_method.variant == "I" and list(spec.output.fpf_criteria) == []
    lines = {round(y * 1e3, 6) for y in spec.mesh.y_partitions}
    assert {25.0, 140.0, 54.0, 111.0, 57.5, 107.5}.issubset(lines) and any(abs(y - 32.857626) < 1e-5 for y in lines)
    assert spec.mesh.nx % 2 == 0, "an even count across puts the extensometer's nodes on the centre line"
    build_model(spec)
    subject = subject_of(spec)
    assert {judge(r, subject).state for r in D638.requirements} <= {"met", "lab", "na", "note"}, "Type I at its least size meets every clause it can"


def test_the_check_reads_back_into_the_form_and_the_form_takes_it(tmp_path):
    """`values_of_spec` is the form's reading turned round: the public check gives rows the form accepts, as the same plastic dog-bone."""
    from anisotropy_fea.intake import check_form, read_values, values_of_spec
    back = values_of_spec(load_spec(CHECK))
    assert (back["material_kind"], back["thickness"], back["own_E"], back["own_nu"], back["criteria"]) == ("isotropic", 3.2, 3000.0, 0.35, "none")
    assert (back["narrow_width"], back["narrow_length"], back["radius"]) == (13.0, 57.0, 76.0) and "outer_radius" not in back
    assert not any(key in back for key in ("angles", "symmetric", "library", "G13", "G23")), "a plastic has no plies and no ply material"
    # the check's spec names no person, date, material name or source; a coupon the form filed carries them
    rows = {**{k: v for k, v in back.items() if v is not None}, "filled_by": "A. Engineer", "date": "2026-11-10", "own_name": "PLASTIC",
            "own_source": "a nominal plastic"}
    path = tmp_path / "values.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    values = check_form(read_values(path))
    assert values.isotropic["E"] == pytest.approx(3000.0) and values.dogbone["radius"] == pytest.approx(76.0)


@pytest.mark.parametrize("changes, message", [
    (dict(ply_1=0, symmetric="yes"), "Ply 1 (bottom), Symmetric: belong to a material of plies; an isotropic material has none, so leave them blank"),
    (dict(library="im7-8552"), "Library material: belong to a material of plies"),
    (dict(own_nu=0.5), "Own material: nu: Poisson's ratio of an isotropic material lies above -1 and below 0.5, not 0.5"),
    (dict(own_E=None), "Own material: E (MPa): required for an isotropic material"),
    (dict(criteria="tsai-wu"), "Failure criterion: an isotropic material's yield and failure are not modelled yet; choose none"),
    (dict(test="three-point bending", span=48, overhang=6, tab_length=None, grips=None, region=None, narrow_width=None, narrow_length=None, radius=None,
          strain_device=None, strain_length=None, standard="none", specimen=None),
     "Material kind: an isotropic material is built for the pulled and pushed tests, not three-point bending"),
    (dict(test="open-hole tension", hole_diameter=3, standard="none", specimen=None),
     "Narrow width (mm) and the other dog-bone rows: belong to unnotched tension only; leave them blank"),
    (dict(radius=None), "Fillet radius (mm): required for a dog-bone"),
    (dict(material_kind="plies"), "Thickness (mm), Own material: E (MPa), Own material: nu: belong to an isotropic material"),
])
def test_the_form_refuses_what_a_plastic_or_a_dog_bone_cannot_be(tmp_path, changes, message):
    from anisotropy_fea.intake import IntakeError
    with pytest.raises(IntakeError, match=re.escape(message)):
        form_values(tmp_path, **changes)


def test_a_plastic_may_leave_the_criterion_blank_as_the_studio_does(tmp_path):
    assert form_values(tmp_path, criteria=None).criteria == ()
