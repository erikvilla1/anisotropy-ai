#!/usr/bin/env python3
"""Writes lib/wing-choices.json, what the wing workspace (ADR-0118) offers before it asks the engine anything: the example wing
file as the engine reads it, and the library materials and cores a wing can name (a material with a ply thickness, a density and
all five strengths; a sandwich core). Also writes the browser test's answer to the example wing,
tests/fixtures/wing/example-answer.json: the engine's report and drawings, as the API sends them, with the run time fixed so the
file does not change from run to run; and its answer to the example with the spar caps the page adds and a cap zone from the root to
40 % of the span with one more 0° ply each side of the middle (ADR-0125), tests/fixtures/wing/caps-answer.json.

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
CAPS_ANSWER = ROOT / "tests" / "fixtures" / "wing" / "caps-answer.json"


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


def answer_text(caps: bool = False) -> str:
    return json.dumps(answer(caps), separators=(",", ":"), ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUT.write_text(text(), encoding="utf-8", newline="\n")
    ANSWER.parent.mkdir(parents=True, exist_ok=True)
    ANSWER.write_text(answer_text(), encoding="utf-8", newline="\n")
    CAPS_ANSWER.write_text(answer_text(caps=True), encoding="utf-8", newline="\n")
    sys.stdout.write(f"wrote {OUT.relative_to(ROOT)}, {ANSWER.relative_to(ROOT)} and {CAPS_ANSWER.relative_to(ROOT)}\n")
