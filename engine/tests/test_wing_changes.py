"""A change of plies to a wing, made on a copy of its wing file and worked before and after (ADR-0128)."""

import copy
import re
import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from anisotropy_engine.wing.analysis import analyze_wing
from anisotropy_engine.wing.changes import PlyChange, change_wing, change_words, preview_change, stack_words
from anisotropy_engine.wing.wing_file import wing_from_dict, wing_report

EXAMPLE = tomllib.loads((Path(__file__).parents[1] / "examples" / "example-wing.toml").read_text(encoding="utf-8"))
CAPS = {**EXAMPLE, "spar_caps": {"front_width": 0.045, "rear_width": 0.045, "half_stack": [0, 0, 45, -45, 0]}}
FOUNDERS = PlyChange(action="add_plies", part="spar_caps", angle=0, count=2, start=0, end=0.4)  # "Add 2 0 plies to the spar caps from the root to 40% span"


def test_the_founders_change_is_the_zone_adr_0125_writes_for_it_and_the_wing_given_is_not_changed():
    before = copy.deepcopy(CAPS)
    changed = change_wing(CAPS, FOUNDERS)
    assert changed["spar_caps"]["half_stack"] == [0, 0, 45, -45, 0]
    assert changed["spar_caps"]["zones"] == [{"start": 0.0, "end": 0.4, "half_stack": [0, 0, 0, 45, -45, 0]}]
    assert CAPS == before and "zones" not in CAPS["spar_caps"]
    assert change_words(CAPS, FOUNDERS) == ("Two 0° plies added to the spar caps from the root to 40 % of the half span, beside the 0° plies: "
                                            "[0/0/0/45/-45/0]s there.")
    wing_from_dict(changed)  # the wing file it writes is one the engine reads


def test_a_change_inside_a_zone_splits_it_and_stretches_of_one_stack_join_into_one():
    once = change_wing(CAPS, FOUNDERS)
    inner = change_wing(once, PlyChange(action="add_plies", part="spar_caps", angle=0, count=2, start=0, end=0.2))
    assert inner["spar_caps"]["zones"] == [{"start": 0.0, "end": 0.2, "half_stack": [0, 0, 0, 0, 45, -45, 0]},
                                           {"start": 0.2, "end": 0.4, "half_stack": [0, 0, 0, 45, -45, 0]}]
    rest = change_wing(once, PlyChange(action="add_plies", part="spar_caps", angle=0, count=2, start=0.4, end=1))
    assert rest["spar_caps"]["half_stack"] == [0, 0, 0, 45, -45, 0] and "zones" not in rest["spar_caps"]  # one stack root to tip: no zone
    middle = change_wing(CAPS, PlyChange(action="add_plies", part="spar_caps", angle=0, count=2, start=0.3, end=0.6))
    assert middle["spar_caps"]["zones"] == [{"start": 0.3, "end": 0.6, "half_stack": [0, 0, 0, 45, -45, 0]}]


def test_a_change_along_the_whole_span_changes_the_half_stack_and_every_zone():
    zoned = change_wing(CAPS, FOUNDERS)
    whole = change_wing(zoned, PlyChange(action="add_plies", part="spar_caps", angle=90, count=2))
    assert whole["spar_caps"]["half_stack"] == [0, 0, 45, -45, 0, 90]
    assert whole["spar_caps"]["zones"] == [{"start": 0.0, "end": 0.4, "half_stack": [0, 0, 0, 45, -45, 0, 90]}]


def test_plies_go_beside_their_angle_or_at_the_middle_and_come_out_nearest_the_middle():
    skin = change_wing(EXAMPLE, PlyChange(action="add_plies", part="skin", angle=90, count=2))["skin"]
    assert skin["half_stack"] == [0, 45, -45, 0, 90]  # no 90° ply to stand beside: on the inside of each face, next to the core
    assert "on the inside of each face" in change_words(EXAMPLE, PlyChange(action="add_plies", part="skin", angle=90, count=2))
    beside = change_wing(EXAMPLE, PlyChange(action="add_plies", part="skin", angle=135, count=4))["skin"]  # 135° is −45°
    assert beside["half_stack"] == [0, 45, -45, 135, 135, 0]
    middle = change_wing(EXAMPLE, PlyChange(action="add_plies", part="skin", angle=0, count=2, placement="middle"))["skin"]
    assert middle["half_stack"] == [0, 45, -45, 0, 0]
    fewer = change_wing(CAPS, PlyChange(action="remove_plies", part="spar_caps", angle=0, count=2, start=0.7, end=1))["spar_caps"]
    assert fewer["zones"] == [{"start": 0.7, "end": 1.0, "half_stack": [0, 0, 45, -45]}]  # the outside plies run on


@pytest.mark.parametrize(("data", "change", "words"), [
    (EXAMPLE, dict(action="add_plies", part="spar_caps", angle=0, count=2), "The wing has no spar caps"),
    (CAPS, dict(action="remove_plies", part="spar_caps", angle=90, count=2), "has 0 plies at 90°"),
    (CAPS, dict(action="remove_plies", part="spar", angle=45, count=4), "has 2 plies at +45°"),
])
def test_a_change_the_wing_cannot_take_is_refused_by_name(data, change, words):
    with pytest.raises(ValueError, match=re.escape(words)):
        change_wing(data, PlyChange(**change))


@pytest.mark.parametrize(("fields", "words"), [
    (dict(count=3), "plies go in pairs"), (dict(start=0.5, end=0.4), "start before end"), (dict(count=0), "greater than or equal to 1"),
    (dict(part="rib"), "Input should be"), (dict(placement="outside"), "Input should be"),
])
def test_a_change_out_of_shape_is_refused(fields, words):
    with pytest.raises(ValidationError, match=words):
        PlyChange(**{"action": "add_plies", "part": "skin", "angle": 0, "count": 2, **fields})


def test_the_preview_works_the_wing_before_and_after_and_judges_the_drop_it_makes():
    preview = preview_change(CAPS, FOUNDERS)
    wing, envelope = wing_from_dict(CAPS)
    report = wing_report(analyze_wing(wing, envelope), "SI", "m/s")
    assert preview["before"]["governing"] == report["governing"] and preview["before"]["mass"] == report["design"]["mass"]
    assert preview["after"]["lowest"]["skin plies"] > preview["before"]["lowest"]["skin plies"]  # more 0° plies where the bending is largest
    assert preview["after"]["mass"] > preview["before"]["mass"]
    assert preview["wing"] == change_wing(CAPS, FOUNDERS) and preview["words"] == change_words(CAPS, FOUNDERS)
    drops = [rule for rule in preview["rules"] if rule["rule"].startswith("drop_")]
    assert {rule["rule"] for rule in drops} == {"drop_count", "drop_ratio", "drop_cover"} and all(rule["at"] == 0.4 and rule["met"] for rule in drops)
    assert {rule["part"] for rule in preview["rules"]} == {"cap"}
    assert stack_words([0, 0, 45, -45, 0]) == "[0/0/45/-45/0]s"
