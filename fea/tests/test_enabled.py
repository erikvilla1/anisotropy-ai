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
