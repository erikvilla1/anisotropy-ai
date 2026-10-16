"""Specs: every required key by name, every invalid combination refused, units converted once (ADR-0030, ADR-0003)."""

from pathlib import Path

import pytest

from anisotropy_fea.spec import SpecError, admissible_ny, full_angles, load_spec, mesh_counts, parse_spec, spec_material, spec_plies, to_si

SPECS = Path(__file__).parents[1] / "validation" / "specs"
NODAL = (SPECS / "unnotched-im7-8552-nodal.toml").read_text(encoding="utf-8")


def spec_with(old: str, new: str, base: str = NODAL):
    assert old in base, f"the spec no longer contains {old!r}"
    return parse_spec(base.replace(old, new, 1))


def test_the_committed_specs_load_and_convert_to_si():
    for path in sorted(SPECS.glob("*.toml")):
        spec = load_spec(path)
        assert spec.si and spec.source_sha256 and spec.source_path == str(path)
        assert spec.geometry.length < 1.0  # metres now
        material = spec_material(spec)
        assert material.rights in ("open-publisher", "public-domain"), f"{path.name}: committed specs use public materials only (R-16)"
        assert material.E1 > 1e9 and material.strengths is not None and material.citation_lines
        plies = spec_plies(spec)
        assert len(plies) == 8 and plies[0].thickness_m == pytest.approx(0.18288e-3)


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
    compression = (SPECS / "compression-im7-8552.toml").read_text(encoding="utf-8")
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


def test_admissible_ny_names_counts_that_hit_every_line():
    assert admissible_ny(250.0, [56.0, 194.0], 100) == [] or all(ny % 125 == 0 for ny in admissible_ny(250.0, [56.0, 194.0], 100))
    assert 125 in admissible_ny(250.0, [56.0, 194.0], 125)
    assert admissible_ny(140.0, [63.5, 76.5], 280) == [280]
