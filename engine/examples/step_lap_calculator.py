"""A stepped lap bond worked by hand, from a file (ADR-0130).

    uv run python examples/step_lap_calculator.py validation/repair_cases/constructed-flush-three-step-repair.toml

Prints, in the file's units, the patch's force at every step boundary, the adhesive's shear stress at the two ends of every
step, the largest stress in each adherend, and the load at which the largest shear stress reaches the adhesive's strength.
"""

import sys
import tomllib
from pathlib import Path

from anisotropy_engine.repair import lap_from_dict, lap_report


def main(path: str) -> None:
    case = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    lap = lap_from_dict({key: case.get(key) for key in ("units", "adhesive", "steps", "applied")})
    report = lap_report(lap, case["units"])
    force, stress, length = (report["units"][key] for key in ("force", "stress", "length"))
    print(case.get("title", Path(path).stem))
    print(f"Load {case['applied']['load']:g} {force}, {len(lap.steps)} step(s), from the patch's tip to the end of the laminate\n")
    print(f"{'step':>4} {'length':>9} {'lambda L':>9} {'N start':>10} {'N end':>10} {'tau start':>10} {'tau end':>10} {'patch':>10} {'laminate':>10}")
    print(f"{'':>4} {length:>9} {'':>9} {force:>10} {force:>10} {stress:>10} {stress:>10} {stress:>10} {stress:>10}")
    for k, row in enumerate(case["steps"]):
        start, end = report["shear_at_ends"][k]
        outer, inner = report["adherend_stresses"][k]
        print(f"{k + 1:>4} {row['length']:>9g} {report['lambda_length'][k]:>9.3f} {report['boundary_forces'][k]:>10.4g} {report['boundary_forces'][k + 1]:>10.4g} "
              f"{start:>10.4g} {end:>10.4g} {outer:>10.4g} {inner:>10.4g}")
    peak = report["peak_shear"]
    print(f"\nLargest shear stress: {peak['value']:.4g} {stress}, at the {peak['end']} of step {peak['step']}")
    if "elastic_limit_load" in report:
        print(f"Load at the adhesive's elastic limit ({case['adhesive']['shear_strength']:g} {stress}): {report['elastic_limit_load']:.4g} {force}")
    else:
        print("The adhesive states no shear strength, so no load at its elastic limit is given")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
