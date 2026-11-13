"""Every output Abaqus holds for a composite shell coupon, one row per element and layer, for the comparison with our kernel (ADR-0066
amendment 2, ADR-0089 part 7).

    abaqus python tools/abaqus_every_output.py <job>.odb --out <folder> [--step Step-1] [--frame -1] [--instance COUPON-1]

Runs under Abaqus's own Python, beside `abaqus_extract_fields.py`, whose plain helpers it shares (the section point's text, the step,
frame and instance choices, the centroid). Writes `<job>-every-output.csv`: for every element and every layer, at the layer's middle
section point (the deck must ask for it: `*Element Output` with the middle points listed first, as `tools/abaqus_detect.py` showed on
2026-11-11 that Abaqus 2025 accepts), the element label, the layer, the section point as the ODB spells it, the centroid, and Abaqus's
own numbers: S11, S22, S12 in the layer's material axes, then Mises, Tresca, the pressure and the maximum, middle and minimum principal
stresses as odbAccess gives them (what CAE shows), then E11, E22, E12. And `<job>-every-output-RF.csv`, the reaction at every node that
carries one, with its coordinates; and `<job>-every-output.json`, the provenance. Abaqus's numbers as they are, in the deck's units: no
conversion, no averaging (ADR-0002).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from abaqus_extract_fields import ExtractError, centroid, number, parse_section_point, pick_frame, pick_one, quoted  # noqa: E402

COLUMNS = ("Element", "Layer", "Section Point", "X", "Y", "S11", "S22", "S12", "Mises", "Tresca", "Pressure", "Max. Principal",
           "Mid. Principal", "Min. Principal", "E11", "E22", "E12")
RF_COLUMNS = ("Node", "X", "Y", "RF1", "RF2")
INVARIANTS = (("Mises", "mises"), ("Tresca", "tresca"), ("Pressure", "press"), ("Max. Principal", "maxPrincipal"),
              ("Mid. Principal", "midPrincipal"), ("Min. Principal", "minPrincipal"))


def middles_of(points: dict) -> dict[int, int]:
    """Section point number -> layer, for the point at the middle of each layer: an interior point (not SNEG or SPOS, the faces of the
    whole section that PRESELECT adds) whose fraction is nearest the layer's own middle, -1 + (2k - 1) / layers. A layer with no interior
    point is refused: the deck did not list it."""
    layers = max(point.layer for point in points.values())
    out = {}
    for layer in range(1, layers + 1):
        interior = [p for p in points.values() if p.layer == layer and not p.face]
        if not interior:
            raise ExtractError(f"layer {layer} has no interior section point in the field; list each layer's middle under *Element Output")
        mid = -1.0 + (2 * layer - 1) / layers
        out[min(interior, key=lambda p: (abs(p.fraction - mid), p.number)).number] = layer
    return out


def rows_of(points: dict, stress: dict, strain: dict, centroids: dict, components: tuple, strain_components: tuple) -> list[list[str]]:
    """The CSV rows: one per element and layer at the layer's middle point, sorted by element then layer. `stress[(element, point)]` is
    (components, invariants); `strain[(element, point)]` the strain components. Plain Python: tested without Abaqus."""
    wanted = middles_of(points)
    missing = [name for name in ("S11", "S22", "S12") if name not in components]
    if missing:
        raise ExtractError(f"the stress field has components {components}, not {missing}")
    out = []
    for (element, point_number) in sorted(stress):
        if point_number not in wanted:
            continue
        values, invariants = stress[(element, point_number)]
        e = strain.get((element, point_number))
        if e is None:
            raise ExtractError(f"element {element} has stress but no strain at section point {point_number}; the deck must ask for E with S")
        by_name = dict(zip(components, values))
        strains = dict(zip(strain_components, e))
        x, y, _ = centroids[element]
        out.append([str(element), str(wanted[point_number]), quoted(points[point_number].description), number(x), number(y)]
                   + [number(by_name[name]) for name in ("S11", "S22", "S12")]
                   + [number(invariants[name]) for name, _ in INVARIANTS]
                   + [number(strains[name]) for name in ("E11", "E22", "E12")])
    if not out:
        raise ExtractError("no values at the layers' middle section points: does the deck list them under *Element Output?")
    return out


def write_csv(path: Path, header: tuple, rows: list[list[str]]) -> str:
    text = ",".join(header) + "\n" + "".join(",".join(row) + "\n" for row in rows)
    with io.open(str(path), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read(path: Path, step_name, frame_index, instance_name) -> dict:
    from abaqusConstants import CENTROID  # Abaqus's own modules: only here
    from odbAccess import openOdb

    odb = openOdb(str(path), readOnly=True)
    try:
        step = odb.steps[pick_one("step", list(odb.steps.keys()), step_name)]
        descriptions = [str(f.description) for f in step.frames]
        index = pick_frame(descriptions, frame_index)
        frame = step.frames[index]
        instance = odb.rootAssembly.instances[pick_one("instance", list(odb.rootAssembly.instances.keys()), instance_name)]
        for name in ("S", "E"):
            if name not in frame.fieldOutputs.keys():
                raise ExtractError(f"frame {index} holds no {name}; its fields are {list(frame.fieldOutputs.keys())}")
        coordinates = {int(n.label): tuple(float(c) for c in n.coordinates) for n in instance.nodes}
        centroids = {int(e.label): centroid([coordinates[int(n)] for n in e.connectivity]) for e in instance.elements}
        points, stress, strain = {}, {}, {}
        s_field, e_field = frame.fieldOutputs["S"], frame.fieldOutputs["E"]
        for value in s_field.getSubset(region=instance, position=CENTROID).values:  # the element's centroid value, as CAE's Probe Values reads it
            if value.sectionPoint is None:
                raise ExtractError(f"element {value.elementLabel} has no section point: not a composite shell section")
            number_ = int(value.sectionPoint.number)
            points.setdefault(number_, parse_section_point(number_, str(value.sectionPoint.description)))
            stress[(int(value.elementLabel), number_)] = (tuple(float(v) for v in value.data),
                                                          {name: float(getattr(value, attribute)) for name, attribute in INVARIANTS})
        for value in e_field.getSubset(region=instance, position=CENTROID).values:
            if value.sectionPoint is not None:
                strain[(int(value.elementLabel), int(value.sectionPoint.number))] = tuple(float(v) for v in value.data)
        reactions = []
        if "RF" in frame.fieldOutputs.keys():
            rf_field = frame.fieldOutputs["RF"]
            for value in rf_field.getSubset(region=instance).values:
                rf = tuple(float(v) for v in value.data)
                if any(rf):
                    x, y, _ = coordinates[int(value.nodeLabel)]
                    reactions.append([str(int(value.nodeLabel)), number(x), number(y), number(rf[0]), number(rf[1])])
            # a coupled grip's reaction is on its reference point, a node of the assembly and of no instance (Abaqus 2025: with kinematic
            # couplings every reaction on the instance is zero). Its label is the assembly's own and may repeat an instance node's.
            assembly_nodes = {int(n.label): tuple(float(c) for c in n.coordinates) for n in odb.rootAssembly.nodes}
            for value in rf_field.values:
                if value.instance is None and int(value.nodeLabel) in assembly_nodes:
                    rf = tuple(float(v) for v in value.data)
                    if any(rf):
                        x, y, _ = assembly_nodes[int(value.nodeLabel)]
                        reactions.append([str(int(value.nodeLabel)), number(x), number(y), number(rf[0]), number(rf[1])])
        return {"odb": str(odb.name), "solver": str(odb.jobData.version), "created": str(odb.jobData.creationTime), "step": str(step.name),
                "frame_index": index, "frame": descriptions[index], "instance": str(instance.name), "points": points, "stress": stress,
                "strain": strain, "centroids": centroids, "components": tuple(str(c) for c in s_field.componentLabels),
                "strain_components": tuple(str(c) for c in e_field.componentLabels), "reactions": sorted(reactions, key=lambda r: int(r[0]))}
    finally:
        odb.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("odb", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--step", default=None)
    parser.add_argument("--frame", type=int, default=None)
    parser.add_argument("--instance", default=None)
    args = parser.parse_args(argv)
    if not args.odb.is_file():
        raise ExtractError(f"no ODB at {args.odb}")
    data = read(args.odb.resolve(), args.step, args.frame, args.instance)
    rows = rows_of(data["points"], data["stress"], data["strain"], data["centroids"], data["components"], data["strain_components"])
    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.odb.stem
    files = {"every_output": {"path": f"{stem}-every-output.csv", "rows": len(rows),
                              "sha256": write_csv(args.out / f"{stem}-every-output.csv", COLUMNS, rows)}}
    if data["reactions"]:
        files["reactions"] = {"path": f"{stem}-every-output-RF.csv", "rows": len(data["reactions"]),
                              "sha256": write_csv(args.out / f"{stem}-every-output-RF.csv", RF_COLUMNS, data["reactions"])}
    provenance = {key: data[key] for key in ("odb", "solver", "created", "step", "frame_index", "frame", "instance")}
    provenance["files"] = files
    with io.open(str(args.out / f"{stem}-every-output.json"), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(provenance, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"{data['solver']}: {len(rows)} element-layer rows, {len(data['reactions'])} reaction nodes, written to {args.out}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ExtractError as exc:
        sys.exit(f"refused: {exc}")
