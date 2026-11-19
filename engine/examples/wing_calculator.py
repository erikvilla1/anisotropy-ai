"""Run a wing file and print its results: `uv run python examples/wing_calculator.py examples/example-wing.toml`.

The file states its units; the results are printed in the same ones. `--stations N` changes the number of
stations along the span (51 when not given).
"""

import argparse
from pathlib import Path

from anisotropy_engine.wing import analyze_wing, load_wing, wing_report


def _margin(value) -> str:
    return "    none" if value is None else f"{value:+8.3f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path)
    parser.add_argument("--stations", type=int, default=51)
    args = parser.parse_args()
    data, wing, envelope = load_wing(args.path)
    result = analyze_wing(wing, envelope, stations=args.stations)
    report = wing_report(result, data["units"], data["envelope"]["speed_unit"])
    u, d = report["units"], report["design"]

    print(f"{report['wing']}: {wing.geometry.airfoil.name}, {len(report['cases'])} cases run, {len(report['not_run'])} not run, "
          f"{report['seconds'] * 1e3:.1f} ms")
    print("\nDesign (the box between the spars, one side)")
    print(f"  mass {d['mass']:.4g} {u['mass']} (skins {d['mass_skins']:.4g}, spars {d['mass_spars']:.4g}, core {d['mass_core']:.4g})")
    print(f"  bending stiffness EI {d['bending_stiffness']:.4g} {u['stiffness']}, torsion stiffness GJ {d['torsion_stiffness']:.4g} {u['stiffness']}")
    print(f"  first bending frequency {d['first_bending_frequency']:.4g} Hz, skin buckling load {d['skin_buckling_load']:.4g} {u['running_load']}")
    print(f"  skin Ex {d['skin_modulus']:.4g} {u['modulus']}, spar Ex {d['spar_modulus']:.4g} {u['modulus']}, "
          f"shear center {d['shear_center']:.4g} {u['length']} from the leading edge")

    proof = envelope.proof_factor is not None
    a = report["aeroelastic"]
    print("\nAeroelastic (the uniform wing, strip theory), equivalent airspeeds")
    for label, key in (("divergence", "divergence"), ("aileron reversal", "reversal")):
        if a[f"{key}_never"]:
            print(f"  {label}: none at any speed" + (" below divergence" if key == "reversal" else " (the aerodynamic center is not ahead of the shear center)"))
        elif a[f"{key}_speed"] is None:
            continue
        else:
            ratio = a[f"{key}_over_dive"]
            print(f"  {label} at {a[f'{key}_speed']:.4g} {u['speed']}" + ("" if ratio is None else f", {ratio:.2f} x the dive speed"))
    for need in a["needs"]:
        print(f"  not run: needs {need}")
    print(f"\nMargins at ultimate load ({envelope.ultimate_factor:g} x limit)" + (f" and at proof load ({envelope.proof_factor:g} x limit)" if proof else ""))
    header = f"{'case':>4} {'':32} {'alt ' + u['altitude']:>8} {'V ' + u['speed']:>8} {'n':>6} {'M root ' + u['moment']:>14} {'tip ' + u['deflection']:>9} | {'skin':>8} {'spar':>8} {'buckling':>8}"
    print(header + (f" | {'proof, lowest':>13}" if proof else ""))
    for c in report["cases"]:
        checks = c["checks"]
        line = (f"{c['number']:>4} {c['label']:32} {c['altitude']:>8.0f} {c['speed']:>8.1f} {c['load_factor']:>+6.2f} {c['root_moment']:>14.5g} "
                f"{c['tip_deflection']:>9.3g} | " + " ".join(_margin(checks[name]["margin_ultimate"]) for name in checks))
        if proof:
            lowest = [checks[name]["margin_proof"] for name in checks if checks[name]["margin_proof"] is not None]
            line += f" | {_margin(min(lowest) if lowest else None):>13}"
        print(line)
    for n in report["not_run"]:
        print(f"{n['number']:>4} {n['label']:32} {n['altitude']:>8.0f}   not run: needs {n['needs']}")

    g = report["governing"]
    if g is not None:
        check = next(c for c in report["cases"] if c["number"] == g["case"] and c["altitude"] == g["altitude"])["checks"][g["check"]]
        where = f"{check['member']}, {check['station']:.3g} {u['length']} from the root"
        if check["ply_angle"] is not None:
            where += f", {check['ply_angle']:g} degree ply, {check['mode']}"
        print(f"\nLowest margin at ultimate: {g['margin_ultimate']:+.3f}, case {g['case']} ({g['label']}) at {g['altitude']:.0f} {u['altitude']}, "
              f"{g['check']}: {where}")
        print("Every case that ran has margins of zero or more." if report["passes"] else "At least one margin is below zero.")


if __name__ == "__main__":
    main()
