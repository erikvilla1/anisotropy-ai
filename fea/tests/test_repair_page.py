"""What the repair's page asks of the fea tools (ADR-0135): a repair read as the page sends it (the repair file's table as JSON),
the solve's statuses and the file it leaves for the API, the table of the STEP file's solids, and the solved slices the page's
tests draw (tests/fixtures/repair/, written by scripts/repair-choices.py), which must be what the solver gives today."""

import json
import tomllib
from pathlib import Path

import pytest

from anisotropy_engine.repair import repair_from_dict
from anisotropy_fea.calculix import find_ccx
from anisotropy_fea.repair_model import REPORT, STOPPED, headline, main, slice_report, solve_slice
from anisotropy_fea.repair_shape import REFUSED, ShapeError, read_repair_file
from anisotropy_fea.repair_shape import main as shape_main

ROOT = Path(__file__).parents[2]
EXAMPLES = {"example": ROOT / "engine" / "examples" / "example-patch-repair.toml",
            "external": ROOT / "engine" / "examples" / "example-external-patch-repair.toml"}
FIXTURES = ROOT / "tests" / "fixtures" / "repair"
needs_ccx = pytest.mark.skipif(find_ccx() is None, reason="CalculiX not found: set ANISOTROPY_CCX or put ccx on PATH (docs/installation-fea-tools.md)")


def as_json(tmp_path: Path, name: str = "example", **changes) -> Path:
    data = tomllib.loads(EXAMPLES[name].read_text(encoding="utf-8"))
    for where, value in changes.items():
        table, key = where.split("__")
        if value is None:
            data[table].pop(key)
        else:
            data[table][key] = value
    path = tmp_path / "repair.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_a_repair_reads_the_same_from_its_file_and_from_the_table_a_page_sends(tmp_path):
    from_file = read_repair_file(EXAMPLES["example"])
    assert read_repair_file(as_json(tmp_path)) == from_file == tomllib.loads(EXAMPLES["example"].read_text(encoding="utf-8"))
    assert repair_from_dict(read_repair_file(as_json(tmp_path))) == repair_from_dict(from_file)
    case = ROOT / "engine" / "validation" / "patch_repair_cases" / "constructed-cross-ply-patch-with-a-cover-ply.toml"
    assert "expected" not in read_repair_file(case), "a validation case reads as a repair: its expected numbers are left out"
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(ShapeError, match="broken.json does not read as a repair file"):
        read_repair_file(broken)
    broken.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ShapeError, match="not a table of values"):
        read_repair_file(broken)


def test_a_repair_that_cannot_be_solved_ends_refused_with_its_reason_as_the_last_line(tmp_path, capsys):
    assert main([str(as_json(tmp_path, adhesive__poisson=None))]) == REFUSED
    assert capsys.readouterr().out.strip().splitlines()[-1] == "refused: The solve of the slice needs the adhesive's Poisson's ratio"
    assert main([str(as_json(tmp_path, steps__count=9))]) == REFUSED
    assert capsys.readouterr().out.strip() == "refused: 9 steps of 1 plies remove 9 plies, and the laminate has 8"
    assert main([str(tmp_path / "none.json")]) == REFUSED


def test_a_solver_that_fails_ends_stopped_with_the_cause_on_stderr_and_no_report(tmp_path, capsys, monkeypatch):
    import anisotropy_fea.repair_model as module
    from anisotropy_fea.calculix import CalculixError

    def failing(*args, **kwargs):
        raise CalculixError("ccx stopped: no memory\nand more")

    monkeypatch.setattr(module, "run_calculix", failing)
    out = tmp_path / "model"
    assert main([str(as_json(tmp_path)), "--out", str(out)]) == STOPPED
    said = capsys.readouterr()
    assert said.err.strip() == "stopped: ccx stopped: no memory" and "refused" not in said.out
    assert not (out / REPORT).exists()


@needs_ccx
def test_the_solve_leaves_its_report_with_the_headline_for_the_api(tmp_path, capsys):
    out = tmp_path / "model"
    assert main([str(as_json(tmp_path)), "--out", str(out), "--cut-faces", "open"]) == 0
    report = json.loads((out / REPORT).read_text(encoding="utf-8"))
    said = capsys.readouterr().out
    assert said.splitlines()[0] == "Example stepped patch repair"
    assert report["headline"].startswith("Under 100 N/mm: largest bondline shear ") and "the adhesive reaches its elastic limit in shear at" in report["headline"]
    assert report["model"]["cut_faces"] == "open" and report["units"] == {"length": "mm", "stress": "MPa", "force": "N/mm"}


@needs_ccx
@pytest.mark.parametrize("name", EXAMPLES)
def test_the_solved_slices_the_pages_tests_draw_are_what_the_solver_gives(name):
    kept = json.loads((FIXTURES / f"{name}-solve.json").read_text(encoding="utf-8"))
    data = tomllib.loads(EXAMPLES[name].read_text(encoding="utf-8"))
    report = slice_report(solve_slice(*repair_from_dict(data)), data["units"])
    assert kept["run_id"] is None and kept["report"]["model"] | {"seconds": 0} == report["model"] | {"seconds": 0}
    # to the digits the page prints (four), with room for the solver's last figures on another machine
    for key in ("peak_shear", "peak_peel"):
        assert kept["report"]["bond"][key]["value"] == pytest.approx(report["bond"][key]["value"], rel=1e-5)
        assert kept["report"]["bond"][key]["part"] == report["bond"][key]["part"]
    assert kept["report"]["elastic_limit_load"] == pytest.approx(report["elastic_limit_load"], rel=1e-5)
    assert kept["report"]["first"]["what"] == report["first"]["what"] and kept["report"]["first"]["load"] == pytest.approx(report["first"]["load"], rel=1e-5)
    assert kept["report"]["first_ply"]["name"] == report["first_ply"]["name"]
    assert [b["patch"] for b in kept["report"]["boundaries"]] == pytest.approx([b["patch"] for b in report["boundaries"]], rel=1e-5)
    assert [len(line["r"]) for line in kept["report"]["bond"]["lines"]] == [len(line["r"]) for line in report["bond"]["lines"]]
    assert kept["headline"] == headline(report)


def test_the_solids_table_is_written_beside_the_step_file(tmp_path):
    pytest.importorskip("gmsh", reason="Gmsh is not installed here (uv sync --extra mesh)")
    step, parts = tmp_path / "repair.step", tmp_path / "parts.json"
    assert shape_main([str(as_json(tmp_path)), "--step", str(step), "--parts", str(parts)]) == 0
    table = json.loads(parts.read_text(encoding="utf-8"))
    assert step.read_text(encoding="ascii").startswith("ISO-10303-21;")
    assert table["title"] == "Example stepped patch repair" and table["units"] == {"length": "mm", "volume": "mm^3"}
    assert [part["name"] for part in table["parts"]][:2] == ["Laminate ply 1 (45 deg)", "Laminate ply 2 (0 deg)"]
    assert {part["kind"] for part in table["parts"]} == {"parent", "adhesive", "patch", "cover"}
    assert sum(part["volume"] for part in table["parts"] if part["kind"] == "patch") == pytest.approx(table["volumes"]["patch"])


def test_a_repair_the_engine_refuses_is_refused_by_the_shape_with_its_reason_on_stderr(tmp_path, capsys):
    assert shape_main([str(as_json(tmp_path, steps__count=9))]) == REFUSED
    assert capsys.readouterr().err.strip() == "9 steps of 1 plies remove 9 plies, and the laminate has 8"
