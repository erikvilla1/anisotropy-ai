"""The `.dat` of an Abaqus run of our deck, read for the validation table (ADR-0066 amendment 1): `abaqus_dat` reads the printed tables as
Abaqus 2025 lays them out, `abaqus_summary` puts the numbers beside the kernel's at the gauge element, and `tools/abaqus_beside.py`
prints them. The `.dat` here is written in that layout from the kernel's own numbers at four figures, as Abaqus prints, so the two
agree by construction; a real run's file (`AS48552-UNT-L1-abaqus-plies.dat`, 2026-11-08) read with the same code gave 28 of 28."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from public_coupon import PUBLIC_COUPON

from anisotropy_fea.abaqus_dat import AbaqusDatError, parse_abaqus_dat
from anisotropy_fea.abaqus_reader import parse_deck
from anisotropy_fea.abaqus_summary import abaqus_beside, layer_of
from anisotropy_fea.femodel import build_model
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.model import to_si as deck_to_si
from anisotropy_fea.report import laminate_check
from anisotropy_fea.spec import parse_spec, to_si
from anisotropy_fea.units import deck_units_of, from_si
from anisotropy_fea.write_abaqus import SECTION_POINTS, write_abaqus

TOOLS = Path(__file__).parents[1] / "tools"
BANNER = """1

   Abaqus 2025                                  Date 08-Nov-2026   Time 14:13:24
   For use by A UNIVERSITY under license from Dassault Systemes or its subsidiary.
"""
OPEN_ELEMENT = "   THE FOLLOWING TABLE IS PRINTED AT THE CENTROID OF THE ELEMENT FOR ELEMENT TYPE S4R AND ELEMENT \n   SET ASSEMBLY_{set}\n"
OPEN_NODE = "   THE FOLLOWING TABLE IS PRINTED FOR NODES BELONGING TO NODE SET ASSEMBLY_{set}\n"


def g4(value: float) -> str:
    """A value as Abaqus prints it: four significant figures, E notation for the small ones."""
    if value == 0.0:
        return "0.000"
    if abs(value) < 1e-2 or abs(value) >= 1e5:
        return f"{value:.4E}"
    return f"{value:.4g}"


def element_table(set_name: str, columns: list[str], rows: list[tuple[int, int | None, list[float]]]) -> str:
    """One `*El Print` table in the layout of the real file: the two-line opening, the column line, the footnote headings, the rows,
    the MAXIMUM and MINIMUM lines and the footnote."""
    has_point = rows[0][1] is not None
    head = ("    ELEMENT  SEC FOOT-   " if has_point else "    ELEMENT  FOOT-   ") + "".join(f"{c:<12}" for c in columns)
    notes = "              PT NOTE \n" if has_point else "             NOTE \n"
    body = ""
    for label, point, values in rows:
        body += f"{label:>12}" + (f"{point:>4}" if has_point else "") + "   OR" + "".join(f"{g4(v):>12}" for v in values) + "\n"
    extremes = "\n MAXIMUM          " + "".join(f"{g4(max(r[2][i] for r in rows)):>12}" for i in range(len(columns))) + "\n ELEMENT          " + \
               "".join(f"{rows[0][0]:>12}" for _ in columns) + "\n\n MINIMUM          " + "".join(f"{g4(min(r[2][i] for r in rows)):>12}" for i in range(len(columns))) + \
               "\n ELEMENT          " + "".join(f"{rows[0][0]:>12}" for _ in columns) + "\n\n OR: *ORIENTATION USED FOR THIS ELEMENT\n\n\n\n"
    return OPEN_ELEMENT.format(set=set_name.upper()) + "\n" + head + "\n" + notes + "\n" + body + extremes


def node_table(set_name: str, columns: list[str], rows: list[tuple[int, list[float]]], totals: bool) -> str:
    head = "       NODE FOOT-  " + "".join(f"{c:<15}" for c in columns)
    body = "".join(f"{label:>10}     " + "".join(f"{v:15.7E}" for v in values) + " \n" for label, values in rows)
    tail = "\n MAXIMUM       " + "".join(f"{g4(max(r[1][i] for r in rows)):>12}" for i in range(len(columns))) + "\n AT NODE       " + \
           "".join(f"{rows[0][0]:>12}" for _ in columns) + "\n\n MINIMUM       " + "".join(f"{g4(min(r[1][i] for r in rows)):>12}" for i in range(len(columns))) + "\n"
    if totals:
        tail += "\n TOTAL         " + "".join(f"{g4(sum(r[1][i] for r in rows)):>12}" for i in range(len(columns))) + "\n"
    return OPEN_NODE.format(set=set_name.upper()) + "  \n" + head + "\n            NOTE\n  \n" + body + tail + "  \n  \n"


@pytest.fixture(scope="module")
def solved(tmp_path_factory):
    """The public coupon's Abaqus deck, in the deck's units, with the kernel's values at the gauge element in those units."""
    spec = to_si(parse_spec(PUBLIC_COUPON))
    text = write_abaqus(build_model(spec))
    units = spec.units
    deck_units = deck_units_of(units)
    folder = tmp_path_factory.mktemp("deck")
    deck_path = folder / "IM7-UNT-L1-abaqus.inp"
    deck_path.write_text(text, encoding="utf-8", newline="\n")
    deck = deck_to_si(parse_deck(text, source_path=deck_path.name), deck_units)
    check = laminate_check(deck, solve_deck(deck))
    label = int(check.gauge.name.split(".")[-1])
    stress = from_si(check.kernel_ply_stress_12, "stress", deck_units)  # (plies, 3)
    strain = np.asarray(check.kernel_strain)
    reaction = from_si(check.kernel_reaction_N, "force", deck_units)
    return {"deck_path": deck_path, "units": units, "label": label, "stress": stress, "strain": strain, "reaction": reaction, "plies": len(check.angles_deg)}


def dat_text(solved: dict, middles: bool = True, reaction_set: str = "RF-Top") -> str:
    """A `.dat` as Abaqus would write it for the deck: the probe element's SF, SE, S and E tables and the reaction's TOTAL."""
    label, plies = solved["label"], solved["plies"]
    ex, ey, gxy = (float(v) for v in solved["strain"])
    out = BANNER + "\n" * 5 + "                                                  E L E M E N T   O U T P U T\n\n\n\n\n"
    out += element_table("Probe-centre", ["SF1", "SF2", "SF3", "SF4", "SF5", "SF6", "SM1", "SM2", "SM3"], [(label, None, [188.2, 0.0036, 0, 0, 0, 0, 0, 0, 0])])
    out += element_table("Probe-centre", ["SE1", "SE2", "SE3", "SE4", "SE5", "SE6", "SK1", "SK2", "SK3"], [(label, None, [ey, ex, -gxy, 0, 0, -0.0025, 0, 0, 0])])
    points = [SECTION_POINTS * k + (SECTION_POINTS + 1) // 2 for k in range(plies)] if middles else [1, SECTION_POINTS * plies]
    layers = list(range(plies)) if middles else [0, plies - 1]
    out += element_table("Probe-centre", ["S11", "S22", "S12"], [(label, p, [float(v) for v in solved["stress"][k]]) for p, k in zip(points, layers)])
    out += element_table("Probe-centre", ["E11", "E22", "E12"], [(label, p, [0.001, -0.0002, 0.0003]) for p in points])
    out += "\n                                       N O D E   O U T P U T\n  \n  \n  \n  \n"
    out += node_table(reaction_set, ["RF1", "RF2", "RF3", "RM1", "RM2", "RM3"], [(2, [2.18e-10, float(solved["reaction"]), 1.5e-14, 0, 0, 0])], totals=True)
    out += node_table("Probe-centre", ["U1", "U2", "U3", "UR1", "UR2", "UR3"], [(815, [-3.1e-14, 0.2464, 0, 0, 0, 0])], totals=False)
    out += "\n\n          THE ANALYSIS HAS BEEN COMPLETED\n\n       TOTAL CPU TIME (SEC) =      1.3    \n"
    return out


def test_the_printed_tables_are_read_as_abaqus_lays_them_out(solved):
    dat = parse_abaqus_dat(dat_text(solved))
    assert dat.version == "Abaqus 2025"
    assert [(t.kind, t.set_name, t.columns[0], len(t.rows)) for t in dat.tables] == [
        ("element", "PROBE-CENTRE", "SF1", 1), ("element", "PROBE-CENTRE", "SE1", 1), ("element", "PROBE-CENTRE", "S11", solved["plies"]),
        ("element", "PROBE-CENTRE", "E11", solved["plies"]), ("node", "RF-TOP", "RF1", 1), ("node", "PROBE-CENTRE", "U1", 1)]
    stress = dat.find("element", "Probe-centre", "S11")  # the set is matched whatever its case, the ASSEMBLY_ prefix dropped
    rows = stress.of(solved["label"])
    assert [r.point for r in rows] == [2, 5, 8, 11, 14, 17, 20, 23][:solved["plies"]] and all(r.tag == "OR" for r in rows)
    assert rows[1].values[0] == pytest.approx(float(solved["stress"][1, 0]), rel=1e-3)  # four printed figures
    reaction = dat.find("node", "RF-Top", "RF2")
    assert reaction.total is not None and reaction.total[1] == pytest.approx(float(solved["reaction"]), rel=1e-3)  # the TOTAL line, not "TOTAL CPU TIME"
    assert dat.find("node", "Probe-centre", "U2").total is None
    with pytest.raises(AbaqusDatError, match="no column 'S33'"):
        stress.column("S33")
    with pytest.raises(AbaqusDatError, match="no element table for set 'Probe-far'"):
        dat.find("element", "Probe-far", "S11")


def test_a_row_that_does_not_read_is_refused_by_its_line(solved):
    text = dat_text(solved)
    broken = text.replace("   OR", "   OR   7", 1)  # a number where the footnote tag is: one value too many for the columns
    with pytest.raises(AbaqusDatError, match=r"\.dat line \d+: .*more numbers than the table has columns"):
        parse_abaqus_dat(broken)
    with pytest.raises(AbaqusDatError, match=r"\.dat line \d+: cannot read"):
        parse_abaqus_dat(text.replace("   OR", "", 1).replace("    ELEMENT  FOOT-   SF1", "    ELEMENT  SEC FOOT-   SF1", 1))
    assert parse_abaqus_dat("no tables here\n").tables == ()
    assert [layer_of(p) for p in (1, 2, 3, 5, 23, 24)] == [None, 1, None, 2, 8, None]


def test_the_summary_puts_abaqus_beside_the_kernel_at_the_gauge_element(solved):
    summary = abaqus_beside(solved["deck_path"], dat_text(solved), solved["units"], "IM7-UNT-L1-abaqus.dat")
    plies = solved["plies"]
    assert summary["solver"] == "Abaqus 2025" and summary["gauge_element"].endswith(f".{solved['label']}") and summary["reaction_set"] == "RF-Top"
    assert summary["agree"] == f"{1 + 3 + 3 * plies} of {1 + 3 + 3 * plies}"  # the reaction, the strain and every ply's three stresses
    assert summary["reaction"]["agrees"] and summary["reaction"]["difference"].endswith(" %")
    assert summary["reaction"]["abaqus"] == pytest.approx(summary["reaction"]["ours"], rel=1e-3)
    assert [g["ply"] for g in summary["gauge"]] == list(range(1, plies + 1)) and [g["angle"] for g in summary["gauge"]][:4] == [45.0, 0.0, -45.0, 90.0]
    for g in summary["gauge"]:
        assert g["agrees"] == [True, True, True]
        assert np.allclose(g["abaqus"], g["ours"], rtol=2e-3, atol=1e-6 * max(abs(v) for v in g["ours"]))
    strain = summary["gauge_strain"]
    assert strain["agrees"] == [True, True, True] and strain["abaqus"][1] > 0 > strain["abaqus"][0]  # SE1 is eps_y, SE2 eps_x: the layup's axis 1 runs along the pull
    assert np.allclose(strain["abaqus"][:2], strain["ours"][:2], rtol=2e-3)
    assert len(summary["dat_sha256"]) == 64 and summary["units"] == solved["units"] and summary["tolerance"] == 0.03


def test_a_dat_that_prints_the_faces_is_refused_with_what_it_printed(solved):
    with pytest.raises(AbaqusDatError, match=r"section points \[1, 24\] .* not the middle of every layer .* download it again"):
        abaqus_beside(solved["deck_path"], dat_text(solved, middles=False), solved["units"])
    with pytest.raises(AbaqusDatError, match="no node table for set 'RF-Top'"):
        abaqus_beside(solved["deck_path"], dat_text(solved, reaction_set="RF-Other"), solved["units"])
    with pytest.raises(AbaqusDatError, match="prints no table"):
        abaqus_beside(solved["deck_path"], "1\n   Abaqus 2025\n", solved["units"])


def test_a_value_outside_the_tolerance_is_marked(solved):
    text = dat_text(solved)
    off = text.replace(g4(float(solved["stress"][1, 0])), g4(float(solved["stress"][1, 0]) * 1.1), 1)  # the 0° ply's sigma_1, 10 % off
    summary = abaqus_beside(solved["deck_path"], off, solved["units"])
    plies = solved["plies"]
    assert summary["gauge"][1]["agrees"] == [False, True, True] and summary["agree"] == f"{3 + 3 * plies} of {1 + 3 + 3 * plies}"


def test_the_tool_prints_the_table_and_writes_the_summary(solved, tmp_path, capsys):
    spec = importlib.util.spec_from_file_location("abaqus_beside_tool", TOOLS / "abaqus_beside.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    dat_path = tmp_path / "IM7-UNT-L1-abaqus.dat"
    dat_path.write_text(dat_text(solved), encoding="utf-8")
    out = tmp_path / "abaqus.json"
    assert tool.main([str(solved["deck_path"]), str(dat_path), "--units", solved["units"], "--json", str(out)]) == 0
    printed = capsys.readouterr().out
    plies = solved["plies"]
    assert f"{1 + 3 + 3 * plies} of {1 + 3 + 3 * plies} values agree within 3 %" in printed and "ply 2 (0 deg) sigma_1, MPa" in printed and "✕" not in printed
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["agree"] == f"{1 + 3 + 3 * plies} of {1 + 3 + 3 * plies}" and written["dat"] == "IM7-UNT-L1-abaqus.dat"
    assert tool.main([str(solved["deck_path"]), str(tmp_path / "missing.dat")]) == 2
    assert "abaqus_beside:" in capsys.readouterr().err


def test_a_value_below_1e_minus_99_is_read_as_fortran_prints_it():
    """Abaqus 2025 prints 1.5633561E-189 as `1.5633561-189`, the letter dropped for the three-digit exponent (seen 2026-11-11 in the D3039
    detection run): the reader takes it, and still refuses a token that is no number."""
    from anisotropy_fea.abaqus_dat import NUMBER, _number

    assert _number("1.5633561-189") == pytest.approx(1.5633561e-189, rel=1e-12)
    assert _number("-3.2-101") == pytest.approx(-3.2e-101, rel=1e-12)
    assert _number("-1.5049691E-42") == pytest.approx(-1.5049691e-42, rel=1e-12)
    assert _number("1.0D-03") == pytest.approx(1e-3)
    assert not NUMBER.match("12-345") and not NUMBER.match("E5") and not NUMBER.match("1.5-12")  # an integer mantissa, a two-digit exponent
