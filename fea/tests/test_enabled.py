"""The tests the studio offers until the first workflow is validated (ADR-0089): the one list, the switch, and the form's definition."""

from __future__ import annotations

import importlib.util

import pytest

from anisotropy_fea import enabled, paths
from anisotropy_fea.enabled import (ALL_TESTS_VARIABLE, SwitchError, all_tests, is_material_kind_enabled, is_standard_enabled, is_test_enabled,
                                    standard_designations)
from anisotropy_fea.intake import MATERIAL_KINDS, TESTS
from anisotropy_fea.standards import NONE, PROFILES


def export_module():
    spec = importlib.util.spec_from_file_location("export_form_definition", paths.ROOT / "fea" / "tools" / "export_form_definition.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_list_names_only_words_the_form_holds():
    assert set(enabled.TESTS) <= set(TESTS) and enabled.TESTS == ("unnotched tension",)
    assert set(enabled.STANDARDS) <= set(PROFILES) and enabled.STANDARDS == ("astm-d3039",)
    assert set(enabled.MATERIAL_KINDS) <= set(MATERIAL_KINDS) and enabled.MATERIAL_KINDS == ("plies",)
    assert standard_designations() == ("ASTM D3039/D3039M-17",)
    assert enabled.DOGBONE is False


@pytest.mark.parametrize(("environ", "expected"), [({}, False), ({ALL_TESTS_VARIABLE: ""}, False), ({ALL_TESTS_VARIABLE: "  "}, False),
                                                   ({ALL_TESTS_VARIABLE: "off"}, False), ({ALL_TESTS_VARIABLE: "OFF"}, False),
                                                   ({ALL_TESTS_VARIABLE: "on"}, True), ({ALL_TESTS_VARIABLE: " On "}, True)])
def test_the_switch_is_on_only_when_it_says_on(environ, expected):
    assert all_tests(environ) is expected


@pytest.mark.parametrize("word", ["yes", "1", "true", "all", "of"])
def test_any_other_switch_word_is_refused(word):
    with pytest.raises(SwitchError, match="must be 'on' or 'off'"):
        all_tests({ALL_TESTS_VARIABLE: word})


def test_the_switch_is_read_from_the_process_on_every_call(monkeypatch):
    monkeypatch.setenv(ALL_TESTS_VARIABLE, "on")
    assert all_tests() is True
    monkeypatch.setenv(ALL_TESTS_VARIABLE, "off")
    assert all_tests() is False
    monkeypatch.delenv(ALL_TESTS_VARIABLE)
    assert all_tests() is False


def test_with_the_switch_off_only_tension_under_d3039_or_no_standard_with_plies_is_offered():
    assert is_test_enabled("unnotched tension", False)
    for test in set(TESTS) - {"unnotched tension"}:
        assert not is_test_enabled(test, False), test
    assert is_standard_enabled(NONE, False) and is_standard_enabled("", False) and is_standard_enabled(None, False)
    assert is_standard_enabled("ASTM D3039/D3039M-17", False) and is_standard_enabled("astm d3039/d3039m-17", False)
    for profile in PROFILES.values():
        if profile.id != "astm-d3039":
            assert not is_standard_enabled(profile.designation, False), profile.id
    assert is_material_kind_enabled("plies", False) and is_material_kind_enabled("", False) and is_material_kind_enabled(None, False)
    assert not is_material_kind_enabled("isotropic", False)


def test_with_the_switch_on_everything_is_offered():
    assert all(is_test_enabled(test, True) for test in TESTS)
    assert all(is_standard_enabled(p.designation, True) for p in PROFILES.values())
    assert is_material_kind_enabled("isotropic", True)


def test_the_form_definition_carries_the_list_and_never_the_switch(monkeypatch):
    module = export_module()
    monkeypatch.setenv(ALL_TESTS_VARIABLE, "on")
    with_on = module.render(module.definition())
    monkeypatch.setenv(ALL_TESTS_VARIABLE, "off")
    with_off = module.render(module.definition())
    assert with_on == with_off
    block = module.definition()["enabled"]
    assert block["tests"] == ["unnotched tension"] and block["standards"] == ["ASTM D3039/D3039M-17"]
    assert block["material_kinds"] == ["plies"] and block["dogbone"] is False and block["switch"] == ALL_TESTS_VARIABLE
    assert "ADR" not in block["not_available"]  # a sentence the page shows the engineer


# --------------------------------------------------------------------------------------------- part 2: the software refuses them

import importlib.util as _importlib_util
import json
import sys
from pathlib import Path

from anisotropy_fea.checks import setup_checklist
from anisotropy_fea.enabled import NotOffered, offered_words, refuse_hidden_kind
from anisotropy_fea.intake import FORM_VERSION, read_values
from anisotropy_fea.tow_test import tow_answer

from test_checks import TOOLS, by_id
from test_intake import OHT_FILL, PUBLIC_FILL

NOT_AVAILABLE = "is not available yet: the workspace offers the unnotched tension coupon"


@pytest.fixture(autouse=True)
def versions(monkeypatch):
    monkeypatch.setattr("anisotropy_fea.checks.ccx_version", lambda ccx: "2.22" if ccx is not None else None)  # as tests/test_checks.py


@pytest.fixture
def closed(monkeypatch):
    """The switch off, as on the hosted tier (the shared set-up turns it on for every other test)."""
    monkeypatch.setenv(ALL_TESTS_VARIABLE, "off")


def checked(folder: Path, values: dict, **changes):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "values.json"
    path.write_text(json.dumps({"form_version": FORM_VERSION, **values, **changes}), encoding="utf-8")
    return setup_checklist(read_values(path), folder / "none", **TOOLS)[0]


def load_tool(name: str, monkeypatch):
    tools = paths.ROOT / "fea" / "tools"
    monkeypatch.syspath_prepend(str(tools))  # run_coupon imports regenerate_decks from its own folder
    spec = _importlib_util.spec_from_file_location(name, tools / f"{name}.py")
    module = _importlib_util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)  # a dataclass looks its module up there
    spec.loader.exec_module(module)
    return module


def test_with_the_switch_off_the_tension_coupon_under_no_standard_or_d3039_is_ready(tmp_path, closed):
    assert checked(tmp_path / "none", PUBLIC_FILL).state == "ready"
    d3039 = checked(tmp_path / "d3039", PUBLIC_FILL, standard="ASTM D3039/D3039M-17", strain_device="extensometer", strain_length=25.0)
    assert not any(NOT_AVAILABLE in p for p in d3039.problems)


def test_with_the_switch_off_a_hidden_test_is_refused_on_its_test_row(tmp_path, closed):
    answer = checked(tmp_path, OHT_FILL)
    assert answer.state == "blocked"
    assert "Test: open-hole tension " + NOT_AVAILABLE in "\n".join(answer.problems)
    assert any("not available yet" in item.message for item in answer.items if item.state in ("fail", "missing"))


def test_with_the_switch_on_the_same_hidden_test_is_judged_as_before(tmp_path):
    answer = checked(tmp_path, OHT_FILL)
    assert not any("not available yet" in p for p in answer.problems)


@pytest.mark.parametrize(("changes", "words"), [
    ({"standard": "ASTM D638-22"}, "ASTM D638-22 " + NOT_AVAILABLE),
    ({"material_kind": "isotropic", "thickness": 3.2, "own_E": 3000.0, "own_nu": 0.35}, "one isotropic material " + NOT_AVAILABLE),
    ({"narrow_width": 13.0, "narrow_length": 57.0, "radius": 76.0}, "a dog-bone " + NOT_AVAILABLE),
])
def test_with_the_switch_off_d638_its_dogbone_and_one_isotropic_material_are_refused(tmp_path, closed, changes, words):
    answer = checked(tmp_path, PUBLIC_FILL, **changes)
    assert answer.state == "blocked"
    assert words in "\n".join(answer.problems)


def test_with_the_switch_off_the_tow_calculation_is_refused(tmp_path, closed):
    path = tmp_path / "tow.json"
    path.write_text(json.dumps({"form_version": FORM_VERSION, "test": "fibre tow tension", "filled_by": "A. Tester", "fibre": "a 12K carbon tow",
                                "specimens": [{"id": "1", "max_force": 2150, "status": "valid"}]}), encoding="utf-8")
    answer = tow_answer(path)
    assert answer["checklist"]["state"] == "blocked" and answer["result"] is None
    identity = next(item for item in answer["checklist"]["items"] if item["id"] == "identity")
    assert "fibre tow tension " + NOT_AVAILABLE in identity["message"]


def test_a_stored_coupon_of_a_hidden_test_is_kept_and_not_reopened_or_run(tmp_path, closed, monkeypatch):
    with pytest.raises(NotOffered, match="its test, open-hole tension, is not available yet"):
        refuse_hidden_kind("open_hole_tension", "IM7-OHT-L1", False)
    refuse_hidden_kind("unnotched_tension", "IM7-UNT-L1", False)
    refuse_hidden_kind("open_hole_tension", "IM7-OHT-L1", True)
    name = "IM7-OHT-L9"
    ours = tmp_path / name / paths.OURS
    ours.mkdir(parents=True)
    (ours / f"{name}.toml").write_text((paths.CHECKS / "open-hole-im7-8552" / "open-hole-im7-8552.toml").read_text(encoding="utf-8"), encoding="utf-8")
    studio = load_tool("studio_tool", monkeypatch)
    with pytest.raises(studio.IntakeError, match="not available yet"):
        studio.values(name, tmp_path)
    run_coupon = load_tool("run_coupon", monkeypatch)
    monkeypatch.setattr(run_coupon.paths, "ours", lambda coupon: tmp_path / coupon / paths.OURS)
    with pytest.raises(run_coupon.Refused, match="not available yet"):
        run_coupon.refuse_hidden(name)


def test_the_blank_excel_form_offers_what_the_studio_offers():
    assert offered_words("test", ("unnotched tension", "open-hole tension"), False) == ("unnotched tension",)
    assert offered_words("standard", ("none", "ASTM D3039/D3039M-17", "ASTM D638-22"), False) == ("none", "ASTM D3039/D3039M-17")
    assert offered_words("material_kind", ("plies", "isotropic"), False) == ("plies",)
    assert offered_words("units", ("mm-MPa", "in-psi"), False) == ("mm-MPa", "in-psi")
    assert offered_words("test", ("unnotched tension", "open-hole tension"), True) == ("unnotched tension", "open-hole tension")


# --------------------------------------------------------------------------------------------- amendment 4: a layup that only stretches

def test_with_the_switch_off_an_unsymmetric_tension_layup_is_refused_on_its_symmetric_row(tmp_path, closed):
    unsymmetric = checked(tmp_path / "once", PUBLIC_FILL, symmetric="no")  # [45/0/-45/90] listed once: it bends as it is pulled
    assert unsymmetric.state == "blocked" and f"Symmetric: {enabled.UNSYMMETRIC}" in "\n".join(unsymmetric.problems)
    assert "ADR" not in enabled.UNSYMMETRIC and "[0/45/-45/90]s" in enabled.UNSYMMETRIC  # a sentence for the engineer, with a way out
    listed = checked(tmp_path / "listed", PUBLIC_FILL, angles=[45, 0, -45, 90, 90, -45, 0, 45], symmetric="no")  # every ply, the same both ways
    assert listed.state == "ready" and not any("unsymmetric" in p for p in listed.problems)
    assert checked(tmp_path / "s", PUBLIC_FILL).state == "ready"


def test_with_the_switch_on_an_unsymmetric_tension_layup_is_judged_as_before(tmp_path):
    assert not any("unsymmetric" in p for p in checked(tmp_path, PUBLIC_FILL, symmetric="no").problems)


def test_the_symmetric_rule_reads_the_whole_layup_and_the_form_definition_carries_its_words():
    assert enabled.is_layup_enabled([0, 90, 90, 0], False) and enabled.is_layup_enabled([0], False)
    assert not enabled.is_layup_enabled([0, 45, -45, 90], False) and enabled.is_layup_enabled([0, 45, -45, 90], True)
    block = export_module().definition()["enabled"]
    assert block["symmetric_only"] is True and block["unsymmetric"] == enabled.UNSYMMETRIC


def test_a_library_material_without_a_ply_thickness_asks_for_it_on_its_row(tmp_path, closed):
    asked = checked(tmp_path / "asked", PUBLIC_FILL, library="as4-8552")
    assert asked.state == "blocked"
    assert any("Ply thickness (mm): required: the library's record of AS4 / 8552 gives no ply thickness" in p for p in asked.problems)
    given = checked(tmp_path / "given", PUBLIC_FILL, library="as4-8552", ply_thickness=0.19)
    assert not any("Ply thickness" in p for p in given.problems)
    assert not any("Ply thickness" in p for p in checked(tmp_path / "im7", PUBLIC_FILL).problems)  # IM7/8552's record gives one


def test_the_test_rows_help_names_only_the_tests_offered():
    from anisotropy_fea.intake import FIELDS

    assert enabled.offered_help("test", FIELDS["test"].help, False) == "the kind of test: unnotched tension, a plain strip pulled; other tests come later"
    assert enabled.offered_help("test", FIELDS["test"].help, True) == FIELDS["test"].help  # the switch on: every test, as before
    # the default is said on its row, after what the row is: the workspace shows a row's first clause under it
    units = FIELDS["units"].help
    assert "studio" not in enabled.NOT_AVAILABLE and units.startswith("the unit system every number") and "; left blank, it is mm-MPa;" in units

