"""Specs: every required key by name, every invalid combination refused, units converted once (ADR-0030, ADR-0003)."""

from pathlib import Path

import pytest

from anisotropy_fea import paths  # where the files live (ADR-0036)
from anisotropy_fea.spec import (SpecError, admissible_ny, full_angles, load_spec, mesh_counts, parse_spec, row_coordinates, spec_material, spec_plies,
                                 to_si)

NODAL = (paths.spec_path("unnotched-im7-8552-nodal")).read_text(encoding="utf-8")


def spec_with(old: str, new: str, base: str = NODAL):
    assert old in base, f"the spec no longer contains {old!r}"
    return parse_spec(base.replace(old, new, 1))


def test_the_committed_specs_load_and_convert_to_si():
    for path in paths.all_specs():
        spec = load_spec(path)
        assert spec.si and spec.source_sha256 and spec.source_path == str(path)
        assert spec.geometry.length < 1.0  # metres now
        material = spec_material(spec)
        if spec.material.library is None:
            # the Kirsch plate: nominal isotropic constants written in the spec, no dataset to cite; its title and comments say so
            assert "Kirsch" in spec.title and material.rights == "spec" and material.E1 == material.E2 and material.strengths is None
            continue
        # A committed spec names a library record whose values may be cited publicly: public-domain, open-publisher, or a licensed
        # reference cited by table and page (ADR-0018; ADR-0030 amendment 4). User-supplied data and explicit constants stay local (R-16).
        assert material.rights in ("open-publisher", "public-domain", "licensed-reference"), f"{path.name}: committed specs cite library materials only (R-16)"
        assert material.E1 > 1e9 and material.strengths is not None and material.citation_lines
        plies = spec_plies(spec)
        if spec.material.library == "im7-8552":
            assert len(plies) == 8 and plies[0].thickness_m == pytest.approx(0.18288e-3)
        else:
            assert spec.material.library == "x840-z60-pw" and len(plies) == 10 and plies[0].thickness_m == pytest.approx(0.1e-3)


def test_units_are_converted_once_and_only_dimensioned_numbers_change():
    raw = parse_spec(NODAL)
    si = to_si(raw)
    assert raw.geometry.length == 250.0 and si.geometry.length == pytest.approx(0.250)
    assert si.geometry.tab_length == pytest.approx(0.056) and si.loading.value == pytest.approx(1e-3)
    assert si.material.transverse.G13 == pytest.approx(4688.43e6) and si.material.transverse.nu23 == 0.45
    assert si.probes.nodes["centre"] == pytest.approx((0.0125, 0.125))
    assert si.mesh.nx == 10 and si.layup.ply_thickness == "library"
    assert to_si(si) is si


def test_full_angles_and_mesh_counts():
    spec = parse_spec(NODAL)
    assert full_angles(spec) == [45, 0, -45, 90, 90, -45, 0, 45]
    assert mesh_counts(spec) == (10, 125)
    by_size = spec_with("nx = 10\nny = 125            # 2 mm rows: the tab lines at 56 and 194 mm fall on node rows", "element_size = 2.0")
    assert mesh_counts(by_size) == (13, 125)


def test_material_definition_from_the_library_and_from_explicit_constants():
    library = spec_material(to_si(parse_spec(NODAL)))
    assert library.name == "IM7-8552" and library.E3 == library.E2 and library.nu13 == library.nu12 and library.f12_star == 0.0
    explicit_text = NODAL.replace('library = "im7-8552"\ndataset = "ncamp-im7-8552-2019-rtd-measured-v1"\n',
                                  "E1 = 162095.74\nE2 = 8963.18\nG12 = 4688.43\nnu12 = 0.316\n").replace('ply_thickness = "library"', "ply_thickness = 0.18288")
    explicit = spec_material(to_si(parse_spec(explicit_text)))
    assert explicit.name == "EXPLICIT" and explicit.rights == "spec" and explicit.strengths is None and explicit.citation_lines == ()
    assert explicit.E1 == pytest.approx(162095.74e6)


REFUSALS = [
    ("kind = \"unnotched_tension\"", "kind = \"open_hole_tension\"", "hole_diameter is required for open_hole_tension"),
    ("tab_length = 56.0", "tab_length = 56.0\nhole_diameter = 6.0", "refused for every other kind"),
    ("tab_length = 56.0", "tab_length = 125.0", "two tabs shorter than the length"),
    ("ny = 125", "ny = 100", "admissible ny near 100"),
    ("nx = 10\n", "", "nx and mesh.ny go together"),
    ("[mesh]\nmesher = \"structured\"\nelement_order = 1\nnx = 10\nny = 125", "[mesh]\nmesher = \"structured\"\nelement_order = 1\nelement_size = 2.0\nnx = 10\nny = 125", "not both and not neither"),
    ("angles = [45, 0, -45, 90]", "angles = []", "at least one ply"),
    ("library = \"im7-8552\"", "library = \"im7-8552\"\nE1 = 1.0", "excludes explicit constants"),
    ("library = \"im7-8552\"\n", "E1 = 1.0\nE2 = 1.0\n", "library or all of E1, E2, G12, nu12"),
    ("transverse_isotropy = true", "transverse_isotropy = false", "E3 and nu13 are required"),
    ("transverse_isotropy = true", "transverse_isotropy = true\nE3 = 9000.0\nnu13 = 0.3", "do not give them"),
    ("value = 1.0", "value = -1.0", "unnotched_tension needs a positive loading.value"),
    ("value = 1.0", "value = 0.0", "must not be zero"),
    ("fpf_criteria = [\"max_stress\", \"tsai_hill\", \"tsai_wu\"]", "fpf_criteria = [\"max_strain\"]", "max_strain is refused"),
    ("fpf_criteria = [\"max_stress\", \"tsai_hill\", \"tsai_wu\"]", "fpf_criteria = [\"hashin\"]", "unknown criterion 'hashin'"),
    ("f12_star = 0.0      # Tsai-Wu interaction term, stated (Abaqus's documented default)\n", "", "material.f12_star is required"),
    ("f12_star = 0.0      # Tsai-Wu interaction term, stated (Abaqus's documented default)", "f12_star = 1.5", "strictly between -1 and 1"),
    ("centre = [12.5, 125.0], grip_corner = [0.0, 56.0]", "centre = [30.0, 125.0]", "lies outside the coupon"),
    ("[grips]\nkind = \"nodal\"\nregion = \"tabs\"     # the whole tab is gripped, as in the team's decks\n", "", "in-plane kinds need a \\[grips\\] table"),
    ("region = \"tabs\"", "region = \"line\"\n[nonsense]\nx = 1", "nonsense"),
    ("units = \"mm-MPa\"", "units = \"in-psi\"", "units must be stated"),
]


@pytest.mark.parametrize("old, new, message", REFUSALS, ids=[r[2][:36] for r in REFUSALS])
def test_invalid_specs_are_refused_by_name(old, new, message):
    with pytest.raises((SpecError, ValueError), match=message):
        spec_with(old, new)


def test_tabs_grips_need_tabs_and_compression_needs_a_negative_value():
    with pytest.raises(SpecError, match="positive geometry.tab_length"):
        spec_with("tab_length = 56.0", "tab_length = 0.0")
    compression = (paths.spec_path("compression-im7-8552")).read_text(encoding="utf-8")
    with pytest.raises(SpecError, match="compression needs a negative loading.value"):
        spec_with("value = -0.1", "value = 0.1", base=compression)


def test_shear_pm45_needs_a_balanced_pm45_layup():
    with pytest.raises(SpecError, match="every ply at \\+45 or -45"):
        spec_with("kind = \"unnotched_tension\"", "kind = \"shear_pm45\"")
    text = NODAL.replace("kind = \"unnotched_tension\"", "kind = \"shear_pm45\"").replace("angles = [45, 0, -45, 90]", "angles = [45, 45]")
    with pytest.raises(SpecError, match="balanced layup"):
        parse_spec(text)
    balanced = parse_spec(text.replace("angles = [45, 45]", "angles = [45, -45]"))
    assert balanced.kind == "shear_pm45"


def test_bending_rules():
    text = NODAL.replace("kind = \"unnotched_tension\"", "kind = \"three_point_bending\"").replace("tab_length = 56.0", "span = 230.0\noverhang = 10.0")
    text = text.replace("[grips]\nkind = \"nodal\"\nregion = \"tabs\"     # the whole tab is gripped, as in the team's decks\n", "")
    with pytest.raises(SpecError, match="no node row on the line\\(s\\) \\['Nose'\\]"):
        parse_spec(text)  # 2 mm rows miss the midspan line at 125 mm
    text = text.replace("ny = 125", "ny = 250")
    spec = parse_spec(text)
    assert spec.grips is None and spec.geometry.span == 230.0
    with pytest.raises(SpecError, match="must equal span \\+ 2 overhang"):
        parse_spec(text.replace("overhang = 10.0", "overhang = 5.0"))
    with pytest.raises(SpecError, match="load_span is required for four_point_bending"):
        parse_spec(text.replace("three_point_bending", "four_point_bending"))
    with pytest.raises(SpecError, match="take no \\[grips\\] table"):
        parse_spec(text.replace("[loading]", "[grips]\nkind = \"nodal\"\nregion = \"line\"\n\n[loading]"))


TEAM_COUPON = (paths.spec_path("X840PW-UNT-L1")).read_text(encoding="utf-8")
TEAM_SEEDS = ("y_partitions = [15.0, 35.97, 44.03, 65.0]", "y_seeds = [15, 21, 8, 21, 15]")


def test_a_mesh_seeded_by_segment_has_the_teams_node_rows():
    """The team's CAE mesh: partitions at 15, 35.97, 44.03 and 65 mm, seeded 15, 21, 8, 21, 15 (their report template)."""
    spec = parse_spec(TEAM_COUPON)
    assert mesh_counts(spec) == (10, 80)
    rows = row_coordinates(spec)
    assert len(rows) == 81 and rows[0] == 0.0 and rows[-1] == 80.0
    assert rows[15] == 15.0 and rows[36] == pytest.approx(35.97, abs=1e-12) and rows[44] == pytest.approx(44.03, abs=1e-12) and rows[65] == 65.0
    assert rows[16] - rows[15] == pytest.approx(20.97 / 21) and rows[37] - rows[36] == pytest.approx(8.06 / 8)
    si = to_si(spec)
    assert si.mesh.y_partitions == pytest.approx([0.015, 0.03597, 0.04403, 0.065]) and row_coordinates(si)[36] == pytest.approx(0.03597)
    assert row_coordinates(parse_spec(NODAL)) is None  # a uniform mesh keeps np.linspace in the mesher, so older decks do not change


SEED_REFUSALS = [
    (TEAM_SEEDS[1], "", "go together"),  # leaves the comment that followed it
    (TEAM_SEEDS[0], TEAM_SEEDS[0] + "\nny = 80", "replaces mesh.ny"),
    (TEAM_SEEDS[1], "y_seeds = [15, 21, 8, 21]", "one count per segment"),
    (TEAM_SEEDS[1], "y_seeds = [15, 21, 0, 21, 15]", "at least 1"),
    (TEAM_SEEDS[0], "y_partitions = [15.0, 44.03, 35.97, 65.0]", "increase strictly"),
    (TEAM_SEEDS[0], "y_partitions = [15.0, 35.97, 44.03, 85.0]", "increase strictly"),
    (TEAM_SEEDS[0], "y_partitions = [14.0, 35.97, 44.03, 65.0]", "no node row on the line\\(s\\) \\['Tab-Bottom-Line'\\]"),
]


@pytest.mark.parametrize("old, new, message", SEED_REFUSALS, ids=[r[2][:30] for r in SEED_REFUSALS])
def test_invalid_seeding_is_refused_by_name(old, new, message):
    with pytest.raises(SpecError, match=message):
        spec_with(old, new, base=TEAM_COUPON)


def test_admissible_ny_names_counts_that_hit_every_line():
    assert admissible_ny(250.0, [56.0, 194.0], 100) == [] or all(ny % 125 == 0 for ny in admissible_ny(250.0, [56.0, 194.0], 100))
    assert 125 in admissible_ny(250.0, [56.0, 194.0], 125)
    assert admissible_ny(140.0, [63.5, 76.5], 280) == [280]


PLANE_STRESS_LINE = "plane_stress = false  # nu23 and the derived nu13 go to CalculiX's three-dimensional law as given (the committed records were made this way)"


def test_plane_stress_writes_zero_through_thickness_poisson_ratios_and_refuses_the_given_ones():
    from anisotropy_fea.spec import SpecError

    assert NODAL.count(PLANE_STRESS_LINE) == 1
    without_nu23 = NODAL.replace("nu23 = 0.45         # nominal, no source\n", "")
    material = spec_material(to_si(parse_spec(without_nu23.replace(PLANE_STRESS_LINE, "plane_stress = true"))))
    assert material.plane_stress and material.nu13 == 0.0 and material.nu23 == 0.0
    assert material.E3 == material.E2 and material.G13 == pytest.approx(4688.43e6) and material.G23 == pytest.approx(3000e6)
    assert not spec_material(to_si(parse_spec(NODAL))).plane_stress
    with pytest.raises(SpecError, match="do not give nu23 or nu13"):
        parse_spec(NODAL.replace(PLANE_STRESS_LINE, "plane_stress = true"))
    with pytest.raises(SpecError, match="nu23 is required unless plane_stress = true"):
        parse_spec(without_nu23)
    with pytest.raises(SpecError, match="E3 is required"):
        parse_spec(without_nu23.replace(PLANE_STRESS_LINE, "plane_stress = true").replace("transverse_isotropy = true", "transverse_isotropy = false"))
    explicit_E3 = without_nu23.replace(PLANE_STRESS_LINE, "plane_stress = true\nE3 = 9000.0").replace("transverse_isotropy = true", "transverse_isotropy = false")
    assert spec_material(to_si(parse_spec(explicit_E3))).E3 == pytest.approx(9000e6)
