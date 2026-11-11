"""tools/run_coupon.py (ADR-0049): one command takes a filled-in input form to the coupon's package, adds the attempt's row and
refreshes the case page; a failed step gets its row too; it refuses, before writing anything, without CalculiX or with an attempt
log behind its folders; its record is made as the case page says. Everything runs under a temporary root, never .local/."""

import functools
import importlib.util
import json
import re
import sys
import threading
import time
from pathlib import Path

import pytest

from public_coupon import DESIGNATION
from test_intake import PUBLIC_FILL

from anisotropy_fea import checks, paths
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
    assert outcome.coupon == DESIGNATION and set(outcome.outputs) == {"package", "abaqus_deck", "prepomax_deck", "prepomax_results", "kernel_summary", "convergence",
                                                                      "kernel_vtu", "fields", "explanation", "record", "checklist", "preview"}  # no document without the PDF
    assert all(path.exists() for path in outcome.outputs.values())
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    assert progress["stage"] == "the outputs" and progress["done"] == list(tool.STAGES[:-1]) and progress["coupon"] == DESIGNATION
    assert set(progress["outputs"]) == set(outcome.outputs) and progress["attempt"].endswith(attempt.name)
    assert progress["result"] == outcome.result and outcome.documents == "written"  # the result was reported before the documents (ADR-0064)
    assert all((out / "kernel" / f"{DESIGNATION}{suffix}").is_file() for suffix in ("-model.png", "-solved.png", ".vtu"))  # drawn after it
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
    readme = (package / "README.txt").read_text(encoding="utf-8")
    assert "Attempt:       02 (our attempt this package delivers)" in readme  # this run's, not row 01, the form's reading
    assert (package / "5-verify" / "compare_every_output.py").is_file() and (package / "4-results" / "ours-every-output.csv").is_file()
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
    # The setup check takes its CalculiX finder as a default argument, bound when checks.py was imported, so patching the
    # module's name does not reach it: the tool's own name for the check gets a copy that is told where CalculiX is.
    monkeypatch.setattr(tool, "setup_checklist", functools.partial(checks.setup_checklist, ccx=lambda: Path("ccx")))


def test_a_failing_script_leaves_its_last_words_in_the_message(tool, tmp_path, capsys):
    failing = tmp_path / "fails.py"
    failing.write_text("import sys\nprint('written the deck')\nprint('CalculiX failed on job (exit 255): the SPOOLES solver stopped while ordering')\nsys.exit(1)\n",
                       encoding="utf-8")
    with pytest.raises(tool.StepFailed) as caught:
        tool.script("CalculiX", [str(failing)], tmp_path)
    assert str(caught.value) == "CalculiX: fails.py exited with code 1: CalculiX failed on job (exit 255): the SPOOLES solver stopped while ordering"
    assert "written the deck" in capsys.readouterr().out  # the script's lines still reach the console as they come
    passing = tmp_path / "passes.py"
    passing.write_text("print('fine')\n", encoding="utf-8")
    tool.script("our engine", [str(passing)], tmp_path)


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
    assert progress["stage"] == "CalculiX" and progress["done"] == ["the setup check", "the input", "the decks", "the attempt", "our engine", "the convergence study"]
    assert set(progress["outputs"]) == {"checklist", "preview"}  # the stand-in steps wrote nothing; the studio files are there
    assert (folder / "team" / progress["attempt"].rsplit("_", 1)[-1] / "values.json").is_file()  # the values file is filed with the coupon


def test_a_gated_run_waits_once_the_coupon_is_named_and_before_its_attempt(tool, tmp_path, monkeypatch):
    """The hosted tier's solver claims the coupon at the gate (ADR-0056 amendment 3): the run holds with its specs written and no
    attempt numbered, says so in the progress, and goes on at `go`."""
    pretend_calculix(tool, monkeypatch)
    monkeypatch.setattr(tool, "script", lambda step, args, cwd: None)
    monkeypatch.setattr(tool, "package", lambda name, pdf, theory: (_ for _ in ()).throw(tool.StepFailed("the package: not in this test")))
    progress_path, gate = tmp_path / "progress.json", tmp_path / "gate"
    failure: list[BaseException] = []

    def run():
        try:
            tool.run(str(public_values(tmp_path)), "A. Engineer", pdf=False, progress=tool.Progress(progress_path), gate=gate)
        except BaseException as exc:  # noqa: BLE001  (the stand-in package stops the run; that is what is expected below)
            failure.append(exc)

    worker = threading.Thread(target=run)
    worker.start()
    def read_progress() -> dict:
        """The progress file as it stands, or {} while the tool is halfway through writing it (the write is not atomic)."""
        try:
            return json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.is_file() else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def held_progress(what: str) -> dict:
        deadline = time.monotonic() + 60
        while not read_progress().get("held"):
            assert time.monotonic() < deadline and worker.is_alive(), f"the run never held {what}"
            time.sleep(0.05)
        return read_progress()

    first = held_progress("before the naming")  # the first hold: nothing named, nothing written (ADR-0056 amendment 6)
    assert first["coupon"] is None and first["stage"] == "the setup check" and first["attempt"] is None and not paths.LOCAL.exists()
    gate.write_text("go", encoding="utf-8")
    deadline = time.monotonic() + 60
    while gate.is_file():  # the word is read once and the file removed, so the second hold waits for a fresh word
        assert time.monotonic() < deadline and worker.is_alive(), "the first word at the gate was never read"
        time.sleep(0.05)
    held = held_progress("at the gate")
    assert held["coupon"] == DESIGNATION and held["stage"] == "the input" and held["attempt"] is None
    assert paths.ours(DESIGNATION).joinpath(f"{DESIGNATION}.toml").is_file() and not paths.runs(DESIGNATION).exists()
    gate.write_text("go", encoding="utf-8")
    worker.join(60)
    assert isinstance(failure[0], tool.StepFailed) and "the result" in str(failure[0])  # the stand-in steps wrote nothing
    after = json.loads(progress_path.read_text(encoding="utf-8"))
    assert after["held"] is False and after["attempt"].split("/")[-1].startswith("attempt-02")
    assert {"the setup check", "the input", "the decks", "the attempt", "our engine", "CalculiX", "the CalculiX record"} <= set(after["timings"])
    assert all(isinstance(v, float) and v >= 0 for v in after["timings"].values())  # each finished stage's seconds (ADR-0056 amendment 6)


def test_a_gate_that_says_anything_but_go_refuses_the_run_before_its_attempt(tool, tmp_path, monkeypatch):
    pretend_calculix(tool, monkeypatch)
    gate = tmp_path / "gate"
    gate.write_text("another job is solving this coupon", encoding="utf-8")
    with pytest.raises(tool.Refused, match="another job is solving this coupon"):
        tool.run(str(public_values(tmp_path)), "A. Engineer", pdf=False, gate=gate)
    assert not paths.LOCAL.exists() and not gate.is_file()  # refused at the first hold, before anything is named or written; the word read once


def test_a_blocked_setup_is_refused_before_anything_is_written(tool, tmp_path, monkeypatch):
    pretend_calculix(tool, monkeypatch)
    with pytest.raises(tool.Refused, match="the setup check blocks the run: Geometry defined: Length \\(mm\\): required"):
        tool.run(str(public_values(tmp_path, length=None)), "A. Engineer", pdf=False)
    assert not paths.LOCAL.exists()
    # an unsymmetric layup no longer blocks a run: the flat shell solves it (ADR-0053); a criterion without its constant still does
    with pytest.raises(tool.Refused, match=r"Failure criterion: Tsai-Wu interaction f12\*: required for Tsai-Wu"):
        tool.run(str(public_values(tmp_path, criteria="tsai-wu")), "A. Engineer", pdf=False)
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


def stand_in_steps(tool, monkeypatch, seen: dict) -> None:
    """Every script step writes the files its step names, and the package fails: what the run must report, and when."""
    def script(step, args, cwd):
        out = Path(args[args.index("--out") + 1])
        name = Path(args[1]).stem.removesuffix("-nodal")
        files = {"our engine": ["summary.txt", f"{name}-fields.json", f"{name}-explanation.json"],
                 "CalculiX": [f"{name}-nodal-ccx.inp", f"{name}-nodal-ccx.frd"], "the drawings": [f"{name}.vtu"]}.get(step)
        targets = [out / f for f in files] if files else [out]
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("stand-in", encoding="utf-8")
        seen.setdefault("steps", []).append(step)

    def package(name, pdf, theory, attempt=None):
        seen["result when the package started"] = json.loads(seen["progress"].read_text(encoding="utf-8"))["result"]
        seen["attempt"] = attempt  # the run's own, which the package names
        raise tool.StepFailed("the package: Tectonic stopped")

    monkeypatch.setattr(tool, "script", script)
    monkeypatch.setattr(tool, "package", package)
    monkeypatch.setattr(tool, "outcome_line", lambda folder: "57 of 57 recorded values agree with CalculiX")
    monkeypatch.setattr(tool, "refresh_page", lambda folder: None)  # the stand-in record is no record the case page can read


def test_the_result_is_reported_before_the_documents_and_a_failed_package_leaves_it_standing(tool, tmp_path, monkeypatch):
    """ADR-0064: the progress says the result once the solve and the record are done, before the drawings and the package; a package
    that fails after it is reported on the row and in the outcome, and the run ends done."""
    pretend_calculix(tool, monkeypatch)
    seen = {"progress": tmp_path / "progress.json"}
    stand_in_steps(tool, monkeypatch, seen)
    outcome = tool.run(str(public_values(tmp_path)), "A. Engineer", pdf=True, progress=tool.Progress(seen["progress"]))
    assert seen["steps"] == ["our engine", "the convergence study", "CalculiX", "the CalculiX record", "the drawings"]
    assert seen["result when the package started"] == "57 of 57 recorded values agree with CalculiX"
    assert outcome.result == "57 of 57 recorded values agree with CalculiX" and outcome.result_at is not None
    assert seen["attempt"] == "02"
    assert outcome.documents.startswith("the package not written (the package: Tectonic stopped)")
    assert {"fields", "explanation", "record", "kernel_summary", "kernel_vtu"} <= set(outcome.outputs) and "package" not in outcome.outputs
    row = next(line for line in (paths.LOCAL / DESIGNATION / "README.md").read_text(encoding="utf-8").splitlines() if line.startswith("| 02 |"))
    assert "57 of 57 recorded values agree with CalculiX" in row and "the package not written" in row and "stopped at" not in row
    progress = json.loads(seen["progress"].read_text(encoding="utf-8"))
    assert progress["stage"] == "the outputs" and progress["done"] == list(tool.STAGES[:-1])


def test_the_outcome_file_keeps_the_result_apart_from_a_missing_document(tool, tmp_path, monkeypatch):
    """What the API's coupon jobs read once the run ends (ADR-0050, ADR-0064): done, the result, and what is missing."""
    pretend_calculix(tool, monkeypatch)
    seen = {"progress": tmp_path / "progress.json"}
    stand_in_steps(tool, monkeypatch, seen)
    result = tmp_path / "outcome.json"
    monkeypatch.setattr("sys.argv", ["run_coupon.py", str(public_values(tmp_path)), "--run-by", "A. Engineer", "--result", str(result),
                                     "--progress", str(seen["progress"])])
    tool.main()
    outcome = json.loads(result.read_text(encoding="utf-8"))
    assert outcome["status"] == "done" and outcome["result"] == "57 of 57 recorded values agree with CalculiX"
    assert outcome["documents"].startswith("the package not written") and outcome["message"] == f"{outcome['result']}; {outcome['documents']}"
