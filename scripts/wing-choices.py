#!/usr/bin/env python3
"""Writes lib/wing-choices.json, what the wing workspace (ADR-0118) offers before it asks the engine anything: the example wing
file as the engine reads it, and the library materials and cores a wing can name (a material with a ply thickness, a density and
all five strengths; a sandwich core). Also writes the browser test's answer to the example wing,
tests/fixtures/wing/example-answer.json: the engine's report and drawings, as the API sends them, with the run time fixed so the
file does not change from run to run.

    uv run --project engine python scripts/wing-choices.py

`api/tests/test_wings_api.py` checks that both files are what this script writes, so a change to the library, the example wing or
the engine's answer fails the tests until the files are written again."""

import json
import sys
import tomllib
from pathlib import Path

from anisotropy_engine.library import library_core, library_material, list_datasets
from anisotropy_engine.wing.analysis import analyze_wing
from anisotropy_engine.wing.wing_file import wing_from_dict, wing_report, wing_views

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "engine" / "examples" / "example-wing.toml"
OUT = ROOT / "lib" / "wing-choices.json"
ANSWER = ROOT / "tests" / "fixtures" / "wing" / "example-answer.json"


def choices() -> dict:
    materials, cores, seen = [], [], set()
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
            materials.append({"id": material_id, "name": record.name})
    return {"example": tomllib.loads(EXAMPLE.read_text(encoding="utf-8")), "materials": materials, "cores": cores}


def text() -> str:
    return json.dumps(choices(), indent=1, ensure_ascii=False) + "\n"


def answer() -> dict:
    """The API's answer to the example wing (POST /v1/wings/analyze), with no run id and the run time fixed."""
    data = tomllib.loads(EXAMPLE.read_text(encoding="utf-8"))
    result = analyze_wing(*wing_from_dict(data))
    report = wing_report(result, data["units"], data["envelope"]["speed_unit"]) | {"seconds": 0.05}
    return {"run_id": None, "engine_version": "0.1.0", "wing": data, "report": report, "views": wing_views(result, data["units"])}


def answer_text() -> str:
    return json.dumps(answer(), separators=(",", ":"), ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUT.write_text(text(), encoding="utf-8", newline="\n")
    ANSWER.parent.mkdir(parents=True, exist_ok=True)
    ANSWER.write_text(answer_text(), encoding="utf-8", newline="\n")
    sys.stdout.write(f"wrote {OUT.relative_to(ROOT)} and {ANSWER.relative_to(ROOT)}\n")
