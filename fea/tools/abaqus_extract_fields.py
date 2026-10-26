"""Export field output from an Abaqus ODB as the CSV field reports Abaqus/CAE writes (Report > Field Output), without the GUI (ADR-0045).

    abaqus python tools/abaqus_extract_fields.py <job>.odb --out <folder> [--step Step-1] [--frame 1] [--instance CFRP-COUPON-1]
        [--quantities S11 S22 S12 Mises] [--layer-point bottom|middle|top]

Runs under Abaqus's own Python (`abaqus python`, 3.10 in Abaqus 2025), so it imports nothing from our package, and `odbAccess`
only inside `read_odb`; everything else is plain Python that `tests/test_abaqus_extract.py` runs under pytest. Writes one file
per quantity, `<job>-<quantity>.csv`, in the layout `anisotropy_fea.abaqus_report.read_field_report` reads (the header and the
section point text of a CAE report, rows sorted by element label then section point, no padding, LF line endings), the
reaction force at every node that carries one as `<job>-RF.csv`, and the provenance as `<job>-extract.json` (solver, creation
time, step, frame, instance, each file's SHA-256). The ODB path is made absolute before opening, because the first column holds
it: the same ODB gives the same bytes and digests however the script is called. Values are the ODB's own numbers in the deck's units: no conversion, no
averaging, no transformation (ADR-0002). What is not stated is refused rather than guessed (ADR-0003): the step and the
instance are taken only when the ODB holds one, the frame only when the step has one after the initial frame; a layer with
several section points in the field needs --layer-point; an integration point other than 1 (a full-integration shell) is
refused with the advice to use S4R or centroid output.

The strings were read from a real ODB on 2026-10-24 (Abaqus/Standard 2025, our X840PW-UNT-L1 deck): the frame description is
padded (`Increment      1: Step Time =    1.000`), a section point reads `SNEG, (fraction = -1.0), Layer = 1` at a face of the
section and `fraction = -0.900000, Layer = 1` inside, and the section category reads `shell < composite > < elset = NAME >`;
CAE prints the category, a colon and the point as the Section Point column, and the elset as the Section Name column.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

QUANTITIES = ("S11", "S22", "S12", "Mises")
LAYER_POINTS = ("bottom", "middle", "top")
HEADER = ("ODB Name", "Step", "Frame", "Part Instance Name", "Element Label", "IntPt", "X", "Y", "Z", "Section Name", "Material Name", "Section Point")
RF_HEADER = ("ODB Name", "Step", "Frame", "Part Instance Name", "Node Label", "X", "Y", "Z", "RF1", "RF2", "RF3")
SECTION_POINT = re.compile(r"^(?:(SNEG|SPOS|SMID)\s*,\s*)?\(?\s*fraction\s*=\s*([-+0-9.eE]+)\s*\)?\s*,\s*Layer\s*=\s*(\d+)\s*$")
CATEGORY_ELSET = re.compile(r"<\s*elset\s*=\s*(.*?)\s*>")


class ExtractError(ValueError):
    """The ODB does not hold what was asked for, or the request leaves a choice the script will not make."""


@dataclass(frozen=True)
class SectionPoint:
    number: int
    description: str  # as the ODB spells it
    face: str  # SNEG, SPOS, SMID or "" inside the section
    fraction: float  # -1 at the bottom face of the section, +1 at the top
    layer: int  # from 1 at the bottom


@dataclass
class OdbData:
    """What the ODB holds, as plain Python: the odbAccess objects never leave `read_odb`."""

    odb: str
    solver: str
    created: str
    step: str
    frame: str
    frame_index: int
    instance: str
    element_type: str
    component_labels: tuple[str, ...]
    centroids: dict[int, tuple[float, float, float]] = field(default_factory=dict)  # element label -> centroid
    sections: dict[int, str] = field(default_factory=dict)  # element label -> the elset CAE prints as Section Name
    categories: dict[int, str] = field(default_factory=dict)  # element label -> section category name
    materials: dict[int, list[str]] = field(default_factory=dict)  # element label -> layer materials, bottom first
    points: dict[int, SectionPoint] = field(default_factory=dict)  # section point number -> point, those present in the field
    values: dict[tuple[int, int], tuple[dict[str, float], float]] = field(default_factory=dict)  # (element, point) -> (components, Mises)
    reactions: list[tuple[str, int, tuple[float, float, float], tuple[float, float, float]]] = field(default_factory=list)  # (instance, node, xyz, RF)


# --- plain helpers, tested without Abaqus --------------------------------------------------------


def parse_section_point(number: int, description: str) -> SectionPoint:
    match = SECTION_POINT.match(description.strip())
    if match is None:
        raise ExtractError(f"section point {number}: {description!r} is not 'FACE, (fraction = f), Layer = n' or 'fraction = f, Layer = n'")
    return SectionPoint(number=number, description=description.strip(), face=match.group(1) or "", fraction=float(match.group(2)), layer=int(match.group(3)))


def category_elset(category: str) -> str:
    """The elset a section category names, `shell < composite > < elset = NAME >` giving NAME; "" when it names none."""
    match = CATEGORY_ELSET.search(category)
    return match.group(1) if match else ""


def choose_layer_points(points: dict[int, SectionPoint], rule: str | None) -> dict[int, SectionPoint]:
    """One section point per layer. A layer with one point in the field gets it; a layer with several needs the rule: bottom
    (its lowest fraction), top (its highest) or middle (the point nearest the layer's mid-fraction, which must be an interior
    point). Without a rule, several points in a layer are refused with the counts."""
    if rule is not None and rule not in LAYER_POINTS:
        raise ExtractError(f"--layer-point must be one of {LAYER_POINTS}, not {rule!r}")
    by_layer: dict[int, list[SectionPoint]] = {}
    for point in points.values():
        by_layer.setdefault(point.layer, []).append(point)
    chosen: dict[int, SectionPoint] = {}
    for layer, candidates in sorted(by_layer.items()):
        candidates = sorted(candidates, key=lambda p: (p.fraction, p.number))
        if len(candidates) == 1:
            chosen[layer] = candidates[0]
            continue
        if rule is None:
            counts = ", ".join(f"layer {k}: {len(v)}" for k, v in sorted(by_layer.items()) if len(v) > 1)
            raise ExtractError(f"several section points per layer in the field ({counts}); say which with --layer-point bottom, middle or top")
        if rule == "bottom":
            chosen[layer] = candidates[0]
        elif rule == "top":
            chosen[layer] = candidates[-1]
        else:
            interior = candidates[1:-1]
            if not interior:
                raise ExtractError(f"layer {layer} has {len(candidates)} section points, none inside it; --layer-point middle needs an interior point")
            mid = 0.5 * (candidates[0].fraction + candidates[-1].fraction)
            chosen[layer] = min(interior, key=lambda p: (abs(p.fraction - mid), p.number))
    return chosen


def centroid(coordinates: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    if not coordinates:
        raise ExtractError("an element with no nodes")
    n = float(len(coordinates))
    return (sum(c[0] for c in coordinates) / n, sum(c[1] for c in coordinates) / n, sum(c[2] for c in coordinates) / n)


def number(value: float) -> str:
    """Nine significant digits, no padding: the same number every run, and what float() reads back."""
    return "%.9g" % float(value)


def quoted(value: str) -> str:
    if '"' in value or "\n" in value or "\r" in value:
        raise ExtractError(f"cannot write {value!r} in a CSV cell: it holds a quote or a line break")
    return '"' + value + '"'


def section_point_text(category: str, point: SectionPoint) -> str:
    """The Section Point column as CAE prints it: the category, a colon, the point."""
    return f"{category} : {point.description}"


def layer_material(materials: list[str], layer: int) -> str:
    """The material of a layer counted from 1 at the bottom; "" when the section lists fewer layers (noted by the caller)."""
    return materials[layer - 1] if 1 <= layer <= len(materials) else ""


def build_reports(data: OdbData, quantities: tuple[str, ...], rule: str | None) -> tuple[dict[str, list[list[str]]], dict[int, SectionPoint], list[str]]:
    """The rows of every requested quantity, the section point chosen per layer, and notes worth printing."""
    for quantity in quantities:
        if quantity not in QUANTITIES:
            raise ExtractError(f"quantity {quantity!r} is not one of {QUANTITIES}")
        if quantity != "Mises" and quantity not in data.component_labels:
            raise ExtractError(f"the stress field has components {data.component_labels}, not {quantity}")
    chosen = choose_layer_points(data.points, rule)
    keep = {point.number for point in chosen.values()}
    notes: list[str] = []
    rows: dict[str, list[list[str]]] = {quantity: [] for quantity in quantities}
    missing_material: set[int] = set()
    for (element, point_number) in sorted(data.values):
        if point_number not in keep:
            continue
        point = data.points[point_number]
        components, mises = data.values[(element, point_number)]
        x, y, z = data.centroids[element]
        material = layer_material(data.materials.get(element, []), point.layer)
        if not material:
            missing_material.add(point.layer)
        head = [data.odb, data.step, data.frame, quoted(data.instance), str(element), "1", number(x), number(y), number(z),
                quoted(data.sections.get(element, "")), quoted(material), quoted(section_point_text(data.categories.get(element, ""), point))]
        for quantity in quantities:
            value = mises if quantity == "Mises" else components[quantity]
            rows[quantity].append(head + [number(value)])
    if missing_material:
        notes.append(f"Material Name left empty for layers {sorted(missing_material)}: the section lists fewer layers (a layup the ODB does not mirror)")
    if any(not r for r in rows.values()):
        raise ExtractError("no values at the chosen section points")
    return rows, chosen, notes


def reaction_rows(data: OdbData) -> list[list[str]]:
    rows = []
    for instance, label, xyz, rf in sorted(data.reactions, key=lambda r: (r[0], r[1])):
        rows.append([data.odb, data.step, data.frame, quoted(instance), str(label), number(xyz[0]), number(xyz[1]), number(xyz[2]),
                     number(rf[0]), number(rf[1]), number(rf[2])])
    return rows


def write_csv(path: Path, header: tuple[str, ...], rows: list[list[str]]) -> str:
    """Write the file with LF line endings and return its SHA-256."""
    text = "\n".join([",".join(header)] + [",".join(row) for row in rows]) + "\n"
    with io.open(str(path), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pick_one(kind: str, names: list[str], wanted: str | None) -> str:
    """The named item, or the only one; several without a name are refused with the list."""
    if wanted is not None:
        if wanted not in names:
            raise ExtractError(f"{kind} {wanted!r} is not in the ODB; it has {names}")
        return wanted
    if len(names) != 1:
        raise ExtractError(f"the ODB holds {len(names)} {kind}s {names}; name one with --{kind}")
    return names[0]


def pick_frame(descriptions: list[str], wanted: int | None) -> int:
    """The frame index asked for (negative counts from the end), or the one frame after the initial frame 0."""
    if wanted is not None:
        if not -len(descriptions) <= wanted < len(descriptions):
            raise ExtractError(f"frame {wanted} is not in the step; it has {len(descriptions)} frames: {descriptions}")
        return wanted % len(descriptions)
    if len(descriptions) == 2:
        return 1
    raise ExtractError(f"the step has {len(descriptions)} frames {descriptions}; say which with --frame (frame 0 is the initial state)")


# --- the ODB ------------------------------------------------------------------------------------------


def _labels(region) -> list[int]:
    """Element labels of an OdbSet region: a flat array for an instance set, one array per instance for an assembly set."""
    labels = []
    for item in region.elements:
        if hasattr(item, "label"):
            labels.append(int(item.label))
        else:
            labels.extend(int(e.label) for e in item)
    return labels


def read_odb(path: Path, step_name: str | None, frame_index: int | None, instance_name: str | None) -> OdbData:
    from odbAccess import openOdb  # Abaqus's own module: only here

    odb = openOdb(str(path), readOnly=True)
    try:
        step = odb.steps[pick_one("step", list(odb.steps.keys()), step_name)]
        descriptions = [str(f.description) for f in step.frames]
        index = pick_frame(descriptions, frame_index)
        frame = step.frames[index]
        instance = odb.rootAssembly.instances[pick_one("instance", list(odb.rootAssembly.instances.keys()), instance_name)]
        if "S" not in frame.fieldOutputs.keys():
            raise ExtractError(f"frame {index} holds no stress field S; its fields are {list(frame.fieldOutputs.keys())}")
        stress = frame.fieldOutputs["S"]
        types = sorted({str(e.type) for e in instance.elements})
        data = OdbData(odb=str(odb.name), solver=str(odb.jobData.version), created=str(odb.jobData.creationTime), step=str(step.name),
                       frame=descriptions[index], frame_index=index, instance=str(instance.name), element_type="/".join(types),
                       component_labels=tuple(str(c) for c in stress.componentLabels))
        coordinates = {int(n.label): (float(n.coordinates[0]), float(n.coordinates[1]), float(n.coordinates[2])) for n in instance.nodes}
        for element in instance.elements:
            label = int(element.label)
            data.centroids[label] = centroid([coordinates[int(n)] for n in element.connectivity])
            data.categories[label] = str(element.sectionCategory.name)
            data.sections[label] = category_elset(data.categories[label])
        for assignment in instance.sectionAssignments:
            section = odb.sections[assignment.sectionName]
            layup = [str(layer.material) for layer in section.layup] if hasattr(section, "layup") else []
            if layup and str(getattr(section, "symmetric", "OFF")) == "ON":
                layup = layup + layup[::-1]
            for label in _labels(assignment.region):
                data.materials[label] = layup
        points_seen = set()
        for value in stress.getSubset(region=instance).values:
            label = int(value.elementLabel)
            if int(value.integrationPoint) != 1:
                raise ExtractError(f"element {label} reports stress at integration point {value.integrationPoint}: a full-integration shell; "
                                   "use S4R (one point at the centroid) or request centroid output")
            if value.sectionPoint is None:
                raise ExtractError(f"element {label} has no section point: not a composite shell section")
            point_number = int(value.sectionPoint.number)
            if point_number not in points_seen:
                data.points[point_number] = parse_section_point(point_number, str(value.sectionPoint.description))
                points_seen.add(point_number)
            components = {name: float(v) for name, v in zip(data.component_labels, value.data)}
            data.values[(label, point_number)] = (components, float(value.mises))
        if "RF" in frame.fieldOutputs.keys():
            assembly_nodes = {int(n.label): (float(n.coordinates[0]), float(n.coordinates[1]), float(n.coordinates[2])) for n in odb.rootAssembly.nodes}
            instance_nodes = {}
            for value in frame.fieldOutputs["RF"].values:
                rf = tuple(float(v) for v in value.data) + (0.0,) * (3 - len(value.data))
                if not any(rf):
                    continue
                label = int(value.nodeLabel)
                if value.instance is None:
                    data.reactions.append(("", label, assembly_nodes[label], rf[:3]))
                else:
                    name = str(value.instance.name)
                    if name not in instance_nodes:
                        instance_nodes[name] = {int(n.label): (float(n.coordinates[0]), float(n.coordinates[1]), float(n.coordinates[2]))
                                               for n in odb.rootAssembly.instances[name].nodes}
                    data.reactions.append((name, label, instance_nodes[name][label], rf[:3]))
    finally:
        odb.close()
    if not data.values:
        raise ExtractError(f"the stress field holds no value on instance {data.instance}")
    return data


# --- the command ----------------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("odb", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--step", default=None, help="step name; needed when the ODB holds several")
    parser.add_argument("--frame", type=int, default=None, help="frame index in the step, -1 the last; needed when the step has more than one after frame 0")
    parser.add_argument("--instance", default=None, help="part instance name as the ODB spells it; needed when there are several")
    parser.add_argument("--quantities", nargs="+", default=list(QUANTITIES), help=f"any of {QUANTITIES}; one file each")
    parser.add_argument("--layer-point", choices=LAYER_POINTS, default=None, help="which section point of a layer to write when the field holds several")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.odb.is_file():
        raise ExtractError(f"no ODB at {args.odb}")
    args.odb = args.odb.resolve()  # the ODB Name column holds this path: absolute, so the files and their digests do not depend on how the script was called
    data = read_odb(args.odb, args.step, args.frame, args.instance)
    rows, chosen, notes = build_reports(data, tuple(args.quantities), args.layer_point)
    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.odb.stem
    print(f"odb {data.odb} | {data.solver} | created {data.created}")
    print(f"step {data.step} | frame {data.frame_index} {data.frame!r} | instance {data.instance} | {data.element_type}, {len(data.centroids)} elements")
    print("section points per layer: " + ", ".join(f"layer {layer}: {point.description}" for layer, point in sorted(chosen.items())))
    files = {}
    for quantity in args.quantities:
        path = args.out / f"{stem}-{quantity}.csv"
        digest = write_csv(path, HEADER + (f"S-{quantity}",), rows[quantity])
        files[quantity] = {"path": path.name, "rows": len(rows[quantity]), "sha256": digest}
        print(f"written {path}: {len(rows[quantity])} rows, sha256 {digest}")
    if data.reactions:
        path = args.out / f"{stem}-RF.csv"
        reactions = reaction_rows(data)
        digest = write_csv(path, RF_HEADER, reactions)
        files["RF"] = {"path": path.name, "rows": len(reactions), "sha256": digest}
        print(f"written {path}: {len(reactions)} nodes with a reaction, sha256 {digest}")
    for note in notes:
        print("note:", note)
    provenance = {"odb": data.odb, "solver": data.solver, "created": data.created, "step": data.step, "frame_index": data.frame_index, "frame": data.frame,
                  "instance": data.instance, "element_type": data.element_type, "elements": len(data.centroids),
                  "section_points": {str(layer): point.description for layer, point in sorted(chosen.items())}, "files": files, "notes": notes}
    with io.open(str(args.out / f"{stem}-extract.json"), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(provenance, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"written {args.out / (stem + '-extract.json')}")
    return 0


if __name__ == "__main__":
    import sys

    try:
        sys.exit(main())
    except ExtractError as exc:
        sys.exit(f"refused: {exc}")
