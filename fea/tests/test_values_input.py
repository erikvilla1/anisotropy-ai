"""A coupon's values as one JSON object (ADR-0046 amendment 2): the rows of the input form by field key, as the studio sends them.
The same checks judge them, a values file is filed with its coupon, and a spec reads back into the values that made it. Form 0.3
adds the Failure criterion and f12* rows. Nothing here touches .local/."""

import json
from pathlib import Path

import pytest

from anisotropy_fea import paths
from anisotropy_fea.intake import (FIELDS, FORM_VERSION, IntakeError, build_specs, check_form, convert, designation_for, fill_form, read_form,
                                   read_input, read_values, spec_from_values, values_of_spec, write_blank_form)
from anisotropy_fea.spec import load_spec, parse_spec, to_si

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
    ({"form_version": "0.2"}, "form_version '0.2' is not the current form's"),
    ({"thickness": 1.0}, "unknown keys thickness"),
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
    assert again.model_dump(exclude=SKIP) == public.model_dump(exclude=SKIP)
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
    with pytest.raises(IntakeError, match="the form states a coupon in mm-MPa"):
        values_of_spec(public.model_copy(update={"units": "m-Pa"}))


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
