#!/usr/bin/env python3
"""Writes what the repair's page (ADR-0135, ADR-0136) offers before it asks the engine anything, and the answers its tests draw.

    uv run --project engine python scripts/repair-choices.py          # the choices and the hand calculation's answers
    uv run --project fea python scripts/repair-choices.py --solve     # also the solved slices (needs CalculiX, `ccx`)

lib/repair-choices.json holds the two example repair files as the engine reads them (a flush repair in a stepped cut,
engine/examples/example-patch-repair.toml, and a patch bonded on top, engine/examples/example-external-patch-repair.toml) and
the library materials a repair can name: a ply material with a ply thickness. tests/fixtures/repair/ holds the API's answer
to each example (POST /v1/repairs/analyze, with no run id) and, with --solve, the solve of each example's slice (POST
/v1/repairs/solve) and its bond followed until it lets go (POST /v1/repairs/bond, ADR-0140), their run times fixed so the files do
not change from run to run. For the repair's chat (ADR-0136) it also
holds two changes previewed on the flush example (POST /v1/repairs/changes: each step 0.5 in long, and a step added), a sweep of
its step length to a load (POST /v1/repairs/sweeps, with no check) and, with --solve, what the solved slice of that sweep's
pick says of it (the answer's `check`).

`api/tests/test_repairs_api.py` checks that the choices and the hand calculation's answers are what this script writes, and
`fea/tests/test_repair_page.py` that the solved slices are what the solver gives today to the digits the page prints."""

import json
import sys
import tomllib
from pathlib import Path

from anisotropy_engine.library import library_core, library_material, list_datasets
from anisotropy_engine.repair import (RepairChange, RepairSweep, bond_needs, pick_check, preview_change, repair_from_dict, repair_report, repair_views,
                                      solve_needs, sweep_repair)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = {"example": ROOT / "engine" / "examples" / "example-patch-repair.toml",
            "external": ROOT / "engine" / "examples" / "example-external-patch-repair.toml"}
OUT = ROOT / "lib" / "repair-choices.json"
FIXTURES = ROOT / "tests" / "fixtures" / "repair"
# The chat's fixtures: the plan's own words, "make each step 0.5 in" and "add a step", and a sweep to a load between the limit loads
# of a 3 mm and a 4 mm step, so the pick is not the range's first value.
CHANGES = {"example-change": {"action": "set", "quantity": "step_length", "value": 0.5, "unit": "in"},
           "example-step-change": {"action": "add_steps", "count": 1}}
SWEEP = {"quantity": "step_length", "start": 3, "end": 25, "unit": "mm", "load": 230, "load_unit": "N/mm"}


def example(name: str) -> dict:
    return tomllib.loads(EXAMPLES[name].read_text(encoding="utf-8"))


def choices() -> dict:
    materials, seen = [], set()
    for dataset in list_datasets():
        material_id = dataset["material_id"]
        if material_id in seen:
            continue
        seen.add(material_id)
        try:
            library_core(material_id)
            continue  # a sandwich core is no ply
        except ValueError:
            pass
        try:
            record = library_material(material_id)
        except ValueError:
            continue
        if record.ply_thickness_m:
            materials.append({"id": material_id, "name": record.name, "strengths": record.lamina.strengths is not None})
    return {"example": example("example"), "external": example("external"), "materials": materials}


def text() -> str:
    return json.dumps(choices(), indent=1, ensure_ascii=False) + "\n"


def answer(name: str) -> dict:
    """The API's answer to an example repair (POST /v1/repairs/analyze), with no run id."""
    data = example(name)
    repair, load = repair_from_dict(data)
    return {"run_id": None, "engine_version": "0.1.0", "repair": data, "report": repair_report(repair, data["units"], load),
            "views": repair_views(repair, data["units"], load), "needs": solve_needs(repair, load), "bond_needs": bond_needs(repair)}


def answer_text(name: str) -> str:
    return json.dumps(answer(name), separators=(",", ":"), ensure_ascii=False) + "\n"


def solve(name: str) -> dict:
    """The API's answer to the solve of an example's slice (POST /v1/repairs/solve), with no run id and the run time fixed."""
    from anisotropy_fea.repair_model import headline, slice_report, solve_slice

    data = example(name)
    repair, load = repair_from_dict(data)
    report = slice_report(solve_slice(repair, load), data["units"])
    report["model"]["seconds"] = 3.0
    return {"run_id": None, "headline": headline(report), "report": report}


def bond(name: str) -> dict:
    """The API's answer to an example's bond followed until it lets go (POST /v1/repairs/bond, ADR-0140), with no run id and the run
    time fixed."""
    from anisotropy_fea.repair_bond import bond_report, headline, run_bond

    data = example(name)
    report = bond_report(run_bond(repair_from_dict(data)[0]), data["units"])
    report["model"]["seconds"] = 10.0
    return {"run_id": None, "headline": headline(report), "report": report}


def change(name: str) -> dict:
    """The API's preview of a change to the flush example (POST /v1/repairs/changes), with no run id."""
    return {"run_id": None, "engine_version": "0.1.0", **preview_change(example("example"), RepairChange(**CHANGES[name]))}


def sweep() -> dict:
    """The API's answer to the sweep of the flush example (POST /v1/repairs/sweeps) before its pick is solved: no run id, no check."""
    return {"run_id": None, "engine_version": "0.1.0", **sweep_repair(example("example"), RepairSweep(**SWEEP)), "check": None}


def sweep_check() -> dict:
    """What the solved slice of the sweep's pick says of it: the `check` of the API's answer."""
    from anisotropy_fea.repair_model import headline, slice_report, solve_slice

    found = sweep()
    repair, load = repair_from_dict(found["picked"])
    report = slice_report(solve_slice(repair, load), found["picked"]["units"])
    return pick_check(found["target"], report) | {"headline": headline(report)}


def compact(value: dict) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n"


if __name__ == "__main__":
    FIXTURES.mkdir(parents=True, exist_ok=True)
    written = [OUT]
    OUT.write_text(text(), encoding="utf-8", newline="\n")
    for name in EXAMPLES:
        path = FIXTURES / f"{name}-answer.json"
        path.write_text(answer_text(name), encoding="utf-8", newline="\n")
        written.append(path)
        if "--solve" in sys.argv[1:]:
            path = FIXTURES / f"{name}-solve.json"
            path.write_text(json.dumps(solve(name), separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
            written.append(path)
            path = FIXTURES / f"{name}-bond.json"
            path.write_text(compact(bond(name)), encoding="utf-8", newline="\n")
            written.append(path)
    for name, value in ({name: change(name) for name in CHANGES} | {"example-sweep": sweep()}
                        | ({"example-sweep-check": sweep_check()} if "--solve" in sys.argv[1:] else {})).items():
        path = FIXTURES / f"{name}.json"
        path.write_text(compact(value), encoding="utf-8", newline="\n")
        written.append(path)
    sys.stdout.write(f"wrote {', '.join(str(path.relative_to(ROOT)) for path in written)}\n")
