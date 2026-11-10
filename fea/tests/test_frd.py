"""The .frd reader (ADR-0030 amendment 6): the node and stress blocks of a hand-written file, the viewer's von Mises, the extremes with
their nodes and positions, the gauge rows; and, with CalculiX present, the public coupon's own .frd read after a run."""

import math
from pathlib import Path

import pytest

from anisotropy_fea.frd import AXES, FrdError, frd_peaks, read_frd, von_mises

# Two nodes on the tab line and two in the gauge, as CalculiX writes them: ` -1`, the node in 10 columns, the values in 12 each.
TINY = """    1C
    1UCalculiX deck written by hand for the test
    2C                             4                                     1
 -1         1 0.00000E+00 0.00000E+00 0.00000E+00
 -1         2 2.50000E+01 5.70000E+01 0.00000E+00
 -1         3 1.25000E+01 1.25000E+02 0.00000E+00
 -1         4 2.50000E+01 1.25000E+02 7.31520E-01
 -3
    3C                             1                                     1
 -1         1    4    0    1
 -2         1         2         3         4
 -3
    1PSTEP                         1           1           1
  100CL  101 1.000000000           4                     0    1           1
 -4  DISP        4    1
 -5  D1          1    2    1    0
 -5  D2          1    2    2    0
 -5  D3          1    2    3    0
 -5  ALL         1    2    0    0    1ALL
 -1         1 0.00000E+00 0.00000E+00 0.00000E+00
 -1         2 1.00000E-02 2.00000E-01 0.00000E+00
 -1         3 0.00000E+00 5.00000E-01 0.00000E+00
 -1         4 0.00000E+00 5.00000E-01 0.00000E+00
 -3
    1PSTEP                         2           1           1
  100CL  101 1.000000000           4                     0    1           1
 -4  STRESS      6    1
 -5  SXX         1    4    1    1
 -5  SYY         1    4    2    2
 -5  SZZ         1    4    3    3
 -5  SXY         1    4    1    2
 -5  SYZ         1    4    2    3
 -5  SZX         1    4    3    1
 -1         1 0.00000E+00 0.00000E+00 0.00000E+00 0.00000E+00 0.00000E+00 0.00000E+00
 -1         2 1.07000E+01 1.58350E+03-4.10000E+00-1.31000E+01 0.00000E+00 0.00000E+00
 -1         3-4.63300E+02 1.19600E+03 0.00000E+00 4.42000E+01 0.00000E+00 0.00000E+00
 -1         4 4.28200E+02 1.10000E+03 0.00000E+00 0.00000E+00 0.00000E+00 0.00000E+00
 -3
 9999
"""


def test_the_tiny_frd_is_read_node_by_node(tmp_path):
    path = tmp_path / "tiny.frd"
    path.write_text(TINY, encoding="utf-8")
    frd = read_frd(path)
    assert frd.node_count == 4 and frd.nodes[2] == (25.0, 57.0, 0.0) and frd.nodes[4] == (25.0, 125.0, 0.73152)
    assert frd.stress[2] == (10.7, 1583.5, -4.1, -13.1, 0.0, 0.0) and frd.stress[3][0] == -463.3  # a negative value touches the column before it
    assert frd.displacement[3] == (0.0, 0.5, 0.0)
    # the viewer's von Mises is the three-dimensional invariant of the nodal state: the public coupon's 1580.4 MPa at node 68861 came from this state
    assert von_mises(frd.stress[2]) == pytest.approx(1580.4, abs=0.1)
    assert von_mises((100.0, 0.0, 0.0, 0.0, 0.0, 0.0)) == pytest.approx(100.0) and von_mises((0.0, 0.0, 0.0, 10.0, 0.0, 0.0)) == pytest.approx(10.0 * math.sqrt(3))


def test_the_peaks_name_their_nodes_and_the_gauge_rows(tmp_path):
    path = tmp_path / "tiny.frd"
    path.write_text(TINY, encoding="utf-8")
    peaks = frd_peaks(read_frd(path), gauge=(70.0, 180.0))
    assert peaks["nodes"] == 4 and peaks["axes"] == AXES == "global"
    assert peaks["mises_max"] == pytest.approx(1580.4, abs=0.1) and peaks["mises_max_node"] == 2 and peaks["mises_max_xyz"] == [25.0, 57.0, 0.0]
    assert peaks["syy_max"] == 1583.5 and peaks["syy_max_node"] == 2 and peaks["syy_min"] == 0.0 and peaks["syy_min_node"] == 1
    assert peaks["sxx_max"] == 428.2 and peaks["sxx_max_node"] == 4 and peaks["sxx_min"] == -463.3 and peaks["sxx_min_node"] == 3
    assert peaks["sxy_max_abs"] == 44.2 and peaks["sxy_max_abs_node"] == 3
    assert (peaks["gauge_from"], peaks["gauge_to"], peaks["gauge_nodes"]) == (70.0, 180.0, 2)  # nodes 3 and 4 lie between the rows
    assert peaks["gauge_syy_max"] == 1196.0 and peaks["gauge_syy_max_node"] == 3 and peaks["gauge_mises_max_node"] == 3
    assert peaks["gauge_sxx_max_abs"] == -463.3  # the largest |SXX| in the gauge, with its sign
    without = frd_peaks(read_frd(path))
    assert "gauge_from" not in without and without["mises_max_node"] == 2
    for key, value in peaks.items():  # every value is a TOML scalar or a list of numbers, so the record's writer takes the block as it is
        assert isinstance(value, (int, float, str)) or (isinstance(value, list) and all(isinstance(v, float) for v in value)), key


def test_what_is_not_an_frd_is_refused(tmp_path):
    path = tmp_path / "not.frd"
    path.write_text("hello\n", encoding="utf-8")
    with pytest.raises(FrdError, match="no node block"):
        read_frd(path)
    path.write_text(TINY.split("    1PSTEP")[0], encoding="utf-8")  # nodes and elements, no results
    with pytest.raises(FrdError, match="no STRESS block"):
        read_frd(path)
    path.write_text(TINY.replace(" -1         2 1.07000E+01", " -1         2 1.07x00E+01"), encoding="utf-8")
    with pytest.raises(FrdError, match="cannot read the STRESS line"):
        read_frd(path)


def test_the_record_tools_gauge_rows_follow_the_tabs():
    from anisotropy_fea.spec import load_spec

    import importlib.util
    spec_path = Path(__file__).resolve().parents[1] / "checks" / "unnotched-im7-8552" / "unnotched-im7-8552-nodal.toml"
    module_spec = importlib.util.spec_from_file_location("record_from_dat", Path(__file__).resolve().parents[1] / "tools" / "record_from_dat.py")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    spec = load_spec(spec_path)
    rows = module.gauge_rows(spec)
    assert rows is not None and rows[0] == pytest.approx(56.0 + 0.1 * (250.0 - 112.0)) and rows[1] == pytest.approx(194.0 - 0.1 * (250.0 - 112.0))  # mm


def test_the_calculix_summary_reads_the_public_record_in_the_fields_units():
    # the public record predates the [frd] block: the reaction and the gauge plies come from its comparison, frd is None
    from anisotropy_fea.calculix_summary import calculix_summary

    record = Path(__file__).resolve().parents[1] / "checks" / "unnotched-im7-8552" / "records" / "unnotched-im7-8552-nodal-calculix.toml"
    beside = calculix_summary(record, "mm-MPa")
    assert beside["record"] == record.name and beside["units"] == "mm-MPa" and beside["tolerance"] == 0.03 and beside["frd"] is None
    assert beside["reaction"]["calculix"] == pytest.approx(16102.21) and beside["reaction"]["ours"] == pytest.approx(16212, rel=1e-3)
    assert beside["reaction"]["difference"].startswith("+0.6") and beside["reaction"]["agrees"] is True
    assert beside["gauge_element"] == "Coupon-1.626" and [g["ply"] for g in beside["gauge"]] == [1, 2, 3, 4, 5, 6, 7, 8]
    ply2 = beside["gauge"][1]  # the stated 0-degree ply, fibres along the pull (ADR-0065), carries the fibre stress
    assert ply2["calculix"][0] == pytest.approx(1180.85, abs=0.01) and ply2["ours"][0] == pytest.approx(1180.85, rel=2e-3) and all(ply2["agrees"])
    inches = calculix_summary(record, "in-psi")
    assert inches["reaction"]["calculix"] == pytest.approx(16102.21 / 4.4482216152605, rel=1e-6)  # N to lbf
    assert inches["gauge"][1]["calculix"][0] == pytest.approx(1180.85 / 6.894757293168e-3, rel=1e-4)  # MPa to psi


# Two bricks of one element in a two-ply laminate (0.5 mm plies, so the interfaces are at -0.5, 0 and 0.5), the plies unconnected: nodes 1-4
# belong to the bottom brick (z from -0.5 to 0), nodes 5-8 to the top one. The bottom ply is a stated 0-degree ply (fibres along y, so its
# sigma_1 is SYY), the top a stated 90-degree ply (fibres along x). The stress block gives every node the same global state but node 4.
PLIES = """    1C
    2C                             8                                     1
 -1         1 0.00000E+00 0.00000E+00-5.00000E-01
 -1         2 2.50000E+01 0.00000E+00-5.00000E-01
 -1         3 0.00000E+00 1.00000E+02 0.00000E+00
 -1         4 2.50000E+01 1.00000E+02 0.00000E+00
 -1         5 0.00000E+00 0.00000E+00 0.00000E+00
 -1         6 2.50000E+01 0.00000E+00 0.00000E+00
 -1         7 0.00000E+00 1.00000E+02 5.00000E-01
 -1         8 2.50000E+01 1.00000E+02 5.00000E-01
 -3
    3C                             2                                     1
 -1      1001    4    0    1
 -2         1         2         3         4
 -1      1002    4    0    1
 -2         5         6         7         8
 -3
    1PSTEP                         1           1           1
  100CL  101 1.000000000           8                     0    1           1
 -4  STRESS      6    1
 -5  SXX         1    4    1    1
 -5  SYY         1    4    2    2
 -5  SZZ         1    4    3    3
 -5  SXY         1    4    1    2
 -5  SYZ         1    4    2    3
 -5  SZX         1    4    3    1
 -1         1 1.00000E+01 4.00000E+02 0.00000E+00 3.00000E+01 0.00000E+00 0.00000E+00
 -1         2 1.00000E+01 4.00000E+02 0.00000E+00 3.00000E+01 0.00000E+00 0.00000E+00
 -1         3 1.00000E+01 4.00000E+02 0.00000E+00 3.00000E+01 0.00000E+00 0.00000E+00
 -1         4 1.00000E+01 6.00000E+02 0.00000E+00-5.00000E+01 0.00000E+00 0.00000E+00
 -1         5 1.00000E+01 4.00000E+02 0.00000E+00 3.00000E+01 0.00000E+00 0.00000E+00
 -1         6 1.00000E+01 4.00000E+02 0.00000E+00 3.00000E+01 0.00000E+00 0.00000E+00
 -1         7 1.00000E+01 4.00000E+02 0.00000E+00 3.00000E+01 0.00000E+00 0.00000E+00
 -1         8 1.00000E+01 4.00000E+02 0.00000E+00 3.00000E+01 0.00000E+00 0.00000E+00
 -3
 9999
"""


def test_the_bricks_are_read_and_their_nodes_belong_to_one_ply_each(tmp_path):
    from anisotropy_fea.frd import FrdPly, ply_of_nodes

    path = tmp_path / "plies.frd"
    path.write_text(PLIES, encoding="utf-8")
    frd = read_frd(path)
    assert frd.elements == {1001: (1, 2, 3, 4), 1002: (5, 6, 7, 8)}
    plies = [FrdPly(0.0, 90.0, 0.5), FrdPly(90.0, 0.0, 0.5)]
    assert ply_of_nodes(frd, plies) == {1: 0, 2: 0, 3: 0, 4: 0, 5: 1, 6: 1, 7: 1, 8: 1}
    tiny = tmp_path / "tiny.frd"
    tiny.write_text(TINY, encoding="utf-8")
    assert read_frd(tiny).elements == {1: (1, 2, 3, 4)}  # the older fixture's one shell element is read too


def test_each_ply_peaks_in_its_own_fibre_axes(tmp_path):
    from anisotropy_fea.frd import FrdPly, frd_ply_peaks

    path = tmp_path / "plies.frd"
    path.write_text(PLIES, encoding="utf-8")
    plies = [FrdPly(0.0, 90.0, 0.5), FrdPly(90.0, 0.0, 0.5)]
    bottom, top = frd_ply_peaks(read_frd(path), plies, gauge=(10.0, 90.0))
    # the 0-degree ply's fibres run along y: sigma_1 is SYY, sigma_2 is SXX, tau_12 is -SXY; node 4 holds its peaks
    assert bottom["ply"] == 1 and bottom["angle"] == 0.0 and bottom["fibre"] == 90.0 and bottom["nodes"] == 4
    assert bottom["s1_max"] == 600.0 and bottom["s1_max_node"] == 4 and bottom["s1_max_xyz"] == [25.0, 100.0, 0.0]
    assert bottom["s2_max"] == 10.0 and bottom["t12_max_abs"] == 50.0 and bottom["t12_max_abs_node"] == 4
    assert "gauge_s1_max" not in bottom  # node 4 sits at y = 100, outside the gauge rows; the other nodes sit at y = 0 or y = 100 too
    # the 90-degree ply's fibres run along x: sigma_1 is SXX
    assert top["ply"] == 2 and top["s1_max"] == 10.0 and top["s2_max"] == 400.0 and top["t12_max_abs"] == 30.0 and top["nodes"] == 4
    wide = frd_ply_peaks(read_frd(path), plies, gauge=(-1.0, 101.0))
    assert wide[0]["gauge_s1_max"] == 600.0 and wide[0]["gauge_s1_max_node"] == 4 and wide[1]["gauge_s1_max"] == 10.0


def test_the_record_writes_the_ply_peaks_as_inline_tables_and_the_summary_converts_them(tmp_path):
    import tomllib

    from anisotropy_fea.compare import format_record, load_record
    from anisotropy_fea.calculix_summary import calculix_summary

    public = Path(__file__).resolve().parents[1] / "checks" / "unnotched-im7-8552" / "records" / "unnotched-im7-8552-nodal-calculix.toml"
    record = load_record(public)
    for key in ("spec", "deck_kernel", "deck_reference"):  # the copy lives in tmp_path, so the paths the record states relative to itself become absolute
        record[key] = str((public.parent / record[key]).resolve())
    record["solver"]["conventions"] = str((public.parent / record["solver"]["conventions"]).resolve())
    record["frd"] = {"nodes": 8, "axes": AXES, "layers": "test", "mises_max": 1.0, "mises_max_node": 4, "mises_max_xyz": [25.0, 100.0, 0.0],
                     "plies": [{"ply": 1, "angle": 0.0, "fibre": 90.0, "nodes": 4, "s1_max": 600.0, "s1_max_node": 4, "s1_max_xyz": [25.0, 100.0, 0.0]}]}
    text = format_record(record)
    assert '\nplies = [{ply = 1, angle = 0.0, fibre = 90.0, nodes = 4, s1_max = 600.0, s1_max_node = 4, s1_max_xyz = [25.0, 100.0, 0.0]}]\n' in text
    assert tomllib.loads(text)["frd"]["plies"][0]["s1_max"] == 600.0
    path = tmp_path / "record.toml"
    path.write_text(text, encoding="utf-8")
    inches = calculix_summary(path, "in-psi")["frd"]["plies"][0]
    assert inches["s1_max"] == pytest.approx(600.0 / 6.894757293168e-3, rel=1e-6) and inches["s1_max_node"] == 4 and inches["angle"] == 0.0
    assert inches["s1_max_xyz"][0] == pytest.approx(25.0 / 25.4, rel=1e-9)
