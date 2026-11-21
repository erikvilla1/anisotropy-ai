"""A repair's slice as an Abaqus and an Ansys input file (ADR-0132 amendment 1): each file states the model CalculiX's deck
states, and what a program wrote is read back through the same reading. Neither program runs here: the files are checked by
reading their text, the Abaqus one also by solving it in CalculiX (which reads the same keywords), and the readers on stand-in
output written from CalculiX's own results in each program's wording."""

import tomllib
from pathlib import Path

import numpy as np
import pytest

from anisotropy_engine.repair import repair_from_dict
from anisotropy_fea.abaqus_dat import parse_abaqus_dat
from anisotropy_fea.calculix import find_ccx, run_calculix
from anisotropy_fea.repair_files import (
    ANSYS_COLUMNS, abaqus_file, ansys_file, compare_answers, engineering_constants, main, read_abaqus, read_ansys,
)
from anisotropy_fea.repair_model import MPA, SliceModelError, build_slice_model, end_pressures, held_nodes, read_results, run_slice_model, slice_answer

ROOT = Path(__file__).parents[2]
EXAMPLE = ROOT / "engine" / "examples" / "example-patch-repair.toml"
needs_ccx = pytest.mark.skipif(find_ccx() is None, reason="CalculiX not found: set ANISOTROPY_CCX or put ccx on PATH (docs/installation-fea-tools.md)")


def model_of(**options):
    case = tomllib.loads(EXAMPLE.read_text(encoding="utf-8"))
    repair, load = repair_from_dict(case)
    return build_slice_model(repair, load, **options)


@pytest.fixture(scope="module")
def model():
    return model_of()


@pytest.fixture(scope="module")
def solved(model):
    results = run_slice_model(model)
    return results, slice_answer(model, results)


def block(text: str, opens: str) -> list[str]:
    """The data lines under the first keyword line that starts with `opens`, up to the next keyword or comment."""
    lines = text.splitlines()
    start = next(k for k, line in enumerate(lines) if line.startswith(opens)) + 1
    stop = next(k for k in range(start, len(lines)) if lines[k].startswith("*"))
    return lines[start:stop]


def ansys_table(model, results) -> str:
    """What the Ansys file writes: the element's number, then the columns of ANSYS_COLUMNS, in mm, N and MPa. Mechanical APDL
    keeps an element table as 32-bit numbers and writes them out to fifteen figures ("0.375531406402588E+02"), so the stand-in rounds each value to a 32-bit number first."""
    stress, strain = results.stress / MPA, results.strain
    width = np.full(len(stress), model.far.strain_width)
    columns = [stress[:, 0], stress[:, 2], stress[:, 1], stress[:, 3], strain[:, 0], strain[:, 1], width, strain[:, 2]]
    columns = [column.astype(np.float32).astype(float) for column in columns]
    return "\n".join(f"{k + 1:9.0f}." + "".join(f"{column[k]:24.15E}" for column in columns) for k in range(len(stress))) + "\n"


def abaqus_dat(model, results) -> str:
    """What Abaqus prints for the file, in its own wording (the set's name on a
    line of its own, the columns PT and FOOT-, the tag OR of an element with an orientation) and its four figures: a table of
    S and a table of E at the four integration points of every element, here each point given the element's mean."""
    stress, strain = results.stress / MPA, results.strain
    tables = ((("S11", "S22", "S33", "S12"), np.column_stack([stress[:, 0], stress[:, 2], stress[:, 1], stress[:, 3]])),
              (("E11", "E22", "E33", "E12"), np.column_stack([strain[:, 0], strain[:, 1], np.zeros(len(strain)), strain[:, 2]])))
    out = ["", "   Abaqus 2025                                  Date 20-Nov-2026   Time 18:30:00", ""]
    for names, values in tables:
        out += ["", "   THE FOLLOWING TABLE IS PRINTED AT THE INTEGRATION POINTS FOR ELEMENT TYPE CPE8R AND ELEMENT SET ", "   EALL", "",
                "    ELEMENT  PT FOOT-       " + "".join(f"{name:<12}" for name in names), "                NOTE ", ""]
        for k, row in enumerate(values):
            out += [f"{k + 1:12d}{point:4d}  OR  " + "".join(f"{value:12.3E}" for value in row) for point in (1, 2, 3, 4)]
        out.append("")
    return "\n".join(out) + "\n"


def test_the_abaqus_file_states_the_decks_model(model):
    text, deck = abaqus_file(model), model.deck
    assert text.isascii() and text.startswith("*Heading\n")
    assert max(len(line) for line in text.splitlines()) <= 120  # Abaqus cuts a line at 256 characters, with a warning
    assert "** Material 5: Adhesive on the floor," in text and "\n**    the cut face of step 3," in text
    assert block(text, "*Node,") == block(deck, "*NODE,")
    elements = [line for line in text.splitlines() if line[:1].isdigit() and line.count(",") == 8]
    assert len(elements) == len(model.elements) and text.count("type=CPE8R") == deck.count("TYPE=CPE8R")

    def stiffness(of: str, key: str) -> list[str]:
        lines = of.splitlines()
        return [lines[k + 1] + lines[k + 2] for k, line in enumerate(lines) if line.startswith(key)]

    assert stiffness(text, "*Elastic, type=ORTHOTROPIC") == stiffness(deck, "*ELASTIC, TYPE=ORTHO")
    assert block(text, "*Dload") == block(deck, "*DLOAD") and len(block(text, "*Dload")) == len(end_pressures(model.mesh, model.far))
    assert block(text, "*Temperature") == block(deck, "*TEMPERATURE") == [f"NALL, {model.far.strain_width:.12g}"]
    assert block(text, "*Boundary") == ["MIDDLE, 1, 1, 0.", "BOTTOM, 2, 2, 0."]
    assert block(text, "*Orientation") == ["1., 0., 0., 0., 1., 0.", "3, 0."] and text.count("orientation=SLICE") == text.count("*Material")
    assert block(text, "*Expansion") == ["0., 0., -1."]
    assert "*El Print, elset=EALL, position=INTEGRATION POINTS, summary=NO\nS\n" in text
    assert "*El Print, elset=EALL, position=INTEGRATION POINTS, summary=NO\nE\n" in text
    assert "NALL, 2, 2, 0." in abaqus_file(model_of(hold="everywhere"))


def test_the_ansys_files_constants_are_the_stiffness_the_other_files_hold(model):
    for matrix in model.stiffness:
        k = engineering_constants(matrix)
        compliance = np.array([[1 / k["EX"], -k["PRXY"] / k["EX"], -k["PRXZ"] / k["EX"]],
                               [-k["PRXY"] / k["EX"], 1 / k["EY"], -k["PRYZ"] / k["EY"]],
                               [-k["PRXZ"] / k["EX"], -k["PRYZ"] / k["EY"], 1 / k["EZ"]]])
        normal = np.linalg.inv(compliance)  # x the load, y the thickness, z the width
        assert np.allclose(normal, matrix[np.ix_([0, 2, 1], [0, 2, 1])], rtol=1e-11)
        assert (k["GXY"], k["GYZ"], k["GXZ"]) == (matrix[4, 4], matrix[3, 3], matrix[5, 5])
    adhesive = engineering_constants(model.stiffness[[part.kind for part in model.mesh.regions].index("adhesive")])
    assert adhesive["EX"] == pytest.approx(2 * 1000e6 * 1.35) and adhesive["PRXY"] == pytest.approx(0.35) and adhesive["GXZ"] == pytest.approx(1000e6)


def test_the_ansys_file_states_the_model(model):
    text = ansys_file(model, "run")
    lines = text.splitlines()
    assert text.isascii() and max(len(line) for line in lines) <= 240
    assert "ET,1,183" in lines and "KEYOPT,1,3,2" in lines
    at = lines.index(f"NBLOCK,6,SOLID,{len(model.nodes_m):10d},{len(model.nodes_m):10d}")
    node = lines[at + 2 + 4]  # the fifth node
    assert int(node[:9]) == 5 and (float(node[27:48]), float(node[48:69])) == pytest.approx(tuple(model.nodes_m[4] * 1e3), rel=1e-12)
    at = lines.index(f"EBLOCK,19,SOLID,{len(model.elements):10d},{len(model.elements):10d}")
    rows = np.array([[int(line[k:k + 10]) for k in range(0, 190, 10)] for line in lines[at + 2:at + 2 + len(model.elements)]])
    assert lines[at + 2 + len(model.elements)] == "-1"
    assert np.array_equal(rows[:, 10], np.arange(1, len(rows) + 1)) and np.array_equal(rows[:, 11:], model.elements + 1) and set(rows[:, 8]) == {8}
    materials = sorted(set(rows[:, 0]))
    assert [line for line in lines if line.startswith("MP,ALPZ,")] == [f"MP,ALPZ,{number},-1." for number in materials]
    assert f"TUNIF,{model.far.strain_width:.12g}" in lines and "TREF,0." in lines and "ERESX,NO" in lines
    assert [line for line in lines if line.startswith("SFE,")] == [f"SFE,{e + 1},2,PRES,,{pressure / MPA:.12g}" for e, pressure in end_pressures(model.mesh, model.far)]
    middle, bottom = held_nodes(model.nodes_m)
    assert f"CMBLOCK,N_MIDDLE,NODE,{len(middle):10d}" in lines and f"CMBLOCK,N_BOTTOM,NODE,{len(bottom):10d}" in lines
    assert "D,N_MIDDLE,UX,0." in lines and "D,N_BOTTOM,UY,0." in lines
    assert "D,ALL,UY,0." in ansys_file(model_of(hold="everywhere")).splitlines()
    assert lines[-5:] == ["*CFOPEN,'run','txt'", "*VWRITE,SEQU," + ",".join(f"RES(1,{k})" for k in range(1, 9)), "(F10.0,8E24.15)", "*CFCLOS", "FINISH"]
    assert [line.split(",")[1] for line in lines if line.startswith("ETABLE,")] == list(ANSYS_COLUMNS)
    with pytest.raises(SliceModelError, match="plain"):
        ansys_file(model, "a name")


@needs_ccx
def test_the_abaqus_file_solved_by_calculix_gives_the_decks_answer(model, solved, tmp_path):
    (tmp_path / "slice.inp").write_text(abaqus_file(model), encoding="ascii")
    again = read_results(model, run_calculix(tmp_path / "slice.inp").dat_text)
    assert np.max(np.abs(again.stress - solved[0].stress)) <= 1e-9 * np.max(np.abs(solved[0].stress))


@needs_ccx
def test_what_ansys_writes_is_read_back_as_the_same_answer(model, solved):
    results, ours = solved
    theirs = slice_answer(model, read_ansys(model, ansys_table(model, results)))
    found = compare_answers(ours, theirs)
    assert found["same_places"] and max(found["largest"].values()) < 1e-6  # the table's seven figures
    assert [what for what, _, _ in found["rows"]][-1].startswith("strength ratio of ") and len(found["rows"]) >= 5 + 4 + 1 + 3
    shifted = ansys_table(model, results).splitlines()
    with pytest.raises(SliceModelError, match="every element"):
        read_ansys(model, "\n".join(shifted[:-1]))
    with pytest.raises(SliceModelError, match="columns"):
        read_ansys(model, "\n".join(line[:-24] for line in shifted))
    wrong = model_of(cut_faces="bonded")
    with pytest.raises(SliceModelError, match="every element"):
        read_ansys(wrong, "\n".join(shifted))
    stress = results.stress.copy()
    stress[:, 0] *= 1.001  # stresses that are not this model's stiffness times the strains
    with pytest.raises(SliceModelError, match="Ansys's stresses are not the engine's stiffness"):
        read_ansys(model, ansys_table(model, type(results)(results.strain, stress, 0.0, None, None)))
    off = type(model)(**{**model.__dict__, "far": type(model.far)(**{**model.far.__dict__, "strain_width": model.far.strain_width * 1.01})})
    with pytest.raises(SliceModelError, match="across the width"):
        read_ansys(off, ansys_table(model, results))


@needs_ccx
def test_what_abaqus_prints_is_read_back_to_its_four_figures(model, solved):
    results, ours = solved
    text = abaqus_dat(model, results)
    table = parse_abaqus_dat(text).find("element", "EALL", "S11")
    assert table.rows[5].label == 2 and table.rows[5].integration_point == 2 and table.rows[5].point is None and table.rows[5].tag == "OR"
    read = read_abaqus(model, text)
    assert read.solver == "Abaqus 2025"
    theirs = slice_answer(model, read, equilibrium_tolerance=1e-3)
    found = compare_answers(ours, theirs)
    assert found["same_places"] and found["largest"]["element_stress"] < 5e-4 and found["largest"]["reported"] < 1e-3
    with pytest.raises(SliceModelError, match="no element table"):
        read_abaqus(model, text.replace("EALL", "OTHER"))
    with pytest.raises(SliceModelError, match="every element"):
        read_abaqus(model, "\n".join(line for line in text.splitlines() if not line.startswith("           7   3")))


@needs_ccx
def test_the_command_writes_the_files_and_compares_a_run(model, solved, tmp_path, capsys):
    assert main([str(EXAMPLE), "--out", str(tmp_path), "--name", "run"]) == 0
    assert (tmp_path / "run-abaqus.inp").read_text(encoding="ascii") == abaqus_file(model)
    assert (tmp_path / "run-ansys.cdb").read_text(encoding="ascii") == ansys_file(model, "run-ansys")
    (tmp_path / "run-ansys.txt").write_text(ansys_table(model, solved[0]), encoding="ascii")
    (tmp_path / "run.dat").write_text(abaqus_dat(model, solved[0]), encoding="ascii")
    capsys.readouterr()
    assert main([str(EXAMPLE), "--ansys", str(tmp_path / "run-ansys.txt"), "--abaqus", str(tmp_path / "run.dat")]) == 0
    printed = capsys.readouterr().out
    assert "Ansys (Ansys Mechanical APDL) beside CalculiX" in printed and "Abaqus (Abaqus 2025) beside CalculiX" in printed
    assert printed.count("in the same places") == 2 and "NOT" not in printed
    assert main([str(EXAMPLE), "--ansys", str(tmp_path / "missing.txt")]) == 2
    assert capsys.readouterr().out.startswith("refused: ")  # before anything is solved
