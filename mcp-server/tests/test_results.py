"""Reading a result (ADR-0107): the values are the ones the fea package wrote, picked out and never recomputed, and the extremes found
here are held to the extremes the package itself wrote in the summary of the same result."""

import pytest

from anisotropy_mcp import results
from conftest import REPO, fixture

FIELDS = fixture("fields.json")
BENDING = fixture("fields.json", REPO / "tests" / "fixtures" / "studio-bending")
STRESS = FIELDS["element"]["ply"]["stress_12"]


def test_a_value_is_the_stored_one_at_the_element_by_its_own_number_and_the_ply_from_the_bottom():
    found = results.values_at(FIELDS, 183, [4], ["S11", "S22", "S12", "E22", "Mises"])
    assert found["element"] == "183" and found["label"] == "Strip-1.183" and found["regions"] == ["Gauge"] and found["at_a_grip"] is False
    assert found["centroid"] == FIELDS["element"]["centroids"][182][:2] and found["length_unit"] == "mm"
    row, = found["rows"]
    assert (row["ply"], row["angle"], row["face"]) == (4, 90.0, None)
    assert row["values"] == {"S11": STRESS[182][3][0], "S22": STRESS[182][3][1], "S12": STRESS[182][3][2],
                             "E22": FIELDS["element"]["ply"]["strain_12"][182][3][1], "Mises": FIELDS["element"]["ply"]["mises"][182][3]}
    assert found["units"] == {"S11": "MPa", "S22": "MPa", "S12": "MPa", "Mises": "MPa", "E22": "-"}
    written = FIELDS["element"]["failure"]["tsai_hill"]
    assert row["failure"]["tsai_hill"] == {"R": written["ratio"][182][3], "index": written["index"][182][3], "mode": "interactive"}
    assert row["failure"]["max_stress"]["mode"] == "transverse tension"


def test_with_nothing_named_every_ply_and_every_quantity_the_result_holds_comes_back():
    found = results.values_at(FIELDS, 1)
    assert [row["ply"] for row in found["rows"]] == list(range(1, 9)) and list(found["rows"][0]["values"]) == list(results.COLUMNS)
    assert found["rows"][0]["values"]["Tresca"] == FIELDS["element"]["ply"]["invariants"]["tresca"][0][0]
    assert results.offer(FIELDS)["quantities"] == list(results.COLUMNS) and results.offer(FIELDS)["element_numbers"] == [1, 250]
    assert results.offer(FIELDS)["gauge_section"] is True and results.offer(FIELDS)["plies"][3] == {"ply": 4, "angle": 90.0}


def test_a_bending_result_has_both_faces_of_every_ply_and_no_quantity_it_did_not_write():
    found = results.values_at(BENDING, 1, [1], ["S11", "Tresca"])
    assert [(row["ply"], row["face"]) for row in found["rows"]] == [(1, "bottom"), (1, "top")]
    assert [row["values"]["S11"] for row in found["rows"]] == [BENDING["element"]["ply"]["stress_12"][0][0][0][0], BENDING["element"]["ply"]["stress_12"][0][0][1][0]]
    assert found["rows"][0]["values"]["Tresca"] is None and "Tresca" not in results.offer(BENDING)["quantities"]
    assert results.offer(BENDING)["faces"] == ["bottom", "top"] and results.offer(BENDING)["gauge_section"] is False
    whole = results.extremes(BENDING, ["S11"], "largest")
    assert whole["region"] == "the whole model" and whole["extremes"][0]["face"] in ("bottom", "top")
    with pytest.raises(results.NotInResult, match="hold no value of that quantity"):
        results.extremes(BENDING, ["Tresca"])


@pytest.mark.parametrize("ask, said", [
    (lambda: results.values_at(FIELDS, 251), "This model has no element 251. Its elements are numbered 1 to 250."),
    (lambda: results.values_at(FIELDS, 1, [9]), "This laminate has 8 plies, counted from the bottom face; there is no ply 9."),
    (lambda: results.values_at(FIELDS, 1, [0]), "there is no ply 0"),
    (lambda: results.values_at(FIELDS, 1, None, ["S33"]), "No quantity 'S33'. The quantities are: S11, S22, S12"),
    (lambda: results.extremes(FIELDS, ["S11"], "biggest"), "No sense 'biggest'"),
    (lambda: results.extremes(FIELDS, ["S11"], region="Middle"), "This model has no region 'Middle'. Ask for default, gauge or whole, or one of its regions: Tab-Bottom, Gauge"),
    (lambda: results.extremes(BENDING, ["S11"], region="gauge"), "This model has no gauge section between grips"),
])
def test_what_the_result_does_not_hold_is_refused_with_what_it_does_hold(ask, said):
    with pytest.raises(results.NotInResult) as refused:
        ask()
    assert said in str(refused.value)


def test_two_parts_with_an_element_of_one_number_are_not_guessed_between():
    twice = {**FIELDS, "mesh": {**FIELDS["mesh"], "element_labels": ["Tab-1.1", *FIELDS["mesh"]["element_labels"][1:]]}}
    twice["mesh"]["element_labels"][1] = "Strip-1.1"
    with pytest.raises(results.NotInResult, match="More than one part has an element 1: Tab-1.1, Strip-1.1"):
        results.values_at(twice, 1)


def test_the_gauge_section_is_the_list_the_package_wrote_with_the_result():
    """ADR-0108: the package reads the gauge section at least a quarter width from each tab line and writes the elements; the server
    takes that list and derives none."""
    gauge = results.gauge_section(FIELDS)
    grips = results.at_grips(FIELDS)
    assert gauge == FIELDS["mesh"]["gauge_elements"] and len(gauge) == FIELDS["summary"]["gauge_reading"]["elements"] == 130
    assert grips and not set(gauge) & grips and set(gauge) < set(FIELDS["mesh"]["element_sets"]["Gauge"])
    assert FIELDS["summary"]["fpf_gauge"]["tsai_hill"]["element"] in gauge and FIELDS["summary"]["verdict"]["outside_earlier"]["element"] in grips
    centroids = FIELDS["element"]["centroids"]
    narrowed = {**FIELDS, "mesh": {**FIELDS["mesh"], "gauge_elements": [e for e in gauge if 66 < centroids[e][1] < 184]}}
    assert 0 < len(results.gauge_section(narrowed)) < len(gauge)  # a finer mesh leaves out more than the row at the grips
    found = results.extremes(narrowed, ["S22"], "largest", "gauge")
    assert found["elements"] == len(narrowed["mesh"]["gauge_elements"])
    assert results.gauge_section({**FIELDS, "mesh": {**FIELDS["mesh"], "gauge_elements": None}}) is None  # the package wrote that there is none


def test_a_result_solved_before_the_list_is_read_by_its_own_rule():
    """A result from before ADR-0108 holds no list: its gauge section is the `Gauge` set less the elements at a gripped node (ADR-0085),
    the rule its own summary was written by."""
    older = {**FIELDS, "mesh": {k: v for k, v in FIELDS["mesh"].items() if k != "gauge_elements"}}
    gauge = results.gauge_section(older)
    assert set(gauge) == set(FIELDS["mesh"]["element_sets"]["Gauge"]) - results.at_grips(FIELDS) and len(gauge) == 130
    assert results.gauge_section(BENDING) is None


def test_each_plys_extreme_in_the_gauge_section_is_the_one_the_package_wrote_in_the_summary():
    """The package's own extremes (`summary.ply_extremes`, the gauge section), ply by ply: the same value, to the digits the fields carry,
    for the largest S11 and S22, the most compressive where there is compression, and the largest |S12| and Mises. The element is not
    compared: across a uniform gauge section many elements hold one value to those digits, and the first in the mesh's order is named
    here, as on the page (`tests/result-question.test.ts` holds the page to the same extremes)."""
    written = {row["ply"]: row for row in FIELDS["summary"]["ply_extremes"]["plies"]}
    assert FIELDS["summary"]["ply_extremes"]["basis"] == "gauge" and len(written) == 8
    largest = results.extremes(FIELDS, ["S11", "S22", "S12", "Mises"], "largest")
    smallest = results.extremes(FIELDS, ["S11", "S22"], "smallest")
    assert largest["region"] == "the gauge section" and largest["elements"] == len(results.gauge_section(FIELDS)) == 130
    checked = 0
    for block in largest["extremes"]:
        unsigned = block["quantity"] in ("S12", "Mises")
        assert block["sense"] == ("magnitude" if unsigned else "largest")
        for row in block["per_ply"]:
            theirs = written[row["ply"]][{"Mises": "mises"}.get(block["quantity"], block["quantity"])]
            theirs = theirs["largest"] if unsigned else theirs["tension"]
            if theirs is None:
                assert row["value"] <= 0  # no tension in this ply: its largest value is not a tension
                continue
            # the largest shear is a magnitude, which two elements across the coupon's axis hold with opposite signs
            assert abs(row["value"]) == pytest.approx(abs(theirs["value"]), rel=1e-8, abs=1e-9) and (unsigned or row["value"] > 0)
            checked += 1
    for block in smallest["extremes"]:
        for row in block["per_ply"]:
            theirs = written[row["ply"]][block["quantity"]]["compression"]
            if theirs is None:
                assert row["value"] >= 0
                continue
            assert row["value"] == pytest.approx(theirs["value"], rel=1e-8)
            checked += 1
    assert checked >= 30
    overall = FIELDS["summary"]["ply_extremes"]["overall"]
    for block in largest["extremes"][:2]:
        assert block["value"] == pytest.approx(overall[block["quantity"]]["tension"]["value"], rel=1e-8)
        assert overall[block["quantity"]]["tension"]["ply"] in [block["ply"], *block["tied_plies"]]


def test_the_overall_extreme_names_its_ply_the_plies_tied_with_it_and_a_grip_when_it_sits_at_one():
    shear, = results.extremes(FIELDS, ["S12"], "largest")["extremes"]  # no sign to speak of: read by magnitude whatever is asked
    values = [abs(row["value"]) for row in shear["per_ply"]]
    assert shear["sense"] == "magnitude" and abs(shear["value"]) == max(values) and shear["ply"] == 1 and shear["angle"] == 45.0
    assert shear["tied_plies"] == [row["ply"] for row in shear["per_ply"][1:] if abs(row["value"]) == abs(shear["value"])] and shear["tied_plies"]
    assert shear["unit"] == "MPa" and shear["what"] == "in-plane shear stress" and shear["at_a_grip"] is False
    one, = results.extremes(FIELDS, ["S22"], "largest", "default", [4])["extremes"]
    assert [row["ply"] for row in one["per_ply"]] == [4] and one["tied_plies"] == []
    whole = results.extremes(FIELDS, ["S22"], "largest", "whole")
    assert whole["region"] == "the whole model" and whole["elements"] == 250 and whole["extremes"][0]["value"] >= one["value"]
    assert whole["extremes"][0]["at_a_grip"] is True and "clamped edge of a grip" in whole["grip_note"]
    tab = results.extremes(FIELDS, ["E11"], "smallest", "Tab-Top")
    assert tab["region"] == "the region Tab-Top" and tab["extremes"][0]["unit"] == "-" and tab["extremes"][0]["regions"] == ["Tab-Top"]


def test_the_first_element_in_the_meshs_order_and_the_first_ply_hold_a_tie():
    """Three elements and two plies with one value everywhere but a smaller one: the extreme is named at the first element that holds
    it and in the first ply, and the other ply is named as tied, as the page does (ADR-0100)."""
    one = {"mesh": {"element_labels": ["P-1.1", "P-1.2", "P-1.3"], "plies": 2, "angles": [0.0, 90.0], "faces": None, "quads": [[0, 1, 2, 3]] * 3,
                    "element_sets": {}, "node_sets": {}},
           "labels": {"stress": "MPa", "length": "mm"},
           "element": {"centroids": [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]], "failure": {},
                       "ply": {"stress_12": [[[1.0, 0, 0], [5.0, 0, 0]], [[5.0, 0, 0], [5.0, 0, 0]], [[5.0, 0, 0], [2.0, 0, 0]]],
                               "strain_12": [[[0, 0, 0]] * 2] * 3, "mises": [[1.0, 5.0], [5.0, 5.0], [5.0, 2.0]]}}}
    block, = results.extremes(one, ["S11"], "largest")["extremes"]
    assert [(row["ply"], row["element"], row["value"]) for row in block["per_ply"]] == [(1, "2", 5.0), (2, "1", 5.0)]
    assert (block["ply"], block["element"], block["tied_plies"], block["at_a_grip"]) == (1, "2", [2], False)
    least, = results.extremes(one, ["S11"], "smallest")["extremes"]
    assert (least["ply"], least["element"], least["value"], least["tied_plies"]) == (1, "1", 1.0, [])
    assert results.extremes(one, ["S11"])["region"] == "the whole model" and "failure" not in results.values_at(one, 2)["rows"][0]


PLATE = fixture("fields.json", REPO / "tests" / "fixtures" / "studio-plate-clamped")


def test_a_plate_with_held_corners_is_read_away_from_them_when_no_region_is_named():
    """ADR-0108 amendment 2: the elements the package wrote, none derived here; the whole model still reaches the clamped corner."""
    away = results.extremes(PLATE, ["S22"], "largest")
    assert away["region"] == "the plate away from its held corners" and away["elements"] == PLATE["summary"]["held_corners"]["elements"]
    package = PLATE["summary"]["ply_extremes"]["overall"]["S22"]["tension"]  # the package's own extreme on the answer's basis, full precision
    assert away["extremes"][0]["value"] == pytest.approx(package["value"], rel=1e-8)  # the mirror element ties at 9 digits
    whole = results.extremes(PLATE, ["S22"], "largest", "whole")
    assert whole["region"] == "the whole model" and whole["extremes"][0]["value"] > away["extremes"][0]["value"]
    older = {**PLATE, "mesh": {key: value for key, value in PLATE["mesh"].items() if key != "away_elements"}}
    assert results.extremes(older, ["S22"], "largest")["region"] == "the whole model"
