"""Every output of an Abaqus run of our deck beside our kernel's, element by element and ply by ply, judged by zone (ADR-0066 amendment 2,
ADR-0089 part 7, round (a)).

    uv run python tools/abaqus_compare.py <spec.toml> <job>-every-output.csv [--deck <the deck Abaqus ran>] [--rf <job>-every-output-RF.csv]
        [--json <file>]

The CSV is what `abaqus python tools/abaqus_extract_fields.py`'s sibling `tools/abaqus_every_output.py` writes from the run's ODB: per
element and layer, at the layer's middle section point, Abaqus's S11, S22, S12 in the layer's material axes, its Mises, Tresca, pressure
and principal stresses, and E11, E22, E12. Our side is the kernel on the same deck (`--deck`, default the spec's committed Abaqus deck,
which Abaqus ran with the extra output request alone), at the same element, the same ply, in the same units. The coupon's zones come from
its spec: the gauge (the extensometer's length at mid-length), the free length beyond one coupon width from a tab line, the band within
that width, the elements on a tab line (the clamped edge: reported, not judged, ADR-0066), and the gripped elements. A value agrees when
it is within the tolerance of Abaqus's, or of the floor times that quantity's largest magnitude in the gauge for a small one. Prints one
line per zone and quantity: how many agree within 1 % and within 3 %, the worst difference and where.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.every_output import FLOOR, QUANTITIES, ZONES, zones_of
from anisotropy_fea.every_output import ours_by_element as ours_of_solution
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.spec import load_spec
from anisotropy_fea.units import deck_units_of, from_si

# the quantities, the zones and our values per element are `anisotropy_fea.every_output`'s, which the package's file for the team is
# written from too (ADR-0089 amendment 3): this tool and the team's `compare_every_output.py` judge the same numbers
__all__ = ("FLOOR", "QUANTITIES", "ZONES", "zones_of", "ours_by_element", "read_abaqus", "compare", "reaction")


def ours_by_element(deck, units: str) -> tuple[dict[int, dict[str, np.ndarray]], object]:
    """Our kernel's values per element label on the deck: each quantity as an array over the plies, in the deck's units."""
    solution = solve_deck(deck)
    return ours_of_solution(solution, units), solution


def read_abaqus(path: Path) -> dict[tuple[int, int], dict[str, float]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {(int(row["Element"]), int(row["Layer"])): {q: float(row[q]) for q in QUANTITIES} for row in csv.DictReader(handle)}


def compare(abaqus: dict, ours: dict, zones: dict[int, str]) -> dict:
    """Per zone and quantity: the count, how many within 1 % and 3 %, the worst relative difference and where."""
    out: dict = {}
    # a small value is judged against the floor times the quantity's largest magnitude in the gauge, the state the coupon is validated in:
    # a zone's own largest would make the gripped zone's zeros, or a tab line's peaks, the yardstick
    gauge = [k for k in abaqus if zones.get(k[0]) == "gauge"] or list(abaqus)
    scales = {q: float(np.max(np.abs([abaqus[k][q] for k in gauge]))) for q in QUANTITIES}
    for zone in ZONES:
        keys = [k for k in abaqus if zones.get(k[0]) == zone]
        if not keys:
            continue
        out[zone] = {"elements": len({k[0] for k in keys})}
        for q in QUANTITIES:
            a = np.array([abaqus[k][q] for k in keys])
            o = np.array([ours[k[0]][q][k[1] - 1] for k in keys])
            scale = scales[q]
            denominator = np.maximum(np.abs(a), FLOOR * scale) if scale > 0 else np.ones_like(a)
            relative = np.abs(o - a) / denominator
            worst = int(np.argmax(relative)) if relative.size else 0
            out[zone][q] = {"values": int(a.size), "within_1": int(np.sum(relative <= 0.01)), "within_3": int(np.sum(relative <= 0.03)),
                            "worst": float(relative[worst]) if relative.size else 0.0, "worst_at": {"element": keys[worst][0], "ply": keys[worst][1],
                            "abaqus": float(a[worst]), "ours": float(o[worst])}, "largest": scale}
    return out


def reaction(rf_path: Path, spec, units: str, solution) -> dict | None:
    """The pull's reaction: Abaqus's RF2 summed over the top grip's nodes, beside our kernel's over the same nodes."""
    if rf_path is None or not rf_path.is_file():
        return None
    length = lambda v: from_si(v, "length", units)  # noqa: E731
    top = length(spec.geometry.length) - length(spec.geometry.tab_length or 0.0)
    with rf_path.open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if float(row["Y"]) >= top - 1e-6]
    abaqus_total = sum(float(row["RF2"]) for row in rows)
    labels = {int(row["Node"]) for row in rows}
    index = {int(key[1]): i for i, key in enumerate(solution.mesh.node_keys)}
    ours_total = float(from_si(sum(solution.reaction[index[n], 1] for n in labels if n in index), "force", units))
    return {"nodes": len(rows), "abaqus": abaqus_total, "ours": ours_total, "relative": (ours_total - abaqus_total) / abs(abaqus_total)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", type=Path)
    parser.add_argument("csv", type=Path, help="<job>-every-output.csv from tools/abaqus_every_output.py")
    parser.add_argument("--deck", type=Path, default=None, help="the deck Abaqus ran; default the spec's committed Abaqus deck")
    parser.add_argument("--rf", type=Path, default=None, help="<job>-every-output-RF.csv; default beside the CSV")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    spec = load_spec(args.spec)
    units = deck_units_of(spec.units)
    deck_path = args.deck or paths.deck_path(args.spec, "abaqus")
    deck = read_deck(deck_path, units)
    ours, solution = ours_by_element(deck, units)
    zones = zones_of(spec, solution.mesh, units)
    abaqus = read_abaqus(args.csv)
    result = {"deck": str(deck_path), "csv": str(args.csv), "units": units, "floor": FLOOR, "zones": compare(abaqus, ours, zones)}
    rf = args.rf or args.csv.with_name(args.csv.name.replace("-every-output.csv", "-every-output-RF.csv"))
    result["reaction"] = reaction(rf, spec, units, solution)
    if result["reaction"]:
        r = result["reaction"]
        print(f"reaction at the top grip ({r['nodes']} nodes): Abaqus {r['abaqus']:.6g}, ours {r['ours']:.6g}, {100 * r['relative']:+.3f} %")
    for zone, table in result["zones"].items():
        print(f"{zone} ({table['elements']} elements)")
        for q in QUANTITIES:
            t = table[q]
            w = t["worst_at"]
            print(f"  {q:15} {t['within_1']:5}/{t['values']} within 1 %, {t['within_3']:5} within 3 %; worst {100 * t['worst']:7.3f} % at element "
                  f"{w['element']} ply {w['ply']} (Abaqus {w['abaqus']:.6g}, ours {w['ours']:.6g})")
    if args.json:
        args.json.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
