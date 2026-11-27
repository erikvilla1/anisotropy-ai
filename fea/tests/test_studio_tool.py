"""tools/studio_tool.py (ADR-0051): the check writes the checklist and the preview, the coupons list reads the case pages, a coupon's
values read back, the fixtures hold a solved public coupon, and the form definition the website imports is the package's.
Everything runs under a temporary root, never .local/."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from anisotropy_fea import paths
from anisotropy_fea.intake import FORM_VERSION, convert

from public_coupon import DESIGNATION
from test_intake import PUBLIC_FILL

TOOLS = Path(__file__).parents[1] / "tools"
STUDIO = TOOLS / "studio_tool.py"


def load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def values_file(folder: Path, **changes) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "values.json"
    path.write_text(json.dumps({"form_version": FORM_VERSION, **PUBLIC_FILL, **changes}), encoding="utf-8")
    return path


def run_tool(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(STUDIO), *args], capture_output=True, text=True, encoding="utf-8")


def test_check_writes_the_checklist_and_the_preview(tmp_path):
    out = tmp_path / "out"
    done = run_tool("--root", str(tmp_path / "root"), "check", str(values_file(tmp_path)), "--out", str(out))
    assert done.returncode == 0, done.stderr
    checklist = json.loads((out / "checklist.json").read_text(encoding="utf-8"))
    preview = json.loads((out / "preview.json").read_text(encoding="utf-8"))
    assert checklist["designation"] == DESIGNATION and {item["state"] for item in checklist["items"] if item["id"] not in ("solver", "document")} == {"pass"}
    assert preview["mesh"]["element_count"] == 1200 and preview["loaded"]["value"] == 1.0
    assert done.stdout.startswith(("ready: ", "blocked: ")) and DESIGNATION in done.stdout  # blocked only where CalculiX is missing


def test_check_of_blocked_values_still_exits_0_and_writes_no_preview(tmp_path):
    out = tmp_path / "out"
    done = run_tool("--root", str(tmp_path / "root"), "check", str(values_file(tmp_path, length=None)), "--out", str(out))
    assert done.returncode == 0 and done.stdout.startswith("blocked: ")
    checklist = json.loads((out / "checklist.json").read_text(encoding="utf-8"))
    assert checklist["state"] == "blocked" and not (out / "preview.json").exists()
    assert next(item for item in checklist["items"] if item["id"] == "geometry")["state"] == "missing"


def test_check_of_a_file_that_is_not_values_names_it(tmp_path):
    bad = tmp_path / "values.json"
    bad.write_text("[]", encoding="utf-8")
    out = tmp_path / "out"
    done = run_tool("--root", str(tmp_path / "root"), "check", str(bad), "--out", str(out))
    assert done.returncode == 0 and "one JSON object" in done.stdout
    checklist = json.loads((out / "checklist.json").read_text(encoding="utf-8"))
    assert checklist["state"] == "blocked" and checklist["items"][0]["state"] == "fail" and "one JSON object" in checklist["items"][0]["message"]
    assert {item["state"] for item in checklist["items"][1:]} == {"pending"}


def test_coupons_and_values_read_the_coupons_under_the_root(tmp_path):
    root = tmp_path / "root"
    assert json.loads(run_tool("--root", str(root), "coupons").stdout) == []  # no folder yet
    convert(values_file(tmp_path), root=root, day="2026-10-28")
    [entry] = json.loads(run_tool("--root", str(root), "coupons").stdout)
    assert entry == {"name": DESIGNATION, "designation": DESIGNATION, "kind": "unnotched_tension", "test": "unnotched tension", "title": entry["title"],
                     "layup": "[45/0/-45/90]s", "status": "in progress", "accepted": "01", "attempts": 1, "category": "team test"}
    values = json.loads(run_tool("--root", str(root), "values", DESIGNATION).stdout)
    assert values["form_version"] == FORM_VERSION and values["test"] == "unnotched tension" and values["library"] == "im7-8552"
    assert values["mesh_seeds"] == [28, 27, 10, 27, 28] and values["criteria"] == "all" and values["filled_by"] is None
    missing = run_tool("--root", str(root), "values", "NONE-UNT-L9")
    assert missing.returncode != 0 and "no coupon of that name" in missing.stderr


def test_fixtures_hold_a_solved_public_coupon(tmp_path):
    out = tmp_path / "fixtures"
    done = run_tool("--root", str(tmp_path / "root"), "fixtures", str(values_file(tmp_path)), "--out", str(out))
    assert done.returncode == 0, done.stderr
    assert sorted(p.name for p in out.iterdir()) == ["checklist.json", "explanation.json", "fields.json", "preview.json"]  # the deck is solved in a folder of its own
    fields = json.loads((out / "fields.json").read_text(encoding="utf-8"))
    explanation = json.loads((out / "explanation.json").read_text(encoding="utf-8"))
    assert fields["coupon"]["designation"] == DESIGNATION and fields["summary"]["reaction"]["value"] > 0 and set(fields["summary"]["fpf"]) == {"max_stress", "tsai_hill"}
    assert explanation["writer"] == "template" and explanation["sentences"][0].startswith("By the ")  # the verdict first (ADR-0091 amendment 2)
    assert any(s.startswith("Unnotched tension, [45/0/-45/90]s, under a displacement") for s in explanation["sentences"])
    assert not any(DESIGNATION in s for s in explanation["sentences"])  # the record's name stays out of the words
    assert explanation["setup_sentences"][0].startswith(("The setup is ready to solve", "The setup is blocked"))


def test_the_form_definition_the_website_imports_is_the_packages():
    tool = load_tool("export_form_definition")
    target = paths.ROOT / "lib" / "coupon-form-definition.json"
    assert target.is_file(), "run tools/export_form_definition.py from fea/"
    assert target.read_text(encoding="utf-8").replace("\r\n", "\n") == tool.render(tool.definition()), "run tools/export_form_definition.py from fea/"
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["form_version"] == FORM_VERSION and data["units"] == "mm-MPa"
    keys = [f["key"] for s in data["sections"] for f in s["fields"]]
    assert len(keys) == len(set(keys)) and "criteria" in keys and "f12_star" in keys and keys[0] == "filled_by"
    assert data["tests"]["unnotched tension"] == "unnotched_tension" and data["criteria"][0] == "all"
    assert data["library"][0]["Id"] and "E1 (MPa)" in data["library"][0] and len(data["glossary"]) >= 7


# --- the live solve (ADR-0086) ---------------------------------------------------------------------------------------------------


def test_live_writes_the_kernels_answer_and_its_seconds_but_no_mesh_study(tmp_path):
    out = tmp_path / "live"
    done = run_tool("--root", str(tmp_path / "root"), "live", str(values_file(tmp_path)), "--out", str(out))
    assert done.returncode == 0, done.stderr
    assert f": {DESIGNATION}, solved by our kernel in" in done.stdout  # ready, or blocked only for the full run on a machine without CalculiX
    assert sorted(p.name for p in out.iterdir()) == ["checklist.json", "explanation.json", "fields.json", "preview.json", "summary.json", "timings.json"]
    text = (out / "fields.json").read_text(encoding="utf-8")
    fields, summary = json.loads(text), json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert fields["summary"] == summary and "convergence" not in summary, "a preview carries no mesh study (ADR-0068)"
    assert summary["verdict"]["basis"] == "gauge" and summary["fpf_gauge"], "the answer of ADR-0085"
    assert text.count("\n") == 1, "the fields are written compactly, the largest file by far"
    timings = json.loads((out / "timings.json").read_text(encoding="utf-8"))
    assert {"imports", "check", "deck", "solve", "fields", "write", "total"} <= set(timings) and all(v >= 0 for v in timings.values())
    assert timings["total"] >= timings["check"] + timings["solve"]


def test_live_on_a_blocked_setup_writes_the_checklist_and_solves_nothing(tmp_path):
    values = {"form_version": FORM_VERSION, **{k: v for k, v in PUBLIC_FILL.items() if k != "length"}}
    path = tmp_path / "values.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    out = tmp_path / "live"
    done = run_tool("--root", str(tmp_path / "root"), "live", str(path), "--out", str(out))
    assert done.returncode == 0 and done.stdout.startswith("blocked: nothing solved"), done.stdout + done.stderr
    assert "fields.json" not in {p.name for p in out.iterdir()} and json.loads((out / "checklist.json").read_text(encoding="utf-8"))["state"] == "blocked"


def test_serve_answers_one_request_per_line_and_outlives_a_bad_one(tmp_path):
    worker = subprocess.Popen([sys.executable, str(STUDIO), "--root", str(tmp_path / "root"), "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    try:
        assert json.loads(worker.stdout.readline())["ready"] is True
        values = values_file(tmp_path)
        answers = []
        for request in (json.dumps({"values": str(values), "out": str(tmp_path / "a")}), "not json", json.dumps({"values": str(values), "out": str(tmp_path / "b")})):
            worker.stdin.write(request + "\n")
            worker.stdin.flush()
            answers.append(json.loads(worker.stdout.readline()))
        assert "state" in answers[0] and "JSONDecodeError" in answers[1]["error"] and "state" in answers[2]  # the worker outlived the bad one
        assert (tmp_path / "a" / "fields.json").is_file() and (tmp_path / "b" / "fields.json").is_file()
        assert "imports" not in json.loads((tmp_path / "b" / "timings.json").read_text(encoding="utf-8")), "a warm worker imported once, before"
        worker.stdin.close()
        assert worker.wait(timeout=60) == 0
    finally:
        worker.kill()


def test_live_solves_with_our_kernel_when_only_the_full_runs_tools_are_missing(tmp_path):
    """Without CalculiX and the document builder the full run is blocked, but our kernel needs neither: the preview is answered and the
    checklist still names what the full run lacks (ADR-0086)."""
    import os
    env = {k: v for k, v in os.environ.items() if k not in ("ANISOTROPY_CCX", "ANISOTROPY_TECTONIC")}
    env["PATH"] = str(Path(sys.executable).parent)  # nothing else on the path: no ccx, no tectonic
    out = tmp_path / "live"
    done = subprocess.run([sys.executable, str(STUDIO), "--root", str(tmp_path / "root"), "live", str(values_file(tmp_path)), "--out", str(out)],
                          capture_output=True, text=True, encoding="utf-8", env=env)
    assert done.returncode == 0, done.stderr
    checklist = json.loads((out / "checklist.json").read_text(encoding="utf-8"))
    items = {item["id"]: item["state"] for item in checklist["items"]}
    assert items["solver"] == "fail" and checklist["state"] == "blocked", "the full run is blocked without CalculiX"
    assert (out / "fields.json").is_file() and done.stdout.startswith(f"blocked: {DESIGNATION}, solved by our kernel in")
    assert {k for k, v in items.items() if v in ("fail", "missing")} <= {"solver", "document"}


def refused_coupon(root: Path) -> str:
    """A stored coupon whose spec the current rules refuse: the public D638 dog-bone with its extensometer stretched past the narrow
    section, as a spec saved before that rule existed would be."""
    source = paths.ROOT / "fea" / "checks" / "d638-type-i-plastic" / "d638-type-i-plastic.toml"
    text = source.read_text(encoding="utf-8")
    assert "gauge_length = 50.0" in text
    assert 'designation = "PLASTIC-UNT-L1"' in text
    name = "PLASTIC-UNT-L9"  # a code of its own: the example's L1 names a stack, and a plastic has none
    folder = root / name / paths.OURS
    folder.mkdir(parents=True)
    broken = text.replace("gauge_length = 50.0", "gauge_length = 70.0").replace('designation = "PLASTIC-UNT-L1"', f'designation = "{name}"')
    (folder / f"{name}.toml").write_text(broken, encoding="utf-8")
    return name


def test_a_stored_coupon_the_rules_now_refuse_does_not_stop_the_others(tmp_path):
    """One spec saved under older rules took the hosted studio down on 2026-11-10: every check, live solve and list read every stored
    spec and the first refusal stopped them all. Now it is listed with why, keeps its codes, and the rest go on."""
    root = tmp_path / "root"
    name = refused_coupon(root)
    [entry] = json.loads(run_tool("--root", str(root), "coupons").stdout)
    assert entry["name"] == name and entry["kind"] == "unreadable" and "no longer passes the checks" in entry["problem"] and "gauge_length" in entry["problem"]
    reopened = run_tool("--root", str(root), "values", name)
    assert reopened.returncode != 0 and "cannot be reopened" in reopened.stderr
    out = tmp_path / "check"
    done = run_tool("--root", str(root), "check", str(values_file(tmp_path)), "--out", str(out))
    assert done.returncode == 0, done.stderr
    checklist = json.loads((out / "checklist.json").read_text(encoding="utf-8"))
    assert checklist["designation"] == DESIGNATION and checklist["state"] in ("ready", "blocked")
    live_out = tmp_path / "live"
    assert run_tool("--root", str(root), "live", str(values_file(tmp_path)), "--out", str(live_out)).returncode == 0
    assert (live_out / "fields.json").is_file()


def test_a_refused_coupons_codes_stay_its_own(tmp_path):
    from anisotropy_fea.intake import IntakeError, check_form, designation_for, read_input, stored_coupons

    root = tmp_path / "root"
    name = refused_coupon(root)
    loaded, refused = stored_coupons(root)
    assert loaded == {} and list(refused) == [name] and "gauge_length" in refused[name]
    values = json.loads(values_file(tmp_path).read_text(encoding="utf-8"))
    taking = tmp_path / "taking.json"
    taking.write_text(json.dumps({**values, "material_code": "PLASTIC"}), encoding="utf-8")
    with pytest.raises(IntakeError) as caught:
        designation_for(check_form(read_input(taking)), root)
    assert f"Material code: PLASTIC is held by {name}, whose spec the current rules refuse" in str(caught.value)
    layup = tmp_path / "layup.json"
    layup.write_text(json.dumps({**values, "layup_code": "L9"}), encoding="utf-8")
    with pytest.raises(IntakeError) as caught:
        designation_for(check_form(read_input(layup)), root)
    assert f"Layup code: L9 is held by {name}, whose spec the current rules refuse" in str(caught.value)
    blank = tmp_path / "blank.json"
    blank.write_text(json.dumps({key: value for key, value in values.items() if key not in ("material_code", "layup_code")}), encoding="utf-8")
    named = designation_for(check_form(read_input(blank)), root)
    assert named.material_code != "PLASTIC" and named.layup_code == "L1"  # a blank code never lands on one the refused coupon holds


# ------------------------------------------------------------------------------- the coupons' folder named by the environment (ADR-0106)

def test_the_environment_names_the_coupons_folder_for_a_whole_process(tmp_path):
    """Behind the sign-in the API starts every tool with the folder of coupons of whoever asked: every location in `paths` follows it."""
    import os
    assert paths.coupons_root({}) == paths.ROOT / ".local" / "fea" and paths.coupons_root({paths.COUPONS_ROOT: ""}) == paths.ROOT / ".local" / "fea"
    assert paths.coupons_root({paths.COUPONS_ROOT: str(tmp_path / "mine")}) == tmp_path / "mine"
    with pytest.raises(ValueError, match="must be an absolute path"):
        paths.coupons_root({paths.COUPONS_ROOT: "mine/coupons"})

    mine, theirs = tmp_path / "mine", tmp_path / "theirs"
    convert(values_file(tmp_path), root=mine, day="2026-10-28")
    asked = "from anisotropy_fea import paths; print(paths.LOCAL); print(paths.ours('X')); print([d.name for d in paths.model_dirs()])"
    for root, coupons in ((mine, [DESIGNATION]), (theirs, [])):
        env = {**os.environ, paths.COUPONS_ROOT: str(root)}
        seen = subprocess.run([sys.executable, "-c", asked], capture_output=True, text=True, encoding="utf-8", env=env)
        assert seen.stdout.splitlines() == [str(root), str(root / "X" / "ours"), str(coupons)], seen.stderr
        listed = subprocess.run([sys.executable, str(STUDIO), "coupons"], capture_output=True, text=True, encoding="utf-8", env=env)  # no --root: the environment's
        assert [entry["name"] for entry in json.loads(listed.stdout)] == coupons, listed.stderr
    refused = subprocess.run([sys.executable, str(STUDIO), "coupons"], capture_output=True, text=True, encoding="utf-8",
                             env={**os.environ, paths.COUPONS_ROOT: "mine/coupons"})
    assert refused.returncode != 0 and "must be an absolute path" in refused.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="the stand-in for CalculiX is a shell script")
def test_a_run_reads_the_coupons_of_the_folder_it_was_started_with(tmp_path):
    """`run_coupon.py` by a coupon's name: the coupon is looked for in the environment's folder, and in no other."""
    import os
    mine, theirs = tmp_path / "mine", tmp_path / "theirs"
    convert(values_file(tmp_path), root=mine, day="2026-10-28")
    ccx = tmp_path / "ccx"
    ccx.write_text("#!/bin/sh\necho 'This is Version 2.22'\n", encoding="utf-8")
    ccx.chmod(0o755)
    result = tmp_path / "outcome.json"
    done = subprocess.run([sys.executable, str(TOOLS / "run_coupon.py"), DESIGNATION, "--run-by", "A. Engineer", "--result", str(result)],
                          capture_output=True, text=True, encoding="utf-8", env={**os.environ, paths.COUPONS_ROOT: str(theirs), "ANISOTROPY_CCX": str(ccx)})
    outcome = json.loads(result.read_text(encoding="utf-8"))
    assert done.returncode != 0 and outcome["status"] == "refused"
    assert f"no {DESIGNATION}.toml, {DESIGNATION}-nodal.toml in" in outcome["message"] and str(theirs / DESIGNATION / "ours") in outcome["message"]
    assert not theirs.exists() and (mine / DESIGNATION / "ours" / f"{DESIGNATION}.toml").is_file()


def test_a_warm_worker_is_told_the_coupons_folder_with_each_request(tmp_path):
    """One warm worker answers many people (ADR-0106): a request's own `root` is the folder its coupon is named among, for that
    request alone."""
    mine, theirs = tmp_path / "mine", tmp_path / "theirs"
    values = values_file(tmp_path)
    convert(values, root=mine, day="2026-10-28")
    worker = subprocess.Popen([sys.executable, str(STUDIO), "--root", str(tmp_path / "shared"), "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    try:
        assert json.loads(worker.stdout.readline())["ready"] is True
        answers = {}
        for name, root in (("mine", str(mine)), ("theirs", str(theirs)), ("shared", None), ("relative", "mine/coupons")):
            worker.stdin.write(json.dumps({"values": str(values), "out": str(tmp_path / name), **({} if root is None else {"root": root})}) + "\n")
            worker.stdin.flush()
            answers[name] = json.loads(worker.stdout.readline())
        exists = {name: json.loads((tmp_path / name / "checklist.json").read_text(encoding="utf-8"))["coupon_exists"] for name in ("mine", "theirs", "shared")}
        assert exists == {"mine": True, "theirs": False, "shared": False}  # the coupon is mine alone
        assert "a request's root is an absolute path" in answers["relative"]["error"] and "state" in answers["shared"]
        worker.stdin.close()
        assert worker.wait(timeout=60) == 0
    finally:
        worker.kill()


# --- the model as a file for another program (ADR-0129) --------------------------------------------------------------------------


@pytest.mark.parametrize("program, ending, first", [("abaqus", "-abaqus.inp", "*Heading"), ("ansys", "-ansys.cdb", "! Generated by anisotropy_fea")])
def test_model_writes_the_file_of_the_program_asked_for_and_solves_nothing(tmp_path, program, ending, first):
    import hashlib

    out = tmp_path / "model"
    done = run_tool("--root", str(tmp_path / "root"), "model", str(values_file(tmp_path)), "--program", program, "--out", str(out))
    assert done.returncode == 0, done.stderr
    head = json.loads((out / "model.json").read_text(encoding="utf-8"))
    name = DESIGNATION + ending
    assert head["state"] == "written" and head["program"] == program and head["name"] == name and head["units"] == "mm-MPa"
    assert sorted(p.name for p in out.iterdir()) == sorted(["checklist.json", "model.json", name])  # no fields, no summary: nothing was solved
    data = (out / name).read_bytes()
    assert data.decode("utf-8").startswith(first) and head["bytes"] == len(data) and head["sha256"] == hashlib.sha256(data).hexdigest()
    assert head["elements"] == 1200 and done.stdout.startswith(f"written: {name}")
    if program == "abaqus":  # how Abaqus/CAE opens it is said first, as comments: Import > Part reads the mesh alone (ADR-0129 amendment 5)
        from anisotropy_fea.write_abaqus import OPENING, _comment

        lines = data.decode("utf-8").splitlines()
        said = [piece for line in OPENING for piece in _comment(line)]
        assert lines[1].startswith("** To open this file in Abaqus/CAE: File > Import > Model.")
        assert lines[1:1 + len(said)] == said and all(line.startswith("** ") and len(line.encode()) <= 256 for line in said)
        assert lines[1 + len(said)].startswith("** Generated by anisotropy_fea")  # then the deck a run writes, unchanged


def test_model_of_a_blocked_setup_writes_the_checklist_alone(tmp_path):
    out = tmp_path / "model"
    done = run_tool("--root", str(tmp_path / "root"), "model", str(values_file(tmp_path, length=None)), "--program", "ansys", "--out", str(out))
    assert done.returncode == 0 and done.stdout.startswith("blocked: no model written"), done.stdout + done.stderr
    assert [p.name for p in out.iterdir()] == ["checklist.json"]
    refused = run_tool("--root", str(tmp_path / "root"), "model", str(values_file(tmp_path)), "--program", "nastran", "--out", str(out))
    assert refused.returncode != 0 and "invalid choice" in refused.stderr


def test_a_mesh_past_the_limit_is_refused_before_meshing_and_the_file_for_another_program_is_still_written(tmp_path):
    """Our kernel builds at most 40,000 elements in one model, judged from the counts before meshing (ADR-0086 amendment 1: a million
    elements took 12 GB on 2026-11-25): the check names an element size that fits, and nothing is solved. The file for Abaqus or Ansys is
    not held to it, since it runs on the engineer's own machine (the founder, 2026-11-24)."""
    fine = {"element_size": 0.38, "mesh_nx": None, "mesh_partitions": None, "mesh_seeds": None}
    out = tmp_path / "live"
    done = run_tool("--root", str(tmp_path / "root"), "live", str(values_file(tmp_path / "live-values", **fine)), "--out", str(out))
    assert done.returncode == 0 and done.stdout.startswith("blocked: nothing solved"), done.stdout + done.stderr
    mesh = next(item for item in json.loads((out / "checklist.json").read_text(encoding="utf-8"))["items"] if item["id"] == "mesh")
    count = int(mesh["message"].split(" elements;")[0].rsplit(" ", 1)[1].replace(",", ""))
    assert mesh["state"] == "fail" and count > 40_000 and mesh["message"].endswith("our solver takes at most 40,000 in one model: use an element size "
                                                                                  "of 0.4 mm or more"), mesh
    # a size of 100 or more is printed plainly, "160 mm", never "1.6e+02 mm": a coupon 100 m long, which once ran the check out of memory
    huge = {**fine, "element_size": 2.0, "length": 100000.0, "width": 10000.0, "tab_length": 5000.0}
    big = tmp_path / "huge"
    done = run_tool("--root", str(tmp_path / "root"), "check", str(values_file(tmp_path / "huge-values", **huge)), "--out", str(big))
    mesh = next(item for item in json.loads((big / "checklist.json").read_text(encoding="utf-8"))["items"] if item["id"] == "mesh")
    assert mesh["state"] == "fail" and mesh["message"] == ("the mesh would have 250,000,000 elements; our solver takes at most 40,000 in one model: "
                                                           "use an element size of 160 mm or more"), mesh
    model = tmp_path / "model"
    written = run_tool("--root", str(tmp_path / "root"), "model", str(values_file(tmp_path / "model-values", **fine)), "--program", "abaqus",
                       "--out", str(model))
    assert written.returncode == 0 and written.stdout.startswith("written: "), written.stdout + written.stderr
    assert json.loads((model / "model.json").read_text(encoding="utf-8"))["elements"] == count  # the count the check judged, before meshing


def run_tool_bounded(*args: str, gigabytes: int = 4, seconds: int = 60) -> subprocess.CompletedProcess:
    """The tool with a limit on its memory and its time, so that a test of a setup that once exhausted both fails here and takes
    nothing else down with it."""
    import resource

    def limit():
        resource.setrlimit(resource.RLIMIT_AS, (gigabytes * 2 ** 30, gigabytes * 2 ** 30))

    return subprocess.run([sys.executable, str(STUDIO), *args], capture_output=True, text=True, encoding="utf-8", preexec_fn=limit, timeout=seconds)


SEEDED = {"element_size": None, "mesh_partitions": "56, 110, 140, 194"}
PAST_THE_MOST = [  # the rows, the count the refusal states, what it says to change, and the rows it names
    ({"element_size": 1e-5}, "more than 1,000,000,000,000", "use an element size of 0.18 mm or more", ["Element size (mm)"]),
    ({"element_size": 1e-6}, "more than 1,000,000,000,000", "use an element size of 0.18 mm or more", ["Element size (mm)"]),
    ({"element_size": 5e-324}, "more than 1,000,000,000,000", "use an element size of 0.18 mm or more", ["Element size (mm)"]),
    ({"element_size": 0.1}, "625,000", "use an element size of 0.18 mm or more", ["Element size (mm)"]),
    ({**SEEDED, "mesh_nx": 10, "mesh_seeds": "28, 27, 99999999999, 27, 28"}, "more than 1,000,000,000,000",
     "give fewer elements across the width or fewer rows per segment", ["Your Abaqus mesh: elements across the width", "Your Abaqus mesh: rows per segment"]),
    ({**SEEDED, "mesh_nx": 10 ** 12, "mesh_seeds": "28, 27, 10, 27, 28"}, "more than 1,000,000,000,000",
     "give fewer elements across the width or fewer rows per segment", ["Your Abaqus mesh: elements across the width", "Your Abaqus mesh: rows per segment"]),
]


@pytest.mark.parametrize("program", ["abaqus", "ansys", "step"])
@pytest.mark.parametrize("changes, count, change, rows", PAST_THE_MOST, ids=["1e-5 mm", "1e-6 mm", "5e-324 mm", "0.1 mm", "99999999999 rows", "nx 1e12"])
def test_a_setup_past_the_most_elements_a_setup_holds_is_blocked_for_every_file_in_a_moment_and_in_little_memory(tmp_path, program, changes, count,
                                                                                                             change, rows):
    """A setup may state at most 200,000 elements, whatever is made of it (ADR-0086 amendment 2). Before, an element size of 1e-5 mm cost
    a STEP file 12 s and 1.2 GB and 1e-6 mm over 10 GB, and 99999999999 rows in a segment ended every program's request at its 30 s:
    the spec was made, and one row built per element row, before anything was judged. The tool runs here under 4 GB and 60 s."""
    import time

    fine = {"mesh_nx": None, "mesh_partitions": None, "mesh_seeds": None, **changes}
    out = tmp_path / "model"
    clock = time.perf_counter()
    done = run_tool_bounded("--root", str(tmp_path / "root"), "model", str(values_file(tmp_path, **fine)), "--program", program, "--out", str(out))
    seconds = time.perf_counter() - clock
    assert done.returncode == 0 and done.stdout.startswith("blocked: no model written"), done.stdout[-300:] + done.stderr[-600:]
    assert [p.name for p in out.iterdir()] == ["checklist.json"]
    checklist = json.loads((out / "checklist.json").read_text(encoding="utf-8"))
    mesh = next(item for item in checklist["items"] if item["id"] == "mesh")
    said = f"the mesh would have {count} elements; a setup holds at most 200,000, whatever is made of it: {change}"
    assert mesh["state"] == "fail" and mesh["message"] == said and mesh["rows"] == rows and checklist["problems"] == [said], mesh
    assert seconds < 20.0, seconds  # the tool's own start is most of it


def test_a_run_past_the_most_a_setup_holds_is_refused_in_the_solvers_own_words_as_before(tmp_path):
    """For a run the limit that concerns the engineer is the solver's 40,000 (ADR-0086 amendment 1): its words stand, whatever the count."""
    fine = {"element_size": 1e-6, "mesh_nx": None, "mesh_partitions": None, "mesh_seeds": None}
    for command in ("live", "check"):
        out = tmp_path / command
        done = run_tool_bounded("--root", str(tmp_path / "root"), command, str(values_file(tmp_path / f"{command}-values", **fine)), "--out", str(out))
        assert done.returncode == 0, done.stdout[-300:] + done.stderr[-600:]
        mesh = next(item for item in json.loads((out / "checklist.json").read_text(encoding="utf-8"))["items"] if item["id"] == "mesh")
        assert mesh["state"] == "fail" and mesh["message"] == ("the mesh would have more than 1,000,000,000,000 elements; our solver takes at most 40,000 "
                                                               "in one model: use an element size of 0.4 mm or more"), mesh


def test_the_most_a_setup_holds_is_no_less_than_the_file_for_another_program_was_ever_written_with(tmp_path):
    """The limit is the largest mesh the model file's route was measured to write inside its 30 s (2026-11-27: 200,208 elements in 26 to
    28 s, 399,854 in 51 to 54 s, which the route ended first), so it refuses no file that route delivered. A mesh past the solver's
    40,000 and inside it is still written, as the founder asked (2026-11-24)."""
    from anisotropy_fea.spec import MOST_ELEMENTS, MOST_ELEMENTS_STATED

    assert MOST_ELEMENTS_STATED == 200_000 and MOST_ELEMENTS == 40_000
    fine = {"element_size": 0.3, "mesh_nx": None, "mesh_partitions": None, "mesh_seeds": None}
    out = tmp_path / "model"
    written = run_tool("--root", str(tmp_path / "root"), "model", str(values_file(tmp_path, **fine)), "--program", "ansys", "--out", str(out))
    assert written.returncode == 0 and written.stdout.startswith("written: "), written.stdout + written.stderr
    assert MOST_ELEMENTS < json.loads((out / "model.json").read_text(encoding="utf-8"))["elements"] <= MOST_ELEMENTS_STATED


@pytest.mark.parametrize("word", ["w" * 200, "\u00e9" * 100, "\u03b1" * 100, "\u4e2d" * 66, "\U0001F600" * 50],
                         ids=["ascii", "two bytes, a plain form", "two bytes", "three bytes", "four bytes"])
def test_a_word_at_its_limit_fits_a_line_of_each_file_and_the_abaqus_file_holds_it_as_typed(tmp_path, word):
    """What a model file holds (ADR-0146): a line of an Abaqus input file 256 bytes, the text as typed in UTF-8; a line of a Mechanical
    APDL file 640 characters of ASCII, a letter outside ASCII written as its plain form or its code. Neither writer cuts a word, so the
    intake bounds a word at 200 bytes and a tab's material at 80; a word of 5000 once stopped both writers, and the route said 503."""
    rows = {"size_from": f"see {word} there", "team_model": word, "test_data": f"{word} {word}", "tab_thickness": 1.5, "tab_bevel": 30,
            "tab_material": word[:80 // len(word[0].encode("utf-8"))]}
    assert len(rows["tab_material"].encode("utf-8")) in (78, 80)
    for program, most, counted in (("abaqus", 256, lambda line: len(line.encode("utf-8"))), ("ansys", 640, len)):
        out = tmp_path / program
        done = run_tool("--root", str(tmp_path / "root"), "model", str(values_file(tmp_path / f"{program}-values", **rows)), "--program", program,
                        "--out", str(out))
        assert done.returncode == 0 and done.stdout.startswith("written: "), done.stdout[-300:] + done.stderr[-600:]
        text = (out / json.loads((out / "model.json").read_text(encoding="utf-8"))["name"]).read_text(encoding="utf-8")
        assert max(counted(line) for line in text.splitlines()) <= most
        if program == "abaqus":
            assert text.count(word) == 4  # once in each of two rows and twice in the third, never changed and never cut
        else:
            assert text.isascii()
    refused = run_tool("--root", str(tmp_path / "root"), "model", str(values_file(tmp_path / "long", size_from=word + word[0])), "--program", "abaqus",
                       "--out", str(tmp_path / "long-out"))
    assert refused.returncode == 0 and refused.stdout.startswith("blocked: no model written"), refused.stdout + refused.stderr
    problems = json.loads((tmp_path / "long-out" / "checklist.json").read_text(encoding="utf-8"))["problems"]
    assert len(problems) == 1 and "Where the size comes from: one word of it takes" in problems[0] and "holds a word of at most 200" in problems[0]


def test_the_text_rows_bounded_for_a_file_are_the_rows_the_files_hold(tmp_path):
    """The bound on a word is put on the rows a writer puts into a file (`intake.FILE_TEXT`), and on no other: this reads each program's
    file for every free text row, so a row a writer starts to write is seen here before a long word of it stops that writer."""
    from anisotropy_fea.intake import FIELDS, FILE_TEXT
    from test_intake import own_constants

    marks = {"filled_by": "QFB", "notes": "QNT", "size_from": "QSF", "team_model": "QTM", "test_data": "QTD", "own_source": "QOS", "tab_material": "QTB"}
    assert all(FIELDS[key].kind == "text" for key in marks)
    rows = {**own_constants(), **{key: f"{mark} words" for key, mark in marks.items()}, "tab_thickness": 1.5, "tab_bevel": 30}
    for program in ("abaqus", "ansys"):
        out = tmp_path / program
        done = run_tool("--root", str(tmp_path / "root"), "model", str(values_file(tmp_path / f"{program}-values", **rows)), "--program", program,
                        "--out", str(out))
        assert done.returncode == 0 and done.stdout.startswith("written: "), done.stdout[-300:] + done.stderr[-600:]
        text = (out / json.loads((out / "model.json").read_text(encoding="utf-8"))["name"]).read_text(encoding="utf-8")
        assert {key for key, mark in marks.items() if mark in text} == {*FILE_TEXT, "tab_material"}, program


def test_serve_writes_a_model_for_a_request_that_names_a_program(tmp_path):
    worker = subprocess.Popen([sys.executable, str(STUDIO), "--root", str(tmp_path / "root"), "serve"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    try:
        assert json.loads(worker.stdout.readline())["ready"] is True
        values = values_file(tmp_path)
        answers = []
        for request in ({"values": str(values), "out": str(tmp_path / "a"), "model": "ansys"}, {"values": str(values), "out": str(tmp_path / "b"), "model": "nastran"},
                        {"values": str(values), "out": str(tmp_path / "c")}):
            worker.stdin.write(json.dumps(request) + "\n")
            worker.stdin.flush()
            answers.append(json.loads(worker.stdout.readline()))
        assert answers[0] == {"state": "written"} and "a model is written for abaqus or ansys" in answers[1]["error"] and "state" in answers[2]
        assert (tmp_path / "a" / f"{DESIGNATION}-ansys.cdb").is_file() and not (tmp_path / "a" / "fields.json").exists()
        assert (tmp_path / "c" / "fields.json").is_file()  # a request without a program is a live solve, as before
        worker.stdin.close()
        assert worker.wait(timeout=60) == 0
    finally:
        worker.kill()
