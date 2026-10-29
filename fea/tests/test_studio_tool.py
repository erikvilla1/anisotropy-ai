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
    assert sorted(p.name for p in out.iterdir()) == [f"{DESIGNATION}-abaqus.inp", "checklist.json", "explanation.json", "fields.json", "preview.json"]
    fields = json.loads((out / "fields.json").read_text(encoding="utf-8"))
    explanation = json.loads((out / "explanation.json").read_text(encoding="utf-8"))
    assert fields["coupon"]["designation"] == DESIGNATION and fields["summary"]["reaction"]["value"] > 0 and set(fields["summary"]["fpf"]) == {"max_stress", "tsai_hill"}
    assert explanation["writer"] == "template" and explanation["sentences"][0].startswith(f"{DESIGNATION}, unnotched tension")
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
