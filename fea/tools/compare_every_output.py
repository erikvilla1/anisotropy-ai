"""Our every output beside your Abaqus run's, element by element and ply by ply, judged by zone: the comparison the team's engineers run
on a coupon package (ADR-0089 amendment 3).

    abaqus python compare_every_output.py <package>/4-results/ours-every-output.csv <job>-every-output.csv [--out <file>.csv]

Plain Python 3, the standard library only: Abaqus's own Python runs it (Abaqus 2024 or later), as does any other Python 3. The first file
is ours, from the package, with `ours-every-output.json` beside it (the zones' lines, our reaction, the acceptance). The second is yours,
written from your job's ODB by `abaqus python abaqus_every_output.py <job>.odb --out <folder>`, which also writes
`<job>-every-output-RF.csv`, the reactions, read from beside it unless `--rf` names it.

Your model is paired with ours element by element: by label when your element numbers are ours (you ran our deck), else by position (you
built the coupon in Abaqus/CAE with the same partitions and seeds). A coupon placed elsewhere is moved onto ours by the offset of the two
meshes' corners, and the comparison says so; a different mesh is refused, with how many of our elements found none of yours.

Each value of ours is judged against yours, the reference: it agrees within a tolerance when the difference is within that share of your
value, or of 2 % of the quantity's largest magnitude in your gauge for a small value (ADR-0066's floor). The verdict is ADR-0089's
acceptance: the reaction and every gauge value within 1 %, every free-length value within 3 %; the band and the tab lines beside the
clamped edges, and the gripped tabs, are reported, not judged. `--out` writes every pair, every quantity: yours, ours, the difference.
"""

import argparse
import csv
import json
import math
import sys
from pathlib import Path

QUANTITIES = ("S11", "S22", "S12", "Mises", "Tresca", "Pressure", "Max. Principal", "Mid. Principal", "Min. Principal", "E11", "E22", "E12")
ZONES = ("gauge", "free length", "band", "tab line", "gripped")
PAIRING = 0.01  # two centroids are the same place within 1 % of the mean element size


class Refused(Exception):
    pass


def read_rows(path, ours):
    """{(element, layer): {"x", "y", "zone" (ours only), quantity: value}} from an every-output CSV."""
    out = {}
    with open(str(path), encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        wanted = ("Element", "Layer", "X", "Y") + QUANTITIES + (("Zone",) if ours else ())
        missing = [name for name in wanted if name not in (reader.fieldnames or ())]
        if missing:
            raise Refused(f"{path} has no column {', '.join(missing)}: is it {'ours from the package' if ours else 'what abaqus_every_output.py wrote'}?")
        for row in reader:
            try:
                key = (int(row["Element"]), int(row["Layer"]))
                values = {name: float(row[name]) for name in ("X", "Y") + QUANTITIES}
            except ValueError as exc:
                raise Refused(f"{path}, element {row.get('Element')} layer {row.get('Layer')}: {exc}") from None
            if not all(math.isfinite(v) for v in values.values()):
                raise Refused(f"{path}, element {key[0]} layer {key[1]}: a value that is not a number")
            if ours:
                values["zone"] = row["Zone"]
            if key in out:
                raise Refused(f"{path}: element {key[0]} layer {key[1]} is listed twice")
            out[key] = values
    if not out:
        raise Refused(f"{path} holds no rows")
    return out


def centroids(rows):
    return {key[0]: (values["X"], values["Y"]) for key, values in rows.items()}


def mean_size(points):
    xs, ys = [p[0] for p in points.values()], [p[1] for p in points.values()]
    area = (max(xs) - min(xs)) * (max(ys) - min(ys))
    return math.sqrt(area / len(points)) if area > 0 else 1.0


def match(ours, yours, shift, tolerance):
    """Our element -> yours at the same place after moving yours by `shift`, or None when one of ours finds none."""
    cell = {}
    for label, (x, y) in yours.items():
        cell.setdefault((round((x + shift[0]) / tolerance), round((y + shift[1]) / tolerance)), []).append((label, x + shift[0], y + shift[1]))
    out, unpaired = {}, 0
    for label, (x, y) in ours.items():
        i, j = round(x / tolerance), round(y / tolerance)
        near = [c for di in (-1, 0, 1) for dj in (-1, 0, 1) for c in cell.get((i + di, j + dj), ())
                if math.hypot(c[1] - x, c[2] - y) <= tolerance]
        if not near:
            unpaired += 1
            continue
        out[label] = min(near, key=lambda c: math.hypot(c[1] - x, c[2] - y))[0]
    return out, unpaired


def pair(ours_rows, your_rows):
    """Our element -> yours, how they were paired, and the shift that moved your coupon onto ours."""
    ours, yours = centroids(ours_rows), centroids(your_rows)
    if len(yours) != len(ours):
        raise Refused(f"your model has {len(yours)} elements and ours {len(ours)}: not the same mesh (the package's PDF, Chapter 4, Mesh: "
                      "the partition lines and the seeds by number)")
    layers = {k[1] for k in ours_rows}
    if {k[1] for k in your_rows} != layers:
        raise Refused(f"your model has layers {sorted({k[1] for k in your_rows})} and ours {sorted(layers)}")
    tolerance = PAIRING * mean_size(ours)
    if set(yours) == set(ours) and all(math.hypot(yours[e][0] - ours[e][0], yours[e][1] - ours[e][1]) <= tolerance for e in ours):
        return {e: e for e in ours}, "by element number: your elements are ours", (0.0, 0.0)
    corner = lambda points: (min(p[0] for p in points.values()), min(p[1] for p in points.values()))  # noqa: E731
    (ox, oy), (yx, yy) = corner(ours), corner(yours)
    best = None
    for shift in ((0.0, 0.0), (ox - yx, oy - yy)):
        mapping, unpaired = match(ours, yours, shift, tolerance)
        if not unpaired and len(set(mapping.values())) == len(mapping):
            how = "by position: your element at the centroid of each of ours"
            if shift != (0.0, 0.0):
                how += f", after moving your coupon by ({shift[0]:.6g}, {shift[1]:.6g}) so that the two meshes' corners meet"
            return mapping, how, shift
        best = unpaired if best is None else min(best, unpaired)
    raise Refused(f"{best} of our {len(ours)} elements have no element of yours at the same place: not the same mesh, or the coupon lies "
                  "along another axis (ours: the width along X, the length, the pull, along Y; the package's PDF, Chapter 4)")


def compare(ours_rows, your_rows, mapping, floor):
    """Per zone and quantity: the count, how many within 1 % and 3 %, the worst difference and where; and every pair's differences."""
    pairs = [(key, (mapping[key[0]], key[1])) for key in sorted(ours_rows)]
    gauge = [yk for ok, yk in pairs if ours_rows[ok]["zone"] == "gauge"] or [yk for _, yk in pairs]
    scales = {q: max(abs(your_rows[k][q]) for k in gauge) for q in QUANTITIES}
    tables, differences = {}, {}
    for ok, yk in pairs:
        for q in QUANTITIES:
            a, o = your_rows[yk][q], ours_rows[ok][q]
            denominator = max(abs(a), floor * scales[q]) if scales[q] > 0 else 1.0
            differences[(ok, q)] = abs(o - a) / denominator if denominator > 0 else 0.0
    for zone in ZONES:
        keys = [(ok, yk) for ok, yk in pairs if ours_rows[ok]["zone"] == zone]
        if not keys:
            continue
        table = {"elements": len({ok[0] for ok, _ in keys})}
        for q in QUANTITIES:
            worst = max(keys, key=lambda p: differences[(p[0], q)])
            table[q] = {"values": len(keys), "within_1": sum(differences[(ok, q)] <= 0.01 for ok, _ in keys),
                        "within_3": sum(differences[(ok, q)] <= 0.03 for ok, _ in keys), "worst": differences[(worst[0], q)],
                        "our_element": worst[0][0], "your_element": worst[1][0], "layer": worst[0][1],
                        "yours": your_rows[worst[1]][q], "ours": ours_rows[worst[0]][q]}
        tables[zone] = table
    return tables, differences, pairs


def reaction(rf_path, meta, shift):
    """Your RF2 summed over the nodes of the top grip, at or above the top tab line, beside ours over the same nodes."""
    if rf_path is None or not Path(rf_path).is_file():
        return None
    top = meta["reaction"]["top_from"]
    tolerance = 1e-6 * max(1.0, abs(top))
    with open(str(rf_path), encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if float(row["Y"]) + shift[1] >= top - tolerance]
    if not rows:
        raise Refused(f"{rf_path}: no reaction at or above the top tab line, Y = {top:g} {meta['length_unit']}")
    yours = sum(float(row["RF2"]) for row in rows)
    ours = meta["reaction"]["ours"]
    return {"nodes": len(rows), "yours": yours, "ours": ours, "difference": (ours - yours) / abs(yours) if yours else float("inf")}


def verdict(tables, rf, acceptance):
    """ADR-0089's acceptance, criterion by criterion: (criterion, met, the evidence)."""
    out = []
    if rf is None:
        out.append(("Reaction within 1 %", None, "no reactions read: write them with abaqus_every_output.py (RF in the field output)"))
    else:
        out.append((f"Reaction within {100 * acceptance['reaction']:g} %", abs(rf["difference"]) <= acceptance["reaction"],
                    f"ours {100 * rf['difference']:+.3f} % from yours"))
    for zone in ("gauge", "free length"):
        limit = acceptance[zone]
        if zone not in tables:
            out.append((f"{zone.capitalize()}: every value within {100 * limit:g} %", None, "no element in this zone"))
            continue
        t = tables[zone]
        total = sum(t[q]["values"] for q in QUANTITIES)
        worst_q = max(QUANTITIES, key=lambda q: t[q]["worst"])
        met = all(t[q]["worst"] <= limit for q in QUANTITIES)
        out.append((f"{zone.capitalize()}: every value within {100 * limit:g} %", met,
                    f"{total} values, the worst {100 * t[worst_q]['worst']:.4g} % ({worst_q})"))
    return out


def write_pairs(path, ours_rows, your_rows, pairs, differences):
    with open(str(path), "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["Our element", "Your element", "Layer", "Zone", "X", "Y"]
                        + [f"{q} {side}" for q in QUANTITIES for side in ("yours", "ours", "difference (%)")])
        for ok, yk in pairs:
            o, y = ours_rows[ok], your_rows[yk]
            writer.writerow([ok[0], yk[0], ok[1], o["zone"], f"{o['X']:.9g}", f"{o['Y']:.9g}"]
                            + [v for q in QUANTITIES for v in (f"{y[q]:.9g}", f"{o[q]:.9g}", f"{100 * differences[(ok, q)]:.4g}")])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ours", type=Path, help="ours-every-output.csv from the package's 4-results folder")
    parser.add_argument("yours", type=Path, help="<job>-every-output.csv, from abaqus_every_output.py")
    parser.add_argument("--rf", type=Path, default=None, help="<job>-every-output-RF.csv; default beside your CSV")
    parser.add_argument("--out", type=Path, default=None, help="write every pair and quantity to this CSV")
    args = parser.parse_args(argv)
    meta_path = args.ours.with_suffix(".json")
    if not meta_path.is_file():
        raise Refused(f"no {meta_path.name} beside {args.ours}: take both files from the package's 4-results folder")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    ours_rows, your_rows = read_rows(args.ours, True), read_rows(args.yours, False)
    mapping, how, shift = pair(ours_rows, your_rows)
    tables, differences, pairs = compare(ours_rows, your_rows, mapping, meta["floor"])
    rf = args.rf or args.yours.with_name(args.yours.name.replace("-every-output.csv", "-every-output-RF.csv"))
    rf_result = reaction(rf, meta, shift)
    unit = meta["stress_unit"]
    print(f"{meta['coupon']}: ours ({meta['written_by']}, {meta['element']} deck) beside {args.yours.name}")
    print(f"paired {len(mapping)} elements x {meta['layers']} plies {how}")
    print(f"a value agrees within a share of yours, or of {100 * meta['floor']:g} % of the quantity's largest in your gauge for a small one; "
          f"stresses in {unit}, strains as numbers")
    if rf_result is not None:
        print(f"reaction at the top grip ({rf_result['nodes']} nodes): yours {rf_result['yours']:.6g} {meta['force_unit']}, ours "
              f"{rf_result['ours']:.6g} {meta['force_unit']}, ours {100 * rf_result['difference']:+.3f} % from yours")
    for zone, table in tables.items():
        judged = "judged" if zone in meta["acceptance"] else "reported, not judged"
        print(f"\n{zone} ({table['elements']} elements; {meta['zones'][zone]}; {judged})")
        for q in QUANTITIES:
            t = table[q]
            print(f"  {q:15} {t['within_1']:6}/{t['values']} within 1 %, {t['within_3']:6} within 3 %; worst {100 * t['worst']:8.4f} % at our "
                  f"element {t['our_element']} (yours {t['your_element']}) ply {t['layer']}: yours {t['yours']:.6g}, ours {t['ours']:.6g}")
    print("\nVerdict")
    results = verdict(tables, rf_result, meta["acceptance"])
    for criterion, met, evidence in results:
        print(f"  {'met' if met else 'NOT MET' if met is False else 'not judged'}: {criterion} ({evidence})")
    if args.out:
        write_pairs(args.out, ours_rows, your_rows, pairs, differences)
        print(f"\nevery pair written to {args.out}")
    return 0 if all(met is not False for _, met, _ in results) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Refused as exc:
        sys.exit(f"refused: {exc}")
