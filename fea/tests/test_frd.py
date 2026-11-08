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
    assert beside["reaction"]["calculix"] == pytest.approx(16162.16) and beside["reaction"]["ours"] == pytest.approx(16212, rel=1e-3)
    assert beside["reaction"]["difference"].startswith("+0.3") and beside["reaction"]["agrees"] is True
    assert beside["gauge_element"] == "Coupon-1.626" and [g["ply"] for g in beside["gauge"]] == [1, 2, 3, 4, 5, 6, 7, 8]
    ply4 = beside["gauge"][3]
    assert ply4["calculix"][0] == pytest.approx(1180.67, abs=0.01) and ply4["ours"][0] == pytest.approx(1180.67, rel=2e-3) and all(ply4["agrees"])
    inches = calculix_summary(record, "in-psi")
    assert inches["reaction"]["calculix"] == pytest.approx(16162.16 / 4.4482216152605, rel=1e-6)  # N to lbf
    assert inches["gauge"][3]["calculix"][0] == pytest.approx(1180.67 / 6.894757293168e-3, rel=1e-4)  # MPa to psi
