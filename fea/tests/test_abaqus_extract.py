"""The ODB extraction script's plain parts, run under ordinary Python: section points, the choice per layer, the CSV layout the report
parser reads back, the reactions file, and the refusals (ADR-0045). The script itself runs under `abaqus python`; `test_abaqus.py` runs it."""

import importlib.util
import sys
from pathlib import Path

import pytest

from anisotropy_fea.abaqus import EXTRACT_SCRIPT, AbaqusError, read_reactions
from anisotropy_fea.abaqus_report import read_field_report


def load_script():
    """The script as a module: it lives in tools/, not in the package, and its dataclasses need it registered under its name."""
    spec = importlib.util.spec_from_file_location("abaqus_extract_fields", EXTRACT_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


X = load_script()
SNEG_1 = X.SectionPoint(1, "SNEG, (fraction = -1.0), Layer = 1", "SNEG", -1.0, 1)
SPOS_10 = X.SectionPoint(30, "SPOS, (fraction = 1.0), Layer = 10", "SPOS", 1.0, 10)


def test_both_spellings_of_a_section_point_are_read():
    assert X.parse_section_point(1, "SNEG, (fraction = -1.0), Layer = 1") == SNEG_1
    inside = X.parse_section_point(2, "fraction = -0.900000, Layer = 1")
    assert (inside.face, inside.fraction, inside.layer) == ("", -0.9, 1)
    top = X.parse_section_point(30, " SPOS, (fraction = 1.0), Layer = 10 ")
    assert (top.face, top.layer, top.description) == ("SPOS", 10, "SPOS, (fraction = 1.0), Layer = 10")
    with pytest.raises(X.ExtractError, match="not 'FACE"):
        X.parse_section_point(3, "Layer = 1")


def test_the_category_names_the_elset_cae_prints_as_section_name():
    assert X.category_elset("shell < composite > < elset = ASSEMBLY_CFRP-COUPON-1_COMPOSITELAYUP-1-1 >") == "ASSEMBLY_CFRP-COUPON-1_COMPOSITELAYUP-1-1"
    assert X.category_elset("solid < homogeneous >") == ""


def test_one_point_per_layer_needs_no_rule_and_several_need_one():
    assert X.choose_layer_points({1: SNEG_1, 30: SPOS_10}, None) == {1: SNEG_1, 10: SPOS_10}
    three = {1: SNEG_1, 2: X.SectionPoint(2, "fraction = -0.900000, Layer = 1", "", -0.9, 1), 3: X.SectionPoint(3, "fraction = -0.800000, Layer = 1", "", -0.8, 1), 30: SPOS_10}
    with pytest.raises(X.ExtractError, match="layer 1: 3.*--layer-point"):
        X.choose_layer_points(three, None)
    assert X.choose_layer_points(three, "bottom")[1] is three[1]
    assert X.choose_layer_points(three, "middle")[1] is three[2]
    assert X.choose_layer_points(three, "top")[1] is three[3]
    assert X.choose_layer_points(three, "top")[10] is SPOS_10  # a layer with one point keeps it under any rule
    two = {1: SNEG_1, 3: three[3], 30: SPOS_10}
    with pytest.raises(X.ExtractError, match="none inside it"):
        X.choose_layer_points(two, "middle")
    with pytest.raises(X.ExtractError, match="--layer-point must be one of"):
        X.choose_layer_points(three, "centre")


def test_picking_a_step_an_instance_and_a_frame():
    assert X.pick_one("step", ["Step-1"], None) == "Step-1"
    assert X.pick_one("instance", ["A-1", "B-1"], "B-1") == "B-1"
    with pytest.raises(X.ExtractError, match="holds 2 instances.*--instance"):
        X.pick_one("instance", ["A-1", "B-1"], None)
    with pytest.raises(X.ExtractError, match="not in the ODB"):
        X.pick_one("step", ["Step-1"], "Step-2")
    frames = ["Increment      0: Step Time =    0.000", "Increment      1: Step Time =    1.000"]
    assert X.pick_frame(frames, None) == 1 and X.pick_frame(frames, -1) == 1 and X.pick_frame(frames, 0) == 0
    with pytest.raises(X.ExtractError, match="3 frames.*--frame"):
        X.pick_frame(frames + ["Increment      2: Step Time =    2.000"], None)
    with pytest.raises(X.ExtractError, match="not in the step"):
        X.pick_frame(frames, 2)


def test_numbers_are_short_and_stable():
    assert X.number(15749.296875) == "15749.2969" and X.number(0.0) == "0" and X.number(-5196.42) == "-5196.42"
    assert float(X.number(1.0e-9)) == pytest.approx(1.0e-9)
    assert X.centroid([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]) == (0.5, 0.5, 0.0)
    with pytest.raises(X.ExtractError, match="quote"):
        X.quoted('a "name"')


def synthetic() -> "X.OdbData":
    """Two S4R elements of a ten-layer symmetric layup, stresses at the outer faces only, as the default field output holds."""
    data = X.OdbData(odb="C:/temp/Job-2.odb", solver="Abaqus/Standard 2025", created="Sat Oct 24 22:13:38 2026", step="Step-1",
                     frame="Increment      1: Step Time =    1.000", frame_index=1, instance="CFRP-COUPON-1", element_type="S4R",
                     component_labels=("S11", "S22", "S33", "S12"))
    category = "shell < composite > < elset = ASSEMBLY_CFRP-COUPON-1_COMPOSITELAYUP-1-1 >"
    for label, xy in ((3, (2.5, 7.5)), (8, (7.5, 12.5))):
        data.centroids[label] = (xy[0], xy[1], 0.0)
        data.categories[label] = category
        data.sections[label] = X.category_elset(category)
        data.materials[label] = ["X840-Z60"] * 10
    data.points = {1: SNEG_1, 30: SPOS_10}
    data.values[(8, 1)] = ({"S11": -12.25, "S22": 1234.5, "S33": 0.0, "S12": 3.0}, 1240.0)
    data.values[(3, 30)] = ({"S11": -5.0, "S22": 56.0, "S33": 0.0, "S12": 0.5}, 58.0)
    data.values[(3, 1)] = ({"S11": -5.0, "S22": 56.0, "S33": 0.0, "S12": -0.5}, 58.0)
    data.values[(8, 30)] = ({"S11": -12.25, "S22": 1234.5, "S33": 0.0, "S12": -3.0}, 1240.0)
    data.reactions = [("", 2, (5.0, 80.0, 0.0), (-2.7e-9, 105914.94, 0.0)), ("", 1, (5.0, 0.0, 0.0), (-6.8e-10, -105914.94, 0.0))]
    return data


def test_the_reports_round_trip_through_the_parser(tmp_path):
    data = synthetic()
    rows, chosen, notes = X.build_reports(data, ("S11", "S22", "S12", "Mises"), None)
    assert notes == [] and sorted(chosen) == [1, 10]
    assert [row[4:6] for row in rows["S22"]] == [["3", "1"], ["3", "1"], ["8", "1"], ["8", "1"]]  # element order, then section point
    digests = {}
    for quantity in rows:
        path = tmp_path / f"Job-2-{quantity}.csv"
        digests[quantity] = X.write_csv(path, X.HEADER + (f"S-{quantity}",), rows[quantity])
        assert b"\r\n" not in path.read_bytes()
        assert X.write_csv(path, X.HEADER + (f"S-{quantity}",), rows[quantity]) == digests[quantity]  # the same file every time
    header = (tmp_path / "Job-2-S22.csv").read_text(encoding="utf-8").splitlines()[0]
    assert header == "ODB Name,Step,Frame,Part Instance Name,Element Label,IntPt,X,Y,Z,Section Name,Material Name,Section Point,S-S22"
    s22 = read_field_report(tmp_path / "Job-2-S22.csv")
    assert (s22.instance, s22.step, s22.frame, s22.odb) == ("CFRP-COUPON-1", "Step-1", "Increment      1: Step Time =    1.000", "C:/temp/Job-2.odb")
    assert s22.values == {(3, 1): 56.0, (3, 10): 56.0, (8, 1): 1234.5, (8, 10): 1234.5}
    assert s22.faces == {(3, 1): "SNEG", (3, 10): "SPOS", (8, 1): "SNEG", (8, 10): "SPOS"}
    assert s22.centroids == {3: (2.5, 7.5), 8: (7.5, 12.5)}
    s12 = read_field_report(tmp_path / "Job-2-S12.csv")
    assert s12.values[(3, 1)] == -0.5 and s12.values[(3, 10)] == 0.5
    assert read_field_report(tmp_path / "Job-2-Mises.csv").values[(8, 10)] == 1240.0
    line = (tmp_path / "Job-2-S11.csv").read_text(encoding="utf-8").splitlines()[1]
    assert line.endswith('"ASSEMBLY_CFRP-COUPON-1_COMPOSITELAYUP-1-1","X840-Z60","shell < composite > < elset = ASSEMBLY_CFRP-COUPON-1_COMPOSITELAYUP-1-1 > : SNEG, (fraction = -1.0), Layer = 1",-5')


def test_a_layer_the_section_does_not_list_leaves_the_material_empty_and_says_so():
    data = synthetic()
    data.materials[3] = ["X840-Z60"] * 5  # a layup the ODB did not mirror
    rows, _, notes = X.build_reports(data, ("S22",), None)
    assert notes == ["Material Name left empty for layers [10]: the section lists fewer layers (a layup the ODB does not mirror)"]
    assert [row[10] for row in rows["S22"] if row[4] == "3"] == ['"X840-Z60"', '""']


def test_refusals():
    data = synthetic()
    with pytest.raises(X.ExtractError, match="not one of"):
        X.build_reports(data, ("E22",), None)
    data.component_labels = ("S11", "S22", "S33")
    with pytest.raises(X.ExtractError, match="has components"):
        X.build_reports(data, ("S12",), None)
    data = synthetic()
    data.values = {}
    with pytest.raises(X.ExtractError, match="no values"):
        X.build_reports(data, ("S22",), None)


def test_the_reactions_file_round_trips(tmp_path):
    data = synthetic()
    rows = X.reaction_rows(data)
    assert [row[4] for row in rows] == ["1", "2"]  # sorted by instance, then node label
    path = tmp_path / "Job-2-RF.csv"
    X.write_csv(path, X.RF_HEADER, rows)
    reactions = read_reactions(path)
    assert reactions[("", 2)] == pytest.approx((-2.7e-9, 105914.94, 0.0)) and reactions[("", 1)][1] == pytest.approx(-105914.94)
    other = tmp_path / "other.csv"
    other.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(AbaqusError, match="not a reactions file"):
        read_reactions(other)


def test_the_script_imports_nothing_of_ours_and_odbaccess_only_where_it_reads():
    lines = Path(EXTRACT_SCRIPT).read_text(encoding="utf-8").splitlines()
    assert not [line for line in lines if line.startswith(("from anisotropy", "import anisotropy"))]
    imports = [i for i, line in enumerate(lines) if "from odbAccess import" in line]
    assert len(imports) == 1 and lines[imports[0]].startswith("    ") and any("def read_odb" in line for line in lines[: imports[0]])
