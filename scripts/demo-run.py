#!/usr/bin/env python3
"""Records the run the home page's product demo replays (ADR-0095).

    python3 scripts/demo-run.py

It asks the repository's own solver for its answer to one public example, the IM7 / 8552 tension coupon under ASTM D3039 whose
rows the browser tests already use (tests/fixtures/studio-standards/values.json), through the command the workspace's live
preview runs (`fea/tools/studio_tool.py live`, ADR-0086), and keeps what the demo draws and prints in lib/demo-run.json: the
mesh, the stress along the fibres in every ply of every element, and the summary's numbers. Nothing is computed here; values are
only picked out and rounded. Needs `uv`. The reference solver is not needed: the live command runs our solver alone.
"""

from __future__ import annotations

import datetime
import json
import subprocess
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALUES = ROOT / "tests" / "fixtures" / "studio-standards" / "values.json"
OUT = ROOT / "lib" / "demo-run.json"


def main() -> None:
    values = json.loads(VALUES.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as scratch:
        out = Path(scratch) / "out"
        subprocess.run(
            ["uv", "run", "-q", "python", "tools/studio_tool.py", "--root", str(Path(scratch) / "coupons"), "live", str(VALUES), "--out", str(out)],
            cwd=ROOT / "fea", check=True,
        )
        fields = json.loads((out / "fields.json").read_text(encoding="utf-8"))
        timings = json.loads((out / "timings.json").read_text(encoding="utf-8"))

    mesh, summary = fields["mesh"], fields["summary"]
    stress = fields["element"]["ply"]["stress_12"]  # per element, per ply: along the fibres, across them, in shear
    plies = mesh["plies"]
    along = [[round(stress[element][ply][0], 1) for element in range(mesh["element_count"])] for ply in range(plies)]
    low, high = min(min(ply) for ply in along), max(max(ply) for ply in along)
    tabs = sorted(set(mesh["element_sets"]["Tab-Bottom"]) | set(mesh["element_sets"]["Tab-Top"]))
    first = summary["fpf"]["max_stress"]
    method = summary["test_method"]
    version = tomllib.loads((ROOT / "fea" / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]

    record = {
        "what": "A recorded run of the public IM7 / 8552 tension example",
        "recorded": datetime.date.today().isoformat(),
        "solver_version": version,
        "rows": "tests/fixtures/studio-standards/values.json",
        "units": {"length": fields["labels"]["length"], "force": fields["labels"]["force"], "stress": fields["labels"]["stress"]},
        "coupon": {
            "test": fields["coupon"]["test"],
            "standard": values["standard"],
            "library": values["library"],
            "layup": fields["coupon"]["layup"],
            "angles": mesh["angles"],
            "length": values["length"],
            "width": values["width"],
            "tab_length": values["tab_length"],
            "thickness": round(method["thickness"], 5),
            "pull": round(summary["applied"]["value"], 6),
            "pull_unit": summary["applied"]["unit"],
        },
        "mesh": {
            "nodes": [[round(x, 4), round(y, 4)] for x, y in mesh["nodes"]],
            "quads": mesh["quads"],
            "tabs": tabs,
        },
        "field": {"key": "S11", "unit": fields["labels"]["stress"], "min": low, "max": high, "plies": along},
        "summary": {
            "nodes": mesh["node_count"],
            "elements": mesh["element_count"],
            "solve_seconds": round(timings["solve"], 3),
            "reaction": round(summary["reaction"]["value"], 1),
            "stress": round(method["stress"], 1),
            "first_failure": {
                "ply": first["ply"],
                "angle": first["angle"],
                "mode": first["mode"],
                "place": first["place"],
                "factor": round(first["factor"], 4),
                "fails": first["fails"],
                "applied": round(first["at_failure"]["applied"], 4),
                "applied_unit": first["at_failure"]["unit"],
                "reaction": round(first["at_failure"]["reaction"], 1),
            },
        },
    }
    OUT.write_text(json.dumps(record, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {mesh['node_count']} nodes, {mesh['element_count']} elements, {plies} plies, "
          f"stress along the fibres {low} to {high} {fields['labels']['stress']}, {OUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
