"""A stepped patch repair worked from its description (ADR-0131), flush in a stepped cut or bonded on top over a hole.

    uv run python examples/patch_repair_calculator.py examples/example-patch-repair.toml

A case of validation/patch_repair_cases/ reads the same way.

Prints, in the file's units, the repair's sizes, the area and the volume of each kind of part, the bondline's lengths, the
steps of the lap the repair makes and, when the file states a load, the patch's force at every step boundary, the adhesive's
shear stress at the two ends of every step and the load at which the largest one reaches the adhesive's strength.
"""

import sys
import tomllib
from pathlib import Path

from anisotropy_engine.repair import repair_from_dict, repair_report


def main(path: str) -> None:
    case = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    repair, load = repair_from_dict({key: value for key, value in case.items() if key != "expected"})  # a validation case reads too
    report = repair_report(repair, case["units"], load)
    units, sizes, lap = report["units"], report["sizes"], report["lap"]
    length, force, stress = units["length"], units["force"], units["stress"]
    print(case.get("title", Path(path).stem))
    if repair.external:
        print(f"Laminate {sizes['thickness']:.4g} {length} thick, {repair.plies} plies of {repair.parent_material.name}; a {repair.patch_shape} patch of "
              f"{repair.steps} step(s) of {repair.plies_per_step} ply each of {repair.patch_material.name} bonded on top, {sizes['patch_thickness']:.4g} {length} thick")
        print(f"Steps reach {', '.join(f'{r:g}' for r in sizes['cut_radii'])} {length} from the middle (step 1, on the laminate, first); "
              f"the patch is {sizes['patch_diameter']:g} {length} long")
        print(f"Patch plies, from the laminate up: {report['patch_layup']}")
    else:
        print(f"Laminate {sizes['thickness']:.4g} {length} thick, {repair.plies} plies of {repair.parent_material.name}; "
              f"{repair.steps} step(s) of {repair.plies_per_step} ply each remove {sizes['plies_removed']} plies, "
              + ("through every ply" if sizes["through"] else f"{sizes['plies_left']} left under the patch"))
        print(f"Cuts at radius {', '.join(f'{r:g}' for r in sizes['cut_radii'])} {length} (step 1 first); the patch is {sizes['patch_diameter']:g} {length} across"
              + (f", the cover plies {sizes['repair_diameter']:g}" if repair.cover_angles else ""))
        print(f"Patch plies, deepest first: {report['patch_layup']}" + (f"; cover plies: {list(repair.cover_angles)}" if repair.cover_angles else ""))
    print(f"\n{'part':>10} {'area in the slice':>20} {'volume in the panel':>22}")
    for kind in report["areas"]:
        print(f"{kind:>10} {report['areas'][kind]:>14.4f} {units['area']:>5} {report['volumes'][kind]:>16.1f} {units['volume']:>5}")
    bond = report["bond_lengths"]
    if repair.external:
        print(f"\nBondline in the half slice: {bond['top_face']:g} {length} on the laminate's top face")
    else:
        print(f"\nBondline in the half slice: ledges {bond['ledges']:g}, cut faces {bond['cut_faces']:g}, floor {bond['floor']:g}, "
              f"under the cover plies {bond['cover']:g} {length}")
    print("\nThe lap, from the repair's edge inward"
          + (", ending at the repair's middle" if lap["ends_at_the_middle"] else ", ending at the hole's edge" if repair.external else ", ending at the deepest cut"))
    answer = lap.get("answer")
    head = f"{'step':<18} {'length':>8} {'patch t':>8} {'patch E':>9} {'lam. t':>8} {'lam. E':>9}"
    print(head + (f" {'N start':>9} {'N end':>9} {'tau start':>10} {'tau end':>9}" if answer else ""))
    for k, step in enumerate(lap["steps"]):
        row = (f"{step['name']:<18} {step['length']:>8g} {step['patch_thickness']:>8.4g} {step['patch_modulus']:>9.5g} "
               f"{step['laminate_thickness']:>8.4g} {step['laminate_modulus']:>9.5g}")
        if answer:
            start, end = answer["shear_at_ends"][k]
            row += f" {answer['boundary_forces'][k]:>9.4g} {answer['boundary_forces'][k + 1]:>9.4g} {start:>10.4g} {end:>9.4g}"
        print(row)
    print(f"(lengths in {length}, moduli in {units['modulus']}" + (f", forces in {force}, shear stresses in {stress})" if answer else ")"))
    if not answer:
        print("\nThe file states no load, so the lap is not solved")
        return
    peak = answer["peak_shear"]
    print(f"\nUnder {lap['load']:g} {force}: largest shear stress {peak['value']:.4g} {stress}, at the {peak['end']} of {lap['steps'][peak['step'] - 1]['name'].lower()}")
    if "elastic_limit_load" in answer:
        print(f"Load at the adhesive's elastic limit: {answer['elastic_limit_load']:.4g} {force} (not the repair's strength: the adhesive yields before it fails)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
