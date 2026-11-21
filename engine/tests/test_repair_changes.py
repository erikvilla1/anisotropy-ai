"""One change to a repair and one quantity swept (ADR-0136): the repair file a change writes, set against one edited by hand
here; a preview and a sweep's rows against the hand calculation called on those files directly; what is refused, in whose
words; the pick and the flat stretch against rows written out here; and the example's numbers the decision record quotes."""

import re
import copy
import math
import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from anisotropy_engine.repair import RepairChange, RepairError, RepairSweep, change_repair, pick_check, preview_change, repair_from_dict, repair_report, sweep_repair
from anisotropy_engine.repair.changes import shown, tidy
from anisotropy_engine.repair.sweeps import _flat_from, round_increment, round_values
from anisotropy_engine.units import INCH, LBF

ENGINE = Path(__file__).parents[1]
EXAMPLE = tomllib.loads((ENGINE / "examples" / "example-patch-repair.toml").read_text(encoding="utf-8"))
EXTERNAL = tomllib.loads((ENGINE / "examples" / "example-external-patch-repair.toml").read_text(encoding="utf-8"))


def worked(data: dict) -> dict:
    """The hand calculation of a repair file, called directly."""
    repair, load = repair_from_dict(data)
    return repair_report(repair, data["units"], load)


def edited(data: dict, table: str, key: str, value) -> dict:
    """A repair file edited by hand: one value of one table."""
    changed = copy.deepcopy(data)
    changed.setdefault(table, {})[key] = value
    return changed


def limit(data: dict) -> float:
    return worked(data)["lap"]["answer"]["elastic_limit_load"]


# ------------------------------------------------------------------------------------------------------------------- a change

def test_a_change_never_changes_the_repair_it_is_given():
    before = copy.deepcopy(EXAMPLE)
    change_repair(EXAMPLE, RepairChange(action="set", quantity="step_length", value=15))
    change_repair(EXAMPLE, RepairChange(action="add_steps", count=1))
    preview_change(EXAMPLE, RepairChange(action="regroup", count=2))
    assert EXAMPLE == before


@pytest.mark.parametrize("quantity, table, key, value", [
    ("step_length", "steps", "length", 15.0), ("bondline", "adhesive", "thickness", 0.15), ("load", "applied", "load", 120.0),
    ("damage", "damage", "diameter", 30.0), ("cover_overlap", "cover", "overlap", 20.0),
])
def test_a_value_set_writes_the_file_a_hand_edit_writes(quantity, table, key, value):
    assert change_repair(EXAMPLE, RepairChange(action="set", quantity=quantity, value=value)) == edited(EXAMPLE, table, key, value)


def test_a_value_in_another_unit_is_converted_into_the_files_unit():
    changed = change_repair(EXAMPLE, RepairChange(action="set", quantity="step_length", value=0.5, unit="in"))
    assert changed["steps"]["length"] == 12.7  # 0.5 in is 12.7 mm exactly, and the file says so without the conversion's last bits
    changed = change_repair(EXAMPLE, RepairChange(action="set", quantity="load", value=685, unit="lb/in"))
    assert changed["applied"]["load"] == pytest.approx(685 * LBF / INCH / 1e3, rel=1e-11)  # N/mm
    inches = {**copy.deepcopy(EXAMPLE), "units": "US"}  # the same table read in inches: only the conversion is looked at
    assert change_repair(inches, RepairChange(action="set", quantity="step_length", value=12.7, unit="mm"))["steps"]["length"] == 0.5
    assert tidy(0.1 + 0.2) == 0.3 and 0.1 + 0.2 != 0.3  # what tidy is for: the last bits of a conversion


def test_a_load_is_set_on_a_repair_that_states_none():
    bare = {key: value for key, value in copy.deepcopy(EXAMPLE).items() if key != "applied"}
    changed = change_repair(bare, RepairChange(action="set", quantity="load", value=80))
    assert changed["applied"] == {"load": 80} and "applied" not in bare
    assert "is set to 80 N/mm" in preview_change(bare, RepairChange(action="set", quantity="load", value=80))["words"]


def test_a_unit_of_the_wrong_kind_and_a_value_of_nothing_are_refused():
    with pytest.raises(RepairError, match="psi is not a length unit"):
        change_repair(EXAMPLE, RepairChange(action="set", quantity="step_length", value=5, unit="psi"))
    with pytest.raises(RepairError, match="unknown unit 'furlong'"):
        change_repair(EXAMPLE, RepairChange(action="set", quantity="step_length", value=5, unit="furlong"))
    with pytest.raises(RepairError, match="must be more than zero"):
        change_repair(EXAMPLE, RepairChange(action="set", quantity="bondline", value=0))
    with pytest.raises(RepairError, match="belongs to a patch bonded on top"):
        change_repair(EXAMPLE, RepairChange(action="set", quantity="patch_overlap", value=3))
    with pytest.raises(RepairError, match="no cover plies: a patch bonded on top has none"):
        change_repair(EXTERNAL, RepairChange(action="set", quantity="cover_overlap", value=3))


def test_a_change_states_one_thing():
    for wrong in (dict(action="set", quantity="load"), dict(action="set", value=3.0), dict(action="set", quantity="load", value=1.0, count=2),
                  dict(action="add_steps"), dict(action="add_steps", count=0), dict(action="add_steps", count=1, value=2.0),
                  dict(action="remove_steps", count=1, angles=(0,)), dict(action="add_steps", count=1, angles=(200,)),
                  dict(action="set", quantity="width", value=3.0), dict(action="set", quantity="load", value=float("nan"))):
        with pytest.raises(ValidationError):
            RepairChange(**wrong)


def test_steps_of_a_flush_repair_that_takes_the_angles_removed():
    more = change_repair(EXAMPLE, RepairChange(action="add_steps", count=1))
    assert more == edited(EXAMPLE, "steps", "count", 5) and "patch" not in more
    assert worked(more)["patch_layup"] == [90, 90, -45, 0, 45]  # the fifth ply from the top face is the second 90
    assert change_repair(EXAMPLE, RepairChange(action="remove_steps", count=1)) == edited(EXAMPLE, "steps", "count", 3)
    assert change_repair(EXAMPLE, RepairChange(action="set_steps", count=2)) == edited(EXAMPLE, "steps", "count", 2)
    with pytest.raises(RepairError, match="takes the angles of the plies its steps remove"):
        change_repair(EXAMPLE, RepairChange(action="add_steps", count=1, angles=(0,)))
    with pytest.raises(RepairError, match="at least one must stay"):
        change_repair(EXAMPLE, RepairChange(action="remove_steps", count=4))
    with pytest.raises(RepairError, match="remove 9 plies, and the laminate has 8"):  # the reader's words, not this module's
        preview_change(EXAMPLE, RepairChange(action="add_steps", count=5))


def test_steps_of_a_flush_patch_with_its_own_plies_need_their_angles_and_go_deepest():
    own = edited(EXAMPLE, "patch", "layup", [0, 0, 0, 0])
    with pytest.raises(RepairError, match="One new step needs the angle of its ply"):
        change_repair(own, RepairChange(action="add_steps", count=1))
    more = change_repair(own, RepairChange(action="add_steps", count=1, angles=(45,)))
    assert more["patch"]["layup"] == [45, 0, 0, 0, 0] and more["steps"]["count"] == 5  # deepest ply first
    assert worked(more)["patch_layup"] == [45, 0, 0, 0, 0]
    fewer = change_repair(edited(EXAMPLE, "patch", "layup", [90, 30, 0, 45]), RepairChange(action="remove_steps", count=2))
    assert fewer["patch"]["layup"] == [0, 45] and fewer["steps"]["count"] == 2  # the two deepest go


def test_steps_of_a_patch_bonded_on_top_need_their_angles_and_go_on_top():
    assert EXTERNAL["steps"] == {"count": 3, "length": 12.5, "plies": 2}
    with pytest.raises(RepairError, match="One new step needs the angles of 2 plies"):
        change_repair(EXTERNAL, RepairChange(action="add_steps", count=1))
    with pytest.raises(RepairError, match="needs the angles of 2 plies"):
        change_repair(EXTERNAL, RepairChange(action="add_steps", count=1, angles=(0,)))
    more = change_repair(EXTERNAL, RepairChange(action="add_steps", count=1, angles=(0, 90)))
    assert more["patch"]["layup"] == [*EXTERNAL["patch"]["layup"], 0, 90] and more["steps"]["count"] == 4
    fewer = change_repair(EXTERNAL, RepairChange(action="remove_steps", count=1))
    assert fewer["patch"]["layup"] == EXTERNAL["patch"]["layup"][:4] and fewer["steps"]["count"] == 2
    preview = preview_change(EXTERNAL, RepairChange(action="add_steps", count=1, angles=(0, 0)))
    assert preview["words"] == "Four steps in place of three: the patch has eight plies, the new plies [0/0] its shortest, on top."
    assert preview["after"]["patch_plies"] == 8 and preview["after"]["patch_diameter"] == pytest.approx(preview["before"]["patch_diameter"] + 2 * 12.5)


def test_the_same_plies_regrouped():
    two = change_repair(EXAMPLE, RepairChange(action="regroup", count=2))
    assert two["steps"] == {"count": 2, "length": 12.5, "plies": 2}
    assert change_repair(two, RepairChange(action="regroup", count=1))["steps"] == {"count": 4, "length": 12.5, "plies": 1}
    assert change_repair(EXTERNAL, RepairChange(action="regroup", count=3))["steps"] == {"count": 2, "length": 12.5, "plies": 3}
    with pytest.raises(RepairError, match="4 plies cannot be grouped in steps of 3: steps of 1, 2, 4 divide them"):
        change_repair(EXAMPLE, RepairChange(action="regroup", count=3))
    preview = preview_change(EXAMPLE, RepairChange(action="regroup", count=2))
    assert preview["words"] == "The same four plies in two steps of two plies each, in place of four steps of one ply."
    assert preview["after"]["plies_removed"] == preview["before"]["plies_removed"] == 4


def test_a_preview_is_the_hand_calculation_of_both_files():
    preview = preview_change(EXAMPLE, RepairChange(action="set", quantity="step_length", value=15))
    before, after = worked(EXAMPLE), worked(edited(EXAMPLE, "steps", "length", 15.0))
    assert preview["repair"] == edited(EXAMPLE, "steps", "length", 15.0)
    for summary, report in ((preview["before"], before), (preview["after"], after)):
        answer = report["lap"]["answer"]
        assert summary["elastic_limit_load"] == answer["elastic_limit_load"]
        assert summary["peak_shear"]["value"] == abs(answer["peak_shear"]["value"])
        assert summary["peak_shear"]["name"] == report["lap"]["steps"][answer["peak_shear"]["step"] - 1]["name"]
        assert summary["repair_diameter"] == report["sizes"]["repair_diameter"] and summary["load"] == 100.0
    assert preview["words"] == "The step length goes from 12.5 mm to 15 mm."
    assert preview["units"] == after["units"] and preview["change"]["quantity"] == "step_length"
    assert preview["after"]["repair_diameter"] == pytest.approx(preview["before"]["repair_diameter"] + 2 * 3 * 2.5)  # three ledges, each 2.5 mm longer, both sides


def test_a_preview_says_the_unit_as_written_and_refuses_in_the_readers_words():
    assert preview_change(EXAMPLE, RepairChange(action="set", quantity="step_length", value=0.5, unit="in"))["words"] == \
        "The step length goes from 12.5 mm to 12.7 mm (0.5 in as written)."
    with pytest.raises(RepairError, match="must be thinner than the plies of one step"):
        preview_change(EXAMPLE, RepairChange(action="set", quantity="bondline", value=0.2))
    words = preview_change(EXAMPLE, RepairChange(action="add_steps", count=1))["words"]
    assert words == ("Five steps in place of four: the cut goes five plies deep, and three plies of the laminate's eight are left under the patch; "
                     "the patch takes the angles of the plies removed.")
    through = preview_change(EXAMPLE, RepairChange(action="set_steps", count=6))["words"]
    assert "six plies deep, and two plies of the laminate's eight are left" in through


def test_the_model_is_linear_in_the_load():
    """Not the engine's own number set against itself: a linear model's stress grows with the load and its limit load does not move."""
    preview = preview_change(EXAMPLE, RepairChange(action="set", quantity="load", value=150))
    assert preview["after"]["peak_shear"]["value"] == pytest.approx(1.5 * preview["before"]["peak_shear"]["value"], rel=1e-12)
    assert preview["after"]["elastic_limit_load"] == pytest.approx(preview["before"]["elastic_limit_load"], rel=1e-12)
    assert preview["before"]["elastic_limit_load"] == pytest.approx(100 * 30 / preview["before"]["peak_shear"]["value"], rel=1e-12)  # load x strength / peak


# -------------------------------------------------------------------------------------------------------------------- a sweep

def test_round_increments_and_values():
    assert round_increment(22.5) == 1.0 and round_increment(0.18) == 0.01 and round_increment(26.0) == 2.0 and round_increment(240.0) == 10.0
    assert round_increment(0.9) == 0.05 and round_increment(55.0) == 2.5
    assert round_values(2.5, 25.0) == [float(n) for n in range(3, 26)]
    assert round_values(0.02, 0.2) == [round(0.01 * n, 2) for n in range(2, 21)]
    assert round_values(4.0, 30.0) == [float(n) for n in range(4, 31, 2)]
    for span in (0.0137, 0.9, 7.0, 22.5, 480.0, 12345.0):
        assert span / round_increment(span) <= 24 * (1 + 1e-9) and span / round_increment(span) > 9.5


def test_a_sweeps_rows_are_the_hand_calculation_at_each_value():
    sweep = sweep_repair(EXAMPLE, RepairSweep(quantity="step_length", start=2, end=20))
    values = [row["value"] for row in sweep["rows"]]
    assert values == [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 12.5, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0]
    assert [row["value"] for row in sweep["rows"] if row["current"]] == [12.5]
    for row in sweep["rows"]:
        report = worked(edited(EXAMPLE, "steps", "length", row["value"]))
        assert row["refused"] is None and row["elastic"] is None
        assert row["elastic_limit_load"] == report["lap"]["answer"]["elastic_limit_load"]
        assert row["peak_shear"]["value"] == abs(report["lap"]["answer"]["peak_shear"]["value"])
        assert row["repair_diameter"] == report["sizes"]["repair_diameter"]
    assert sweep["pick"] is None and sweep["picked"] is None and sweep["target"] is None and sweep["load"] == 100.0
    assert sweep["quantity"] == {"name": "step_length", "words": "the step length", "unit": "mm"}


def test_the_examples_limit_load_goes_flat_in_the_step_length():
    """The numbers ADR-0136 quotes, by the hand calculation called directly on files edited here."""
    at = {length: limit(edited(EXAMPLE, "steps", "length", length)) for length in (0.5, 2.0, 4.0, 8.0, 10.0, 20.0)}
    assert [shown(at[length]) for length in (0.5, 2.0, 4.0, 8.0, 10.0, 20.0)] == ["172.4", "216.8", "233.5", "238.2", "238.5", "238.6"]
    assert all(shown(limit(edited(EXTERNAL, "steps", "length", length))) == "142.2" for length in (2.0, 5.0, 12.5, 25.0))
    grouped = [limit({**copy.deepcopy(EXAMPLE), "steps": {"count": 4 // plies, "length": 12.5, "plies": plies}}) for plies in (4, 2, 1)]
    assert [shown(value) for value in grouped] == ["144.1", "178.9", "238.5"]
    assert shown(limit(edited(EXAMPLE, "adhesive", "thickness", 0.15))) == "292.1"
    sweep = sweep_repair(EXAMPLE, RepairSweep(quantity="step_length"))
    assert sweep["flat_from"]["value"] == 6.0 and not sweep["flat_from"]["every_row"]
    assert sweep["words"][-1] == "From 6 mm up the limit load stays within 1 % of 238.6 N/mm: past it, the step length no longer changes it."
    assert sweep_repair(EXTERNAL, RepairSweep(quantity="step_length"))["flat_from"] == {"value": 3.0, "elastic_limit_load": pytest.approx(142.2197, abs=1e-3), "every_row": True}
    assert sweep_repair(EXAMPLE, RepairSweep(quantity="bondline"))["flat_from"] is None  # still rising at the end of its range


def test_the_pick_is_the_smallest_repair_whose_adhesive_is_still_elastic():
    sweep = sweep_repair(EXAMPLE, RepairSweep(quantity="step_length", load=230))
    rows = sweep["rows"]
    assert sweep["target"] == 230 and rows[sweep["pick"]]["value"] == 4.0
    assert [row["value"] for row in rows if row["elastic"] is False] == [3.0] and rows[-1]["refused"] and rows[-1]["elastic"] is None
    assert all(row["elastic"] == (row["elastic_limit_load"] >= 230) for row in rows if row["refused"] is None)
    assert sweep["picked"] == edited(EXAMPLE, "steps", "length", 4.0)
    assert rows[sweep["pick"]]["repair_diameter"] == min(row["repair_diameter"] for row in rows if row["elastic"])
    assert ("The smallest of these whose adhesive is still elastic at 230 N/mm: a step length of 4 mm, the repair 74 mm across. "
            "Its adhesive reaches its elastic limit at 233.5 N/mm.") in sweep["words"]
    assert "1 of them could not be worked. At 25 mm: The repair is 0.2 m across" in sweep["words"][1]


def test_a_load_nothing_reaches_names_the_most_and_no_pick():
    sweep = sweep_repair(EXAMPLE, RepairSweep(quantity="step_length", load=300))
    assert sweep["pick"] is None and sweep["picked"] is None and not any(row["elastic"] for row in sweep["rows"])
    assert sweep["words"][2].startswith("None of these keeps the adhesive elastic at 300 N/mm. The most is 238.6 N/mm")
    assert sweep["most"]["elastic_limit_load"] == max(row["elastic_limit_load"] for row in sweep["rows"] if row["refused"] is None)


def test_a_load_in_its_own_unit_and_a_range_in_its_own():
    sweep = sweep_repair(EXAMPLE, RepairSweep(quantity="step_length", start=0.1, end=1, unit="in", load=1300, load_unit="lb/in"))
    assert sweep["target"] == pytest.approx(1300 * LBF / INCH / 1e3, rel=1e-11) and sweep["rows"][0]["value"] == 2.54 and sweep["rows"][-1]["value"] == 25.4
    assert sweep["rows"][sweep["pick"]]["value"] == 3.0  # 227.7 N/mm asked; 3 mm gives 228.1


def test_a_pick_at_the_start_of_the_range_says_a_smaller_value_was_not_tried():
    sweep = sweep_repair(EXTERNAL, RepairSweep(quantity="step_length", load=140))
    assert sweep["pick"] == 0 and "It is the first value of the range: a smaller one was not tried." in sweep["words"]
    assert "over this whole range, the step length no longer changes it" in sweep["words"][-1]


def test_a_quantity_that_leaves_the_size_picks_the_nearest_to_the_repair_as_it_stands():
    sweep = sweep_repair(EXAMPLE, RepairSweep(quantity="bondline", load=260))
    assert sweep["rows"][sweep["pick"]]["value"] == 0.12  # thicker than it stands, and the thinnest that is
    assert sweep["words"][2].startswith("The nearest of these to the repair as it stands whose adhesive is still elastic at 260 N/mm: a bondline of 0.12 mm.")
    assert [row["value"] for row in sweep["rows"] if row["refused"]] == [0.19, 0.2]  # thicker than a ply: the reader refuses them
    already = sweep_repair(EXAMPLE, RepairSweep(quantity="bondline", load=200))
    assert already["rows"][already["pick"]]["current"]  # elastic at 200 N/mm as it stands: the pick is the repair itself


def test_the_number_of_steps_is_swept_over_every_grouping_of_the_same_plies():
    sweep = sweep_repair(EXAMPLE, RepairSweep(quantity="steps", load=170))
    assert [(row["value"], row["plies_per_step"], row["current"]) for row in sweep["rows"]] == [(1, 4, False), (2, 2, False), (4, 1, True)]
    assert sweep["rows"][sweep["pick"]]["value"] == 2 and sweep["picked"]["steps"] == {"count": 2, "length": 12.5, "plies": 2}
    assert sweep["words"][0] == "The same 4 plies grouped in 1, 2 and 4 steps, each worked by hand under 100 N/mm."
    assert "2 steps of 2 plies, the repair 75 mm across" in sweep["words"][1] and sweep["flat_from"] is None
    for row in sweep["rows"]:
        assert row["elastic_limit_load"] == limit({**copy.deepcopy(EXAMPLE), "steps": {"count": row["value"], "length": 12.5, "plies": row["plies_per_step"]}})
    assert [row["value"] for row in sweep_repair(EXTERNAL, RepairSweep(quantity="steps"))["rows"]] == [1, 2, 3, 6]


def test_what_a_sweep_refuses():
    bare = {key: value for key, value in copy.deepcopy(EXAMPLE).items() if key != "applied"}
    with pytest.raises(RepairError, match="A sweep needs a load per unit width"):
        sweep_repair(bare, RepairSweep(quantity="step_length"))
    no_strength = copy.deepcopy(EXAMPLE)
    del no_strength["adhesive"]["shear_strength"]
    with pytest.raises(RepairError, match="needs the adhesive's shear strength"):
        sweep_repair(no_strength, RepairSweep(quantity="step_length", load=200))
    assert sweep_repair(no_strength, RepairSweep(quantity="step_length"))["rows"][0]["elastic_limit_load"] is None  # a table without limit loads
    with pytest.raises(RepairError, match="a flush patch fills its cut"):
        sweep_repair(EXAMPLE, RepairSweep(quantity="patch_overlap"))
    with pytest.raises(RepairError, match="it has no cover plies"):
        sweep_repair(EXTERNAL, RepairSweep(quantity="cover_overlap"))
    with pytest.raises(RepairError, match="No value of the range could be worked"):
        sweep_repair(EXAMPLE, RepairSweep(quantity="bondline", start=0.5, end=1))
    for wrong in (dict(quantity="step_length", start=5), dict(quantity="step_length", start=9, end=3), dict(quantity="steps", start=1, end=4),
                  dict(quantity="step_length", unit="mm"), dict(quantity="step_length", load_unit="N/mm"), dict(quantity="load"),
                  dict(quantity="step_length", load=0), dict(quantity="step_length", start=-1, end=3)):
        with pytest.raises(ValidationError):
            RepairSweep(**wrong)


def test_where_the_limit_load_goes_flat_on_rows_written_out_here():
    def rows(limits, values=None):
        values = values or list(range(1, len(limits) + 1))
        return [{"value": float(v), "refused": None, "elastic_limit_load": load} for v, load in zip(values, limits)]

    assert _flat_from(rows([50, 80, 95, 99.5, 100, 100])) == {"value": 4.0, "elastic_limit_load": 100, "every_row": False}
    assert _flat_from(rows([99.2, 99.9, 100, 100])) == {"value": 1.0, "elastic_limit_load": 100, "every_row": True}
    assert _flat_from(rows([10, 20, 30, 40, 50])) is None  # rising to the end
    assert _flat_from(rows([10, 50, 90, 99.5, 100], [1, 2, 3, 9.9, 10])) is None  # near only because the last two values are close
    assert _flat_from(rows([100, 100])) is None  # too few rows to say
    mixed = rows([50, 99.5, 100]) + [{"value": 4.0, "refused": "does not fit", "elastic_limit_load": None}]
    assert _flat_from(mixed) == {"value": 2.0, "elastic_limit_load": 100, "every_row": False}
    assert _flat_from(rows([50, 98.9, 100])) is None  # 1.1 % off: not within 1 %


def test_numbers_in_a_sentence_have_four_figures_and_no_exponent():
    assert [shown(value) for value in (238.53884, 12.5766, 0.12, 74.0, 12345.6, 0.000123456, -3.14159, 0)] == \
        ["238.5", "12.58", "0.12", "74", "12346", "0.0001235", "−3.142", "0"]
    assert math.isclose(float(shown(1 / 3)), 1 / 3, rel_tol=1e-3)


# ---- the pick held to a solved slice: the slice's report is the fea package's, written out here in what the check reads

def solved_slice(**changes) -> dict:
    report = {"units": {"length": "mm", "stress": "MPa", "force": "N/mm"}, "load": 100.0, "elastic_limit_load": 260.8, "peel_limit_load": None,
              "bond": {"peak_shear": {"value": -11.5, "r": 37.3, "part": "Adhesive on the ledge of step 2"}, "peak_peel": {"value": 4.112, "r": 62.4, "part": "Adhesive under the cover plies"}},
              "first": {"what": "adhesive", "load": 260.8}, "first_ply": {"name": "Laminate ply 6 (-45°)", "load": 466.1, "kind": "parent"}}
    return report | changes


def test_a_pick_is_held_by_its_slice_when_what_comes_first_there_is_at_or_above_the_load_named():
    held = pick_check(230.0, solved_slice())
    assert held["state"] == "solved" and held["holds"] is True and held["first"] == {"what": "adhesive", "load": 260.8}
    assert held["peak_shear"]["value"] == -11.5 and held["first_ply"] == {"name": "Laminate ply 6 (-45°)", "load": 466.1}
    assert held["words"] == ["The pick solved as a slice under 100 N/mm: largest bondline shear 11.5 MPa, largest peel stress 4.112 MPa.",
                             "As the load grows, the adhesive reaches its elastic limit in shear first, at 260.8 N/mm.",
                             "That is at or above the 230 N/mm named: the slice holds the pick."]
    assert pick_check(260.8, solved_slice())["holds"] is True, "at the load itself the adhesive is still elastic"
    below = pick_check(261.0, solved_slice())
    assert below["holds"] is False and below["words"][-1] == "That is below the 261 N/mm named: the slice does not hold the pick."


def test_what_the_hand_calculation_does_not_hold_can_come_first_in_the_slice():
    peel = pick_check(230.0, solved_slice(peel_limit_load=180.0, first={"what": "peel", "load": 180.0}))
    assert peel["holds"] is False and peel["peel_limit_load"] == 180.0
    assert peel["words"][1] == "As the load grows, the bondline's peel stress reaches the peel strength first, at 180 N/mm."
    ply = pick_check(230.0, solved_slice(first={"what": "ply", "load": 150.0}))
    assert ply["words"][1] == "As the load grows, a ply reaches a strength (Laminate ply 6 (-45°)) first, at 150 N/mm."
    none = pick_check(230.0, solved_slice(first=None, first_ply=None, elastic_limit_load=None))
    assert none["holds"] is None and none["first_ply"] is None and "not checked" in none["words"][-1]
    for words in (peel["words"], ply["words"], none["words"]):
        assert not re.search(r"strength of the repair|repair's strength|carr|margin|design", " ".join(words))
