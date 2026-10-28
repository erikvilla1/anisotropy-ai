"""tools/run_coupon.py (ADR-0049): one command takes a filled-in input form to the coupon's package, adds the attempt's row and
refreshes the case page; a failed step gets its row too; it refuses, before writing anything, without CalculiX or with an attempt
log behind its folders; its record is made as the case page says. Everything runs under a temporary root, never .local/."""

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from public_coupon import DESIGNATION
from test_intake import PUBLIC_FILL

from anisotropy_fea import paths
from anisotropy_fea.calculix import find_ccx
from anisotropy_fea.case_pages import NO_RECORD_YET, read_case
from anisotropy_fea.intake import convert, fill_form, next_commands, write_blank_form

TOOLS = Path(__file__).parents[1] / "tools"
needs_ccx = pytest.mark.skipif(find_ccx() is None, reason="CalculiX not found: set ANISOTROPY_CCX or put ccx on PATH (docs/installation-fea-tools.md)")


@pytest.fixture
def tool(monkeypatch, tmp_path):
    """The tool as a module, with the coupons' root moved to a temporary folder."""
    monkeypatch.setattr(paths, "LOCAL", tmp_path / "fea")
    monkeypatch.setattr(paths, "MODELS", tmp_path / "fea")
    monkeypatch.syspath_prepend(str(TOOLS))  # it imports regenerate_decks from its own folder
    spec = importlib.util.spec_from_file_location("run_coupon", TOOLS / "run_coupon.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)  # its dataclass looks the module up there
    spec.loader.exec_module(module)
    return module


def public_form(tmp_path: Path) -> Path:
    return fill_form(write_blank_form(tmp_path / "blank.xlsx"), PUBLIC_FILL, tmp_path / "filled.xlsx")


def public_values(tmp_path: Path, **changes) -> Path:
    from anisotropy_fea.intake import FORM_VERSION

    path = tmp_path / "values.json"
    path.write_text(json.dumps({"form_version": FORM_VERSION, **PUBLIC_FILL, **changes}), encoding="utf-8")
    return path


@needs_ccx
def test_a_filled_form_goes_to_its_package_in_one_command(tool, tmp_path):
    progress_path = tmp_path / "progress.json"
    outcome = tool.run(str(public_form(tmp_path)), "A. Engineer", pdf=False, theory=False, progress=tool.Progress(progress_path))
    folder, attempt = paths.LOCAL / DESIGNATION, outcome.attempt
    out = attempt / "run"
    assert outcome.coupon == DESIGNATION and set(outcome.outputs) == {"package", "abaqus_deck", "prepomax_deck", "prepomax_results", "kernel_summary",
                                                                      "kernel_vtu", "fields", "explanation", "record", "checklist", "preview"}  # no document without the PDF
    assert all(path.exists() for path in outcome.outputs.values())
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    assert progress["stage"] == "the outputs" and progress["done"] == list(tool.STAGES[:-1]) and progress["coupon"] == DESIGNATION
    assert set(progress["outputs"]) == set(outcome.outputs) and progress["attempt"].endswith(attempt.name)
    fields = json.loads((out / "kernel" / f"{DESIGNATION}-fields.json").read_text(encoding="utf-8"))
    assert fields["summary"]["reaction"]["value"] > 0 and json.loads((out / "studio" / "checklist.json").read_text(encoding="utf-8"))["state"] == "ready"
    assert attempt.parent == paths.runs(DESIGNATION) and attempt.name.startswith("attempt-02_")  # row 01 is the form's reading
    decks = paths.ours(DESIGNATION) / "decks"
    assert (decks / f"{DESIGNATION}-abaqus.inp").is_file() and (decks / f"{DESIGNATION}-nodal-ccx.inp").is_file()
    assert "first-ply failure, max_stress: factor" in (out / "kernel" / "summary.txt").read_text(encoding="utf-8")
    assert (out / "calculix" / f"{DESIGNATION}-nodal-ccx.frd").is_file()
    assert "A. Engineer" in (paths.verification(DESIGNATION) / f"{DESIGNATION}-calculix.toml").read_text(encoding="utf-8")
    [package] = paths.documents(DESIGNATION).iterdir()  # named by the day it was built
    assert package.name.endswith(f"_{DESIGNATION}") and (package / "2-our-model" / "abaqus" / f"{DESIGNATION}-abaqus.inp").is_file()
    assert (package / "2-our-model" / "calculix" / f"{DESIGNATION}-nodal-ccx.inp").is_file()
    assert read_case(folder).attempts == 2
    page = (folder / "README.md").read_text(encoding="utf-8")
    row = next(line for line in page.splitlines() if line.startswith("| 02 |"))
    assert "run_coupon.py" in row and "run by A. Engineer" in row and "package written" in row
    count = re.search(r"(\d+) of (\d+) recorded values agree with CalculiX", row)
    assert count and count[1] == count[2]  # the gauge probes only: every recorded value agrees
    assert NO_RECORD_YET not in page  # the result block now reads the record


def test_without_calculix_nothing_is_written(tool, tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "find_ccx", lambda: None)
    with pytest.raises(tool.Refused, match="CalculiX not found"):
        tool.run(str(public_form(tmp_path)), "A. Engineer", pdf=False)
    assert not paths.LOCAL.exists()


def test_the_outcome_file_says_why_a_run_was_refused(tool, tmp_path, monkeypatch):
    """What the API's coupon jobs read (ADR-0050): the status and the message, written even when the run stops before it starts."""
    monkeypatch.setattr(tool, "find_ccx", lambda: None)
    result = tmp_path / "outcome.json"
    monkeypatch.setattr("sys.argv", ["run_coupon.py", str(public_form(tmp_path)), "--run-by", "A. Engineer", "--result", str(result)])
    with pytest.raises(SystemExit, match="CalculiX not found"):
        tool.main()
    outcome = json.loads(result.read_text(encoding="utf-8"))
    assert outcome["status"] == "refused" and "CalculiX not found" in outcome["message"] and outcome["outputs"] == {}
    assert outcome["coupon"] is None and outcome["fea_version"]


def pretend_calculix(tool, monkeypatch) -> None:
    monkeypatch.setattr(tool, "find_ccx", lambda: Path("ccx"))
    monkeypatch.setattr(tool, "ccx_version", lambda ccx: "2.22")
    monkeypatch.setattr("anisotropy_fea.checks.ccx_version", lambda ccx: "2.22")
    monkeypatch.setattr("anisotropy_fea.checks.find_ccx", lambda: Path("ccx"))


def test_a_failed_step_gets_its_row(tool, tmp_path, monkeypatch):
    pretend_calculix(tool, monkeypatch)

    def script(step, args, cwd):  # our engine passes, CalculiX stops the run
        if step == "CalculiX":
            raise tool.StepFailed(f"{step}: run_calculix.py exited with code 1")

    monkeypatch.setattr(tool, "script", script)
    progress_path = tmp_path / "progress.json"
    with pytest.raises(tool.StepFailed):
        tool.run(str(public_values(tmp_path)), "A. Engineer", pdf=False, progress=tool.Progress(progress_path))
    folder = paths.LOCAL / DESIGNATION
    assert read_case(folder).attempts == 2 and [p.name[:10] for p in paths.runs(DESIGNATION).iterdir()] == ["attempt-02"]
    row = next(line for line in (folder / "README.md").read_text(encoding="utf-8").splitlines() if line.startswith("| 02 |"))
    assert "stopped at CalculiX: run_calculix.py exited with code 1" in row
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    assert progress["stage"] == "CalculiX" and progress["done"] == ["the setup check", "the input", "the decks", "the attempt", "our engine"]
    assert set(progress["outputs"]) == {"checklist", "preview"}  # the stand-in engine step wrote nothing; the studio files are there
    assert (folder / "team" / progress["attempt"].rsplit("_", 1)[-1] / "values.json").is_file()  # the values file is filed with the coupon


def test_a_blocked_setup_is_refused_before_anything_is_written(tool, tmp_path, monkeypatch):
    pretend_calculix(tool, monkeypatch)
    with pytest.raises(tool.Refused, match="the setup check blocks the run: Geometry defined: Length \\(mm\\): required"):
        tool.run(str(public_values(tmp_path, length=None)), "A. Engineer", pdf=False)
    assert not paths.LOCAL.exists()
    with pytest.raises(tool.Refused, match="Laminate assigned: 4 plies: the layup is not symmetric"):
        tool.run(str(public_values(tmp_path, symmetric="no")), "A. Engineer", pdf=False)
    assert not paths.LOCAL.exists()


def test_an_attempt_log_behind_its_folders_is_refused(tool, tmp_path, monkeypatch):
    monkeypatch.setattr(tool, "find_ccx", lambda: Path("ccx"))
    monkeypatch.setattr(tool, "ccx_version", lambda ccx: "2.22")
    convert(public_form(tmp_path), root=paths.LOCAL)
    (paths.runs(DESIGNATION) / "attempt-03_2026-10-26" / "run").mkdir(parents=True)  # a run whose rows 02 and 03 were never written
    with pytest.raises(tool.Refused, match="attempt log ends at row 01"):
        tool.run(DESIGNATION, "A. Engineer", pdf=False)
    assert not paths.ours(DESIGNATION).joinpath("decks").exists()


@pytest.mark.parametrize("kind, probes", [("unnotched_tension", "--node-probes centre --element-probes centre"),
                                          ("open_hole_tension", "--node-probes gauge --element-probes far")])
def test_the_record_is_made_as_the_case_page_says(tool, tmp_path, kind, probes):
    record_command = next(c for c in next_commands(tmp_path / DESIGNATION, DESIGNATION, kind) if "record_from_dat.py" in c)
    assert f"--tolerance {tool.TOLERANCE} --floor {tool.FLOOR}" in record_command and probes in record_command
    assert set(tool.LEFT_OUT) == {"open_hole_tension", None}
