"""A coupon's values as one JSON object (ADR-0046 amendment 2): the rows of the input form by field key, as the studio sends them.
The same checks judge them, a values file is filed with its coupon, and a spec reads back into the values that made it. Form 0.3
adds the Failure criterion and f12* rows. Nothing here touches .local/."""

import json
from pathlib import Path

import pytest

from anisotropy_fea import paths
from anisotropy_fea.intake import (FIELDS, FILE_TEXT, FORM_VERSION, WORD_BYTES, IntakeError, build_specs, check_form, convert, designation_for, fill_form,
                                   read_form, read_input, read_values, size_that_fits, spec_from_values, stated_elements, values_of_spec,
                                   write_blank_form)
from anisotropy_fea.spec import MOST_ELEMENTS_STATED, element_estimate, load_spec, parse_spec, to_si

from public_coupon import DESIGNATION, PUBLIC_COUPON
from test_intake import OHT_FILL, PUBLIC_FILL, own_constants

SKIP = {"title", "source_sha256", "source_path"}  # the title is composed from the rows; a hand-written one is not kept


@pytest.fixture(scope="module", autouse=True)
def local_untouched():
    before = sorted(p.name for p in paths.LOCAL.iterdir()) if paths.LOCAL.is_dir() else None
    yield
    after = sorted(p.name for p in paths.LOCAL.iterdir()) if paths.LOCAL.is_dir() else None
    assert before == after, "the values tests must not write under .local/"


def values_file(folder: Path, values: dict, name: str = "values.json", **changes) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(json.dumps({"form_version": FORM_VERSION, **values, **changes}), encoding="utf-8")
    return path


def specs_of(folder: Path, values: dict, **changes) -> tuple[str, str]:
    form = read_values(values_file(folder, values, **changes))
    checked = check_form(form)
    return build_specs(checked, designation_for(checked, folder / "no-coupons"), form.path.name)


# --------------------------------------------------------------------------------------------- the same rows, the same checks

def test_a_values_file_gives_the_specs_the_filled_form_gives(tmp_path):
    blank = write_blank_form(tmp_path / "blank.xlsx")
    form = read_form(fill_form(blank, PUBLIC_FILL, tmp_path / "filled.xlsx"))
    values = read_values(values_file(tmp_path, PUBLIC_FILL))
    assert values.version == FORM_VERSION and set(values.cells) == set(FIELDS) == set(form.cells)
    assert check_form(values) == check_form(form)
    from_form = build_specs(check_form(form), designation_for(check_form(form), tmp_path / "none"), "filled.xlsx")
    from_values = build_specs(check_form(values), designation_for(check_form(values), tmp_path / "none"), "filled.xlsx")
    assert from_values == from_form


def test_lists_and_booleans_stand_for_the_forms_text(tmp_path):
    main, _ = specs_of(tmp_path, PUBLIC_FILL, mesh_partitions=[56, 110, 140, 194], mesh_seeds=[28, 27, 10, 27, 28], symmetric=True)
    spec = parse_spec(main)
    assert spec.mesh.y_partitions == [56.0, 110.0, 140.0, 194.0] and spec.mesh.y_seeds == [28, 27, 10, 27, 28] and spec.layup.symmetric
    main, _ = specs_of(tmp_path, PUBLIC_FILL, symmetric=False)
    assert not parse_spec(main).layup.symmetric


def test_the_ply_rows_may_be_given_one_by_one(tmp_path):
    rows = {k: v for k, v in PUBLIC_FILL.items() if k != "angles"}
    main, _ = specs_of(tmp_path, {**rows, "ply_1": 45, "ply_2": 0, "ply_3": -45, "ply_4": 90})
    assert parse_spec(main).layup.angles == [45.0, 0.0, -45.0, 90.0]


@pytest.mark.parametrize("changes, message", [
    ({"form_version": None}, "form_version is required"),
    ({"form_version": "0.2"}, "form_version '0.2' is not one this tool reads"),
    ({"laminate_thickness": 1.0}, "unknown keys laminate_thickness"),  # "thickness" is a row since form 0.9 (ADR-0075)
    ({"ply_1": 0}, "give angles or the ply rows"),
    ({"angles": "45, 0"}, "angles must be a list"),
    ({"angles": list(range(17))}, "lists 17 plies; the form holds 16"),
    ({"library": {"id": "im7-8552"}}, "library holds an object"),
])
def test_a_values_file_outside_the_rows_is_refused_by_name(tmp_path, changes, message):
    data = {"form_version": FORM_VERSION, **PUBLIC_FILL, **changes}
    path = tmp_path / "values.json"
    path.write_text(json.dumps({k: v for k, v in data.items() if not (k == "form_version" and v is None)}), encoding="utf-8")
    with pytest.raises(IntakeError, match=message):
        read_values(path)


def test_a_file_that_is_not_values_is_refused(tmp_path):
    (tmp_path / "notes.json").write_text("not json", encoding="utf-8")
    with pytest.raises(IntakeError, match="not a values file"):
        read_values(tmp_path / "notes.json")
    (tmp_path / "list.json").write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(IntakeError, match="one JSON object"):
        read_values(tmp_path / "list.json")
    (tmp_path / "coupon.toml").write_text("", encoding="utf-8")
    with pytest.raises(IntakeError, match=r"a filled-in form \(.xlsx\) or a values file \(.json\)"):
        read_input(tmp_path / "coupon.toml")
    assert read_input(values_file(tmp_path, PUBLIC_FILL)).cells["library"] == "im7-8552"


def test_a_blank_row_in_the_values_is_refused_as_on_the_form(tmp_path):
    with pytest.raises(IntakeError) as refused:
        specs_of(tmp_path, PUBLIC_FILL, length=None, G23="")
    assert "Length (mm): required" in str(refused.value) and "G23 (MPa): required" in str(refused.value)


@pytest.mark.parametrize("changes, said", [
    ({"width": float("inf")}, "Width (mm): a finite number is needed, not inf"),
    ({"length": float("nan")}, "Length (mm): a finite number is needed, not nan"),
    ({"length": "1e999"}, "Length (mm): a finite number is needed, not inf"),
    ({"element_size": float("-inf")}, "a finite number is needed, not -inf"),
    ({"tab_thickness": float("inf"), "tab_bevel": 30}, "Tab thickness (mm): a finite number is needed, not inf"),
    ({"material_code": "A" * 300}, "Material code and Layup code: the coupon's name would be 307 characters, and a name is at most 80; give shorter codes"),
    ({"layup_code": "L" + "1" * 90}, "the coupon's name would be 99 characters, and a name is at most 80"),
    ({"tab_thickness": 1.5, "tab_bevel": 30, "tab_material": "g" * 81},
     "Tab material: at most 80 bytes (a letter outside the basic Latin letters takes 2 to 4), not 81"),
    # a name is bounded in bytes, as a file counts it: 80 emoji are 320 bytes, more than a line of an Abaqus file holds
    ({"tab_thickness": 1.5, "tab_bevel": 30, "tab_material": "\U0001F600" * 80}, "Tab material: at most 80 bytes (a letter outside the basic Latin letters takes 2 to 4), not 320"),
    ({"tab_thickness": 1.5, "tab_bevel": 30, "tab_material": "\u00e9" * 41}, "Tab material: at most 80 bytes (a letter outside the basic Latin letters takes 2 to 4), not 82"),
    # a whole number of hundreds of digits, which JSON holds and a float does not
    ({"length": 10 ** 400}, "Length (mm): the number is too large"),
    ({"mesh_nx": 10 ** 400}, "Your Abaqus mesh: elements across the width: the number is too large"),
    ({"value": -10 ** 400}, ": the number is too large"),
    ({"angles": [45, 10 ** 400, -45, 90]}, "Ply 2: the number is too large"),
    # a word no line of a model file can hold: neither writer cuts a word
    ({"size_from": "x" * 5000}, "Where the size comes from: one word of it takes 5000 bytes, and a line of a model file holds a word of at most 200; "
                                "shorten it or put a space in it"),
    ({"team_model": "job " + "\u00e9" * 101}, "Your Abaqus model of this coupon: one word of it takes 202 bytes, and a line of a model file holds a word of at most 200"),
    ({"test_data": "\U0001F600" * 51 + " report"}, "Test data: one word of it takes 204 bytes"),
    ({**own_constants(), "own_source": "report-" + "n" * 194}, ": one word of it takes 201 bytes, and a line of a model file holds a word of at most 200"),
])
def test_a_size_that_is_no_finite_number_or_a_name_too_long_is_refused_at_its_row(tmp_path, changes, said):
    """What a values file may hold and no model may (JSON as Python reads it takes Infinity and NaN, and 1e999 is infinite): each
    stopped the tool with an error of its own before, one of them naming the folder it wrote in (ADR-0146)."""
    with pytest.raises(IntakeError) as refused:
        specs_of(tmp_path, PUBLIC_FILL, **changes)
    assert said in str(refused.value)


def test_a_name_at_its_limit_is_taken(tmp_path):
    longest = "A" * (80 - len("-UNT-L1"))
    main, _ = specs_of(tmp_path, PUBLIC_FILL, material_code=longest, layup_code="L1", tab_thickness=1.5, tab_bevel=30, tab_material="g" * 80)
    spec = parse_spec(main)
    assert spec.coupon.designation == f"{longest}-UNT-L1" and len(spec.coupon.designation) == 80 and spec.tabs.material == "g" * 80
    for material in ("\u00e9" * 40, "\U0001F600" * 20):  # 80 bytes of letters that take two and four
        assert parse_spec(specs_of(tmp_path, PUBLIC_FILL, tab_thickness=1.5, tab_bevel=30, tab_material=material)[0]).tabs.material == material


@pytest.mark.parametrize("word", ["w" * WORD_BYTES, "\u00e9" * (WORD_BYTES // 2), "\U0001F600" * (WORD_BYTES // 4)], ids=["ascii", "two bytes", "four bytes"])
def test_a_word_at_its_limit_is_taken_in_every_text_row_as_typed(tmp_path, word):
    assert len(word.encode("utf-8")) == WORD_BYTES == 200 and FILE_TEXT == ("size_from", "team_model", "test_data", "own_source")
    rows = {key: f"see {word} there" for key in ("size_from", "team_model", "test_data", "notes", "filled_by")}
    values = check_form(read_values(values_file(tmp_path, PUBLIC_FILL, **rows)))
    assert all(getattr(values, key) == text for key, text in rows.items())
    assert check_form(read_values(values_file(tmp_path, PUBLIC_FILL, **{**own_constants(), "own_source": f"see {word}"}))).own["source"] == f"see {word}"
    # a row that reaches no model file is not bounded by what a file's line holds: a long address in the notes is taken
    long = check_form(read_values(values_file(tmp_path, PUBLIC_FILL, notes="https://example.org/" + word * 3, filled_by=word * 2)))
    assert long.notes.endswith(word * 3) and long.filled_by == word * 2


@pytest.mark.parametrize("changes, said", [
    ({"length": 10 ** 400}, "Length (mm): the number is too large"),
    ({"regions": [{"name": "Patch", "x0": 10 ** 400, "x1": 20, "y0": 10, "y1": 20}]}, "Regions: entry 1 ('Patch') has a bound that is not a number"),
    ({"supports": [{"region": "Edge-Bottom", "dofs": [1, 2, 3], "value": 10 ** 400}]}, "Supports: entry 1 (Edge-Bottom) has a value that is not a number"),
    ({"loads": [{"region": "Face", "pressure": 10 ** 400}]}, "Loads: entry 1 (Face) has a pressure that is not a number"),
    ({"loads": [{"region": "Edge-Top", "dof": 2, "total": 10 ** 400}]}, "Loads: entry 1 (Edge-Top) has a total that is not a number"),
])
def test_a_whole_number_too_large_for_a_float_is_refused_at_its_row_in_a_plates_lists_too(tmp_path, changes, said):
    """A length of 1 followed by 400 zeros is JSON, and `float` raises OverflowError for it, which no row caught: the tool stopped and
    the route answered 503 (ADR-0146, the review's second round)."""
    from anisotropy_fea import enabled

    plate = dict(filled_by="A. Engineer", date="2026-10-25", test="plate", material_code="AL", layup_code="L1", size_from="a plate",
                 length=200.0, width=100.0, material_kind="isotropic", own_name="Aluminium", own_E=70000.0, own_nu=0.33, own_source="a handbook",
                 thickness=2.0, element_size=10.0, supports=[{"region": "Edge-Bottom", "dofs": [1, 2, 3]}], loads=[{"region": "Face", "pressure": 0.01}])
    with enabled.every_test(True), pytest.raises(IntakeError) as refused:
        check_form(read_values(values_file(tmp_path, plate, **changes)))
    assert said in str(refused.value) and len(str(refused.value)) < 600  # and never the number's hundreds of digits


# --------------------------------------------------------------------------------------------- the most elements a setup holds (ADR-0086 amendment 2)

def rows_of(fill: dict, **changes) -> dict:
    return {**{key: value for key, value in fill.items() if not key.startswith("mesh_")}, **changes}


@pytest.mark.parametrize("fill", [PUBLIC_FILL, OHT_FILL], ids=["strip", "open hole"])
def test_the_count_the_rows_state_is_the_count_of_the_spec_they_make(tmp_path, fill):
    """`stated_elements` is arithmetic on the rows, done before a spec is made of them; it is the spec's own estimate."""
    from anisotropy_fea import enabled

    finest = size_that_fits(fill["length"], fill["width"], MOST_ELEMENTS_STATED)
    with enabled.every_test(True):
        for size in (5.0, 2.0, 0.7, finest):
            values = check_form(read_values(values_file(tmp_path, rows_of(fill, element_size=size))))
            spec = spec_from_values(values, designation_for(values, tmp_path / "none"), "values.json")
            assert stated_elements(values) == element_estimate(spec) <= MOST_ELEMENTS_STATED, size
        seeded = check_form(read_values(values_file(tmp_path, PUBLIC_FILL)))
        assert stated_elements(seeded) == 10 * (28 + 27 + 10 + 27 + 28) == element_estimate(spec_from_values(seeded, designation_for(seeded, tmp_path / "none"), "v"))


@pytest.mark.parametrize("changes, count, change", [
    ({"element_size": 0.1}, "625,000", "use an element size of 0.18 mm or more"),
    ({"element_size": 1e-5}, "more than 1,000,000,000,000", "use an element size of 0.18 mm or more"),
    ({"element_size": 1e-6}, "more than 1,000,000,000,000", "use an element size of 0.18 mm or more"),
    ({"element_size": 5e-324}, "more than 1,000,000,000,000", "use an element size of 0.18 mm or more"),  # a length over it is beyond any number
    ({"element_size": None, "mesh_nx": 10, "mesh_partitions": "56, 110, 140, 194", "mesh_seeds": "28, 27, 99999999999, 27, 28"},
     "more than 1,000,000,000,000", "give fewer elements across the width or fewer rows per segment"),
    ({"element_size": None, "mesh_nx": 10, "mesh_partitions": "56, 110, 140, 194", "mesh_seeds": "28, 27, 99999, 27, 28"},
     "1,001,090", "give fewer elements across the width or fewer rows per segment"),
    ({"element_size": None, "mesh_nx": 10 ** 12, "mesh_partitions": "56, 110, 140, 194", "mesh_seeds": "28, 27, 10, 27, 28"},
     "more than 1,000,000,000,000", "give fewer elements across the width or fewer rows per segment"),
])
def test_rows_whose_mesh_would_pass_the_most_a_setup_holds_are_refused_by_arithmetic_before_a_spec_is_made(tmp_path, monkeypatch, changes, count, change):
    """An element size of 1e-5 mm once cost the STEP file 12 s and 1.2 GB, 1e-6 mm over 10 GB, and 99999999999 rows in a segment a 504 for
    every program: the spec's check built one row per element row (ADR-0086 amendment 2). Here nothing is built: the spec's parser is
    stood in by one that fails the test if it is called."""
    import time

    from anisotropy_fea import intake

    values = check_form(read_values(values_file(tmp_path, rows_of(PUBLIC_FILL, **changes))))
    monkeypatch.setattr(intake, "parse_spec", lambda *args, **kwargs: pytest.fail("a spec was made of the rows"))
    monkeypatch.setattr(intake, "render_toml", lambda *args, **kwargs: pytest.fail("a spec was written from the rows"))
    clock = time.perf_counter()
    with pytest.raises(IntakeError) as refused:
        build_specs(values, designation_for(values, tmp_path / "none"), "values.json")
    assert time.perf_counter() - clock < 1.0
    rows = "Your Abaqus mesh: elements across the width, Your Abaqus mesh: rows per segment" if "mesh_seeds" in changes else "Element size (mm)"
    assert str(refused.value) == (f"values.json: the spec refuses the inputs: the mesh would have {count} elements; a setup holds at most 200,000, "
                                  f"whatever is made of it: {change} (form rows: {rows})")


# --------------------------------------------------------------------------------------------- the failure criterion rows (form 0.3)

def test_all_reports_every_criterion_the_material_allows(tmp_path):
    assert parse_spec(specs_of(tmp_path, PUBLIC_FILL)[0]).output.fpf_criteria == ["max_stress", "tsai_hill"]
    with_f12 = parse_spec(specs_of(tmp_path, PUBLIC_FILL, f12_star=-0.5)[0])
    assert with_f12.output.fpf_criteria == ["max_stress", "tsai_hill", "tsai_wu"] and with_f12.material.f12_star == -0.5
    assert parse_spec(specs_of(tmp_path, PUBLIC_FILL, criteria="none")[0]).output.fpf_criteria == []
    assert parse_spec(specs_of(tmp_path, PUBLIC_FILL, criteria="tsai-hill")[0]).output.fpf_criteria == ["tsai_hill"]
    assert parse_spec(specs_of(tmp_path, PUBLIC_FILL, criteria="Tsai-Wu", f12_star=0.0)[0]).output.fpf_criteria == ["tsai_wu"]
    without = {**own_constants(), **{k: None for k in ("own_F1t", "own_F1c", "own_F2t", "own_F2c", "own_F6")}}
    assert parse_spec(specs_of(tmp_path, PUBLIC_FILL, **without)[0]).output.fpf_criteria == []  # all, on a material without strengths


@pytest.mark.parametrize("changes, message", [
    (dict(criteria="tsai-wu"), "Tsai-Wu interaction f12\\*: required for Tsai-Wu"),
    (dict(f12_star=1.0), "Tsai-Wu interaction f12\\*: must lie strictly between -1 and 1, not 1"),
    (dict(criteria="strength"), "Failure criterion: 'strength' is not one of all, maximum stress, tsai-hill, tsai-wu, none"),
    ({**own_constants(), **{k: None for k in ("own_F1t", "own_F1c", "own_F2t", "own_F2c", "own_F6")}, "criteria": "maximum stress"},
     "Failure criterion: the material has no strengths"),
    (dict(library="unobtainium"), "Library material: unknown library material 'unobtainium'"),
])
def test_a_criterion_the_inputs_cannot_support_is_refused_by_row(tmp_path, changes, message):
    with pytest.raises(IntakeError, match=message):
        specs_of(tmp_path, PUBLIC_FILL, **changes)


# --------------------------------------------------------------------------------------------- a spec reads back into its values

def round_trip(folder: Path, spec):
    values = values_of_spec(spec)
    values.update(filled_by="A. Engineer", date="2026-10-28")
    form = read_values(values_file(folder, values))
    checked = check_form(form)
    main, _ = build_specs(checked, designation_for(checked, folder / "none"), form.path.name)
    return values, parse_spec(main)


def plane_stress(spec):
    """The public check states nu23 for CalculiX's three-dimensional law; the form fixes plane stress, so the round trip starts there."""
    transverse = spec.material.transverse.model_copy(update={"plane_stress": True, "nu23": None})
    return spec.model_copy(update={"material": spec.material.model_copy(update={"transverse": transverse})})


def test_the_public_coupon_reads_back_into_its_values(tmp_path):
    public = plane_stress(parse_spec(PUBLIC_COUPON))
    values, again = round_trip(tmp_path, public)
    assert values["test"] == "unnotched tension" and values["material_code"] == "IM7" and values["layup_code"] == "L1" and values["criteria"] == "all"
    assert values["mesh_nx"] == 10 and values["mesh_partitions"] == [56.0, 110.0, 140.0, 194.0] and values["name_part"] == "Strip"
    # a tension coupon the form writes asks Abaqus for every layer (ADR-0089 amendment 1), an output request the hand-written spec predates
    expected = public.model_copy(update={"output": public.output.model_copy(update={"abaqus": public.output.abaqus.model_copy(update={"every_layer": True, "element": "S4"})})})
    assert again.model_dump(exclude=SKIP) == expected.model_dump(exclude=SKIP)
    assert values_of_spec(to_si(public)) == values_of_spec(public)  # a loaded spec gives the same rows as the file's text


@pytest.mark.parametrize("fill", [PUBLIC_FILL, OHT_FILL, {**PUBLIC_FILL, **own_constants()}, {**PUBLIC_FILL, "criteria": "tsai-hill", "f12_star": -0.5},
                                  {**PUBLIC_FILL, "tab_length": 0.0, "region": "line", "element_size": 2.0, "mesh_nx": None, "mesh_partitions": None,
                                   "mesh_seeds": None, "name_part": None, "name_instance": None, "name_material": None, "name_layup": None,
                                   "name_section": None}])
def test_values_to_spec_to_values_is_the_identity(tmp_path, fill):
    main, _ = specs_of(tmp_path, fill)
    first = parse_spec(main)
    values, again = round_trip(tmp_path / "again", first)
    assert again.model_dump(exclude=SKIP) == first.model_dump(exclude=SKIP)
    given = {k: v for k, v in fill.items() if v is not None and k not in ("filled_by", "date", "notes")}
    for key, value in given.items():
        if key == "name_material" and "own_name" in given:
            continue  # own constants carry their name on the Own material row; the deck's material name is that one
        if key in ("mesh_partitions", "mesh_seeds"):
            assert [float(p) for p in str(value).split(",")] == [float(p) for p in values[key]], key
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            assert values[key] == pytest.approx(value), key
        else:
            assert values[key] == value, key


def test_a_spec_the_form_cannot_state_is_refused(tmp_path):
    with pytest.raises(IntakeError, match="the form fixes plane_stress = true"):
        values_of_spec(parse_spec(PUBLIC_COUPON))  # nu23 stated, plane_stress false
    public = plane_stress(parse_spec(PUBLIC_COUPON))
    with pytest.raises(IntakeError, match="the form fixes element_order = 1"):
        values_of_spec(public.model_copy(update={"mesh": public.mesh.model_copy(update={"element_order": 2})}))
    with pytest.raises(IntakeError, match="offers all, one criterion or none"):
        values_of_spec(public.model_copy(update={"output": public.output.model_copy(update={"fpf_criteria": ["max_stress", "tsai_wu"]}),
                                                 "material": public.material.model_copy(update={"f12_star": 0.0})}))
    with pytest.raises(IntakeError, match="the form states a coupon in one of mm-MPa, m-Pa, in-psi, in-ksi"):
        values_of_spec(public.model_copy(update={"units": "SI"}))


def test_a_spec_reads_back_in_the_units_it_is_stated_in():
    """A spec in any stated system gives the rows in that system, with the Units row set (ADR-0061)."""
    public = plane_stress(parse_spec(PUBLIC_COUPON))
    assert values_of_spec(public)["units"] == "mm-MPa" and values_of_spec(public)["length"] == 250.0
    si = to_si(public)
    inches = values_of_spec(si.model_copy(update={"units": "in-psi"}))  # the same SI coupon, read back in inches and psi
    assert inches["units"] == "in-psi" and inches["length"] == pytest.approx(250.0 / 25.4) and inches["width"] == pytest.approx(25.0 / 25.4)
    assert inches["G13"] == pytest.approx(4688.43e6 / 6894.757293168, rel=1e-9) and inches["value"] == pytest.approx(1.0 / 25.4)
    assert inches["mesh_partitions"] == pytest.approx([56.0 / 25.4, 110.0 / 25.4, 140.0 / 25.4, 194.0 / 25.4])


def test_a_plain_mesh_with_tabs_reads_back_as_seeds(tmp_path):
    nodal = plane_stress(parse_spec(paths.spec_path("unnotched-im7-8552-nodal").read_text(encoding="utf-8")))  # nx 10, ny 125, 56 mm tabs
    values = values_of_spec(nodal)
    assert values["mesh_nx"] == 10 and values["mesh_partitions"] == [56.0, 194.0] and values["mesh_seeds"] == [28, 69, 28]
    assert values["grips"] == "nodal" and "material_code" not in values  # the check has no identity card


def test_spec_from_values_judges_without_writing(tmp_path):
    form = read_values(values_file(tmp_path, PUBLIC_FILL))
    checked = check_form(form)
    spec = spec_from_values(checked, designation_for(checked, tmp_path / "none"), form.path.name)
    assert spec.si and spec.coupon.designation == DESIGNATION and spec.geometry.length == pytest.approx(0.25)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["values.json"]


# --------------------------------------------------------------------------------------------- filing

def test_a_values_file_is_filed_with_its_coupon(tmp_path):
    root = tmp_path / "root"
    path = values_file(tmp_path, PUBLIC_FILL, name="values-abcd1234.json")
    intake = convert(path, root=root, day="2026-10-28")
    folder = root / DESIGNATION
    assert sorted(p.relative_to(folder).as_posix() for p in intake.written) == [
        "README.md", f"ours/{DESIGNATION}-nodal.toml", f"ours/{DESIGNATION}.toml", "team/2026-10-28/README.md", "team/2026-10-28/values-abcd1234.json"]
    readme = (folder / "team/2026-10-28/README.md").read_text(encoding="utf-8")
    assert "values-abcd1234.json" in readme and "the coupon's values as the studio sent them" in readme
    assert load_spec(folder / "ours" / f"{DESIGNATION}.toml").coupon.designation == DESIGNATION
    # a later values file replaces the specs and is filed too, so the attempt it starts has its input
    changed = values_file(tmp_path / "later", {**PUBLIC_FILL, "value": 2.0}, name="values-ef567890.json")
    again = convert(changed, root=root, day="2026-10-29", replace=True)
    assert sorted(p.relative_to(folder).as_posix() for p in again.written) == [f"ours/{DESIGNATION}-nodal.toml", f"ours/{DESIGNATION}.toml",
                                                                                "team/2026-10-29/values-ef567890.json"]
    assert load_spec(folder / "ours" / f"{DESIGNATION}.toml").loading.value == pytest.approx(0.002)
