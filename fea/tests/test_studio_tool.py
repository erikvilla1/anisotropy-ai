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
