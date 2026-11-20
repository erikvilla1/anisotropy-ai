#!/usr/bin/env python3
"""Writes lib/wing-choices.json, what the wing workspace (ADR-0118) offers before it asks the engine anything: the example wing
file as the engine reads it, and the library materials and cores a wing can name (a material with a ply thickness, a density and
all five strengths, with the bases of strengths it offers; a sandwich core). Also writes the browser test's answer to the example wing,
tests/fixtures/wing/example-answer.json: the engine's report and drawings, as the API sends them, with the run time fixed so the
file does not change from run to run; and its answer to the example with the spar caps the page adds and a cap zone from the root to
40 % of the span with one more 0° ply each side of the middle (ADR-0125), tests/fixtures/wing/caps-answer.json; and the preview of
"Add 2 0 plies to the spar caps from the root to 40% span" on the example with those caps and no zone (ADR-0128), which gives that
zone, tests/fixtures/wing/caps-preview.json; and the preview of two 0° plies added to the example's skin from the root to 40 %, the MCP
server's stand-in answer, tests/fixtures/wing/skin-preview.json.

    uv run --project engine python scripts/wing-choices.py

`api/tests/test_wings_api.py` checks that the files are what this script writes, so a change to the library, the example wing or
the engine's answer fails the tests until the files are written again."""

import json
import sys
import tomllib
from pathlib import Path

from anisotropy_engine.library import library_core, library_material, list_datasets
from anisotropy_engine.wing.analysis import analyze_wing
from anisotropy_engine.wing.changes import PlyChange, preview_change
from anisotropy_engine.wing.wing_file import wing_from_dict, wing_report, wing_views

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "engine" / "examples" / "example-wing.toml"
OUT = ROOT / "lib" / "wing-choices.json"
ANSWER = ROOT / "tests" / "fixtures" / "wing" / "example-answer.json"
CAPS_ANSWER = ROOT / "tests" / "fixtures" / "wing" / "caps-answer.json"
CAPS_PREVIEW = ROOT / "tests" / "fixtures" / "wing" / "caps-preview.json"
SKIN_PREVIEW = ROOT / "tests" / "fixtures" / "wing" / "skin-preview.json"
# the founder's ask of 2026-11-19, as the page reads it (lib/wing-chat.ts)
FOUNDERS = PlyChange(action="add_plies", part="spar_caps", angle=0, count=2, start=0, end=0.4)
SKIN = PlyChange(action="add_plies", part="skin", angle=0, count=2, start=0, end=0.4)


def choices() -> dict:
    materials, cores, seen = [], [], set()
    # the bases of strengths each material offers beside its means (ADR-0126): "B-basis" when the library holds that dataset
    bases = {d["material_id"]: d["strength_basis"] for d in list_datasets() if d["strength_basis"]}
    for dataset in list_datasets():
        material_id = dataset["material_id"]
        if material_id in seen:
            continue
        seen.add(material_id)
        try:
            core = library_core(material_id)
        except ValueError:
            core = None
        if core is not None:
            cores.append({"id": material_id, "name": core.name})
            continue
        try:
            record = library_material(material_id)
        except ValueError:
            continue
        if record.ply_thickness_m and record.density_kg_per_m3 and record.lamina.strengths is not None:
            materials.append({"id": material_id, "name": record.name, "bases": ["mean", *([bases[material_id]] if material_id in bases else [])]})
    return {"example": tomllib.loads(EXAMPLE.read_text(encoding="utf-8")), "materials": materials, "cores": cores}


def text() -> str:
    return json.dumps(choices(), indent=1, ensure_ascii=False) + "\n"


def with_caps(data: dict) -> dict:
    """The example with the spar caps the page's "Add spar caps" gives it (a tenth of the chord to two digits, the skin's plies
    with one more at 0° outside) and a zone from the root to 40 % of the span with one more 0° ply each side of the middle."""
    width = float(f"{0.1 * data['geometry']['chord']:.2g}")
    stack = [0, *data["skin"]["half_stack"]]
    zone = {"start": 0, "end": 0.4, "half_stack": [0, *stack]}
    return data | {"spar_caps": {"front_width": width, "rear_width": width, "half_stack": stack, "zones": [zone]}}


def answer(caps: bool = False) -> dict:
    """The API's answer to the example wing (POST /v1/wings/analyze), with no run id and the run time fixed; with `caps`, to the
    example with its spar caps and a cap zone."""
    data = tomllib.loads(EXAMPLE.read_text(encoding="utf-8"))
    if caps:
        data = with_caps(data)
    result = analyze_wing(*wing_from_dict(data))
    report = wing_report(result, data["units"], data["envelope"]["speed_unit"]) | {"seconds": 0.05}
    return {"run_id": None, "engine_version": "0.1.0", "wing": data, "report": report, "views": wing_views(result, data["units"])}


def without_zones(data: dict) -> dict:
    """The example with its spar caps as the page's "Add spar caps" gives them, before any zone."""
    caps = {key: value for key, value in with_caps(data)["spar_caps"].items() if key != "zones"}
    return data | {"spar_caps": caps}


def preview(skin: bool = False) -> dict:
    """The API's preview of the founder's change on the example with spar caps and no zone (POST /v1/wings/changes), with no run id; with
    `skin`, of two 0° plies added to the example's skin from the root to 40 %."""
    data = tomllib.loads(EXAMPLE.read_text(encoding="utf-8"))
    return {"run_id": None, "engine_version": "0.1.0", **(preview_change(data, SKIN) if skin else preview_change(without_zones(data), FOUNDERS))}


def answer_text(caps: bool = False) -> str:
    return json.dumps(answer(caps), separators=(",", ":"), ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUT.write_text(text(), encoding="utf-8", newline="\n")
    ANSWER.parent.mkdir(parents=True, exist_ok=True)
    ANSWER.write_text(answer_text(), encoding="utf-8", newline="\n")
    CAPS_ANSWER.write_text(answer_text(caps=True), encoding="utf-8", newline="\n")
    for path, skin in ((CAPS_PREVIEW, False), (SKIN_PREVIEW, True)):
        path.write_text(json.dumps(preview(skin), separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    written = ", ".join(str(path.relative_to(ROOT)) for path in (OUT, ANSWER, CAPS_ANSWER, CAPS_PREVIEW, SKIN_PREVIEW))
    sys.stdout.write(f"wrote {written}\n")
