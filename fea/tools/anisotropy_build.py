"""Build a coupon in Abaqus/CAE from data (ADR-0094 amendment 4). The site answers a run's coupon as one JSON file, the numbers
and names of the model and nothing else, and this file is the code that draws it. It is part of the connector, handed over and
checked with it, so what runs in the user's Abaqus is what was installed and never something the site sent.

    check(data)    reads the data as hostile: every field has a stated type, size and range, a field it does not know is refused,
                   and every reason is given at once. What comes back holds numbers, names from a short alphabet, and nothing else.
    build(data)    asks Abaqus/CAE for the model: the outline, its partition lines, the material, the composite layup ply by ply, the
                   grips, the step, the seeds and the mesh, the output requests and a job. It adds one model and one job, refuses
                   when either name is taken, and saves nothing.
    parse(bytes)   the site's answer, JSON of at most 2 MB, checked; read(path) is the same for a file on the disk.

The data is used as values only: a number is a dimension or a count, a name is a name Abaqus keeps, the element type is one of two
looked up by name. Nothing in it is evaluated, imported, formatted into code or put on a command line.

The calls are the ones the downloaded build script makes (`anisotropy_fea.write_cae_script`, which a user runs by hand with File >
Run Script), in the same order with the same values: `fea/tests/test_anisotropy_build.py` runs both against a stand-in for Abaqus and
sets the two lists of calls side by side.

The standard library only; Abaqus's own modules are imported inside `build`, so the rest is plain Python that runs beside Abaqus,
in the helper, before Abaqus is started. Python 3, so Abaqus 2024 or later.
"""

from __future__ import annotations

import io
import json
import math
import re
from pathlib import Path

FORMAT = "anisotropy-coupon/1"
MAX_BYTES = 2 * 1024 * 1024
UNITS = ("mm-MPa", "m-Pa")
ELEMENTS = ("S4", "S4R")
KINDS = ("faces", "edges")
COUPON = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")  # the coupon's name on the site, which names its folder on this PC
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,37}")  # a model and a job, as Abaqus/CAE takes them
LABEL = re.compile(r"[A-Za-z0-9\[(][A-Za-z0-9 ._+/,()\[\]-]{0,79}")  # any other name: no quote, backslash, or anything outside plain ASCII
TEXT = re.compile(r"[ -~]{1,300}")
BUILT = re.compile(r"Built by anisotropy_fea \S+ from (\S+), spec sha256 [0-9a-f]+, units (\S+)")  # the description, as the menu reads it back
MOST = {"lines": 200, "plies": 1000, "sets": 50, "places": 200, "points": 10, "couplings": 10, "boundaries": 20, "loads": 20,
        "elements": 2000000, "side": 20000, "integration_points": 99}
FIELDS = ("format", "coupon", "units", "model", "job", "part", "instance", "description", "width", "length", "lines", "bands", "rows",
          "columns", "element", "material", "elastic", "fail_stress", "layup", "symmetric", "plies", "integration_points",
          "section_points", "sets", "points", "couplings", "boundaries", "loads")


class NotACoupon(ValueError):
    """The data is not a coupon this file builds; `problems` lists every reason."""

    def __init__(self, problems):
        self.problems = tuple(problems)
        super().__init__("; ".join(self.problems))


# ------------------------------------------------------------------------------------------------------- reading the data as hostile

def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and abs(value) < 1e30 and math.isfinite(value)  # the size first: a huge whole number is no float


def _count(value, most: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= most


def _text(value, shape) -> bool:
    return isinstance(value, str) and shape.fullmatch(value) is not None


def _list(value, most: int, least: int = 0) -> bool:
    return isinstance(value, (list, tuple)) and least <= len(value) <= most  # a tuple too: what `check` gives back is itself a coupon


def _numbers(value, count: int) -> bool:
    return _list(value, count, count) and all(_number(v) for v in value)


def check(data) -> dict:
    """The coupon as this file builds it: the same fields, numbers as floats, counts as integers, lists as tuples. Raises
    `NotACoupon` with every reason. Nothing is built here, and Abaqus is not needed."""
    if not isinstance(data, dict):
        raise NotACoupon(["the file is not a coupon of Anisotropy's: it is not one JSON object"])
    if data.get("format") != FORMAT:
        raise NotACoupon([f"the file does not say it is {FORMAT}, the one format this connector builds: a newer site needs a newer connector"])
    problems = [f"it has no {name}" for name in FIELDS if name not in data]
    problems += [f"it has a field this connector does not know, {str(name)[:40]!r}" for name in data if name not in FIELDS]
    if problems:
        raise NotACoupon(problems)
    d = data
    bad = problems.append

    if not _text(d["coupon"], COUPON):
        bad("coupon is not a plain name")
    if d["units"] not in UNITS:
        bad(f"units is not one of {' or '.join(UNITS)}")
    for name in ("model", "job"):
        if not _text(d[name], NAME):
            bad(f"{name} is not a name Abaqus/CAE takes for a model and a job: a letter, then letters, digits, - and _, 38 at most")
    for name in ("part", "instance", "material", "layup"):
        if not _text(d[name], LABEL):
            bad(f"{name} is not a plain name")
    found = BUILT.fullmatch(d["description"]) if _text(d["description"], TEXT) else None
    if found is None:
        bad("description is not the line Anisotropy writes on a model it builds")
    elif found.group(2) != d["units"]:
        bad(f"description says the units {found.group(2)} and units says {d['units']}")

    sizes = _number(d["width"]) and _number(d["length"]) and d["width"] > 0 and d["length"] > 0
    if not sizes:
        bad("width and length are not two positive numbers")
    if not (_list(d["lines"], MOST["lines"]) and all(_number(y) for y in d["lines"])):
        bad(f"lines is not a list of at most {MOST['lines']} numbers")
    elif sizes:
        edges = [0.0, *[float(y) for y in d["lines"]], float(d["length"])]
        if any(b <= a for a, b in zip(edges, edges[1:])):
            bad("lines are not in rising order between 0 and the length")
        elif not (_list(d["bands"], len(edges) - 1, len(edges) - 1) and all(_numbers(band, 2) for band in d["bands"])
                  and [[float(a), float(b)] for a, b in d["bands"]] == [[a, b] for a, b in zip(edges, edges[1:])]):
            bad("bands are not the stretches between the lines, bottom first")
        elif not (_list(d["rows"], len(edges) - 1, len(edges) - 1) and all(_count(n, MOST["side"]) for n in d["rows"])):
            bad("rows is not one count of elements for each band")
    if not _count(d["columns"], MOST["side"]):
        bad("columns is not a count of elements")
    elif _list(d["rows"], MOST["lines"] + 1) and all(_count(n, MOST["side"]) for n in d["rows"]) and sum(d["rows"]) * d["columns"] > MOST["elements"]:
        bad(f"the mesh has more than {MOST['elements']} elements")
    if d["element"] not in ELEMENTS:
        bad(f"element is not one of {' or '.join(ELEMENTS)}")
    if not _numbers(d["elastic"], 6):
        bad("elastic is not six numbers: E1, E2, nu12, G12, G13, G23")
    if d["fail_stress"] is not None and not _numbers(d["fail_stress"], 7):
        bad("fail_stress is neither seven numbers nor null")
    if not isinstance(d["symmetric"], bool):
        bad("symmetric is not true or false")
    plies = _list(d["plies"], MOST["plies"], 1) and all(
        _list(ply, 3, 3) and _text(ply[0], LABEL) and _number(ply[1]) and ply[1] > 0 and _number(ply[2]) and abs(ply[2]) <= 360 for ply in d["plies"])
    if not plies:
        bad(f"plies is not a list of 1 to {MOST['plies']} plies, each a name, a positive thickness and an angle")
    elif len({ply[0] for ply in d["plies"]}) != len(d["plies"]):
        bad("two plies have one name")
    if not _count(d["integration_points"], MOST["integration_points"]):
        bad("integration_points is not a count")
    if not (_list(d["section_points"], 2 * MOST["plies"], 1) and all(_count(n, 2 * MOST["plies"] * MOST["integration_points"]) for n in d["section_points"])):
        bad("section_points is not a list of section point numbers")

    def places(value) -> bool:
        return _list(value, MOST["places"], 1) and all(_numbers(place, 2) for place in value)

    sets = _list(d["sets"], MOST["sets"], 1) and all(
        _list(s, 3, 3) and _text(s[0], LABEL) and s[1] in KINDS and places(s[2]) for s in d["sets"])
    if not sets:
        bad("sets is not a list of sets, each a name, faces or edges, and a point on each")
    points = _list(d["points"], MOST["points"]) and all(_list(p, 2, 2) and _text(p[0], LABEL) and _numbers(p[1], 2) for p in d["points"])
    if not points:
        bad("points is not a list of reference points, each a name and (x, y)")
    known = ({s[0] for s in d["sets"]} if sets else set()) | ({p[0] for p in d["points"]} if points else set())
    if sets and points and len(known) != len(d["sets"]) + len(d["points"]):
        bad("two sets or reference points have one name")
    couplings = _list(d["couplings"], MOST["couplings"]) and all(
        _list(c, 3, 3) and all(_text(name, LABEL) for name in c) for c in d["couplings"])
    if not couplings:
        bad("couplings is not a list of couplings, each a name, a reference point's set and the set it carries")
    elif sets and points:
        for name, control, held in d["couplings"]:
            if control not in {p[0] for p in d["points"]} or held not in {s[0] for s in d["sets"]}:
                bad(f"the coupling {name} does not join a reference point of this coupon to a set of it")
    boundaries = _list(d["boundaries"], MOST["boundaries"]) and all(
        _list(b, 2, 2) and _text(b[0], LABEL) and _list(b[1], 6, 6) and all(v is None or _number(v) for v in b[1]) for b in d["boundaries"])
    if not boundaries:
        bad("boundaries is not a list of a set and six values, each a number or null")
    loads = _list(d["loads"], MOST["loads"]) and all(
        _list(load, 4, 4) and _text(load[0], LABEL) and _text(load[1], LABEL) and _count(load[2], 3) and _number(load[3]) for load in d["loads"])
    if not loads:
        bad("loads is not a list of loads, each a name, a set, a direction 1 to 3 and a force")
    if sets and points and boundaries and loads:
        for target in [b[0] for b in d["boundaries"]] + [load[1] for load in d["loads"]]:
            if target not in known:
                bad(f"{target} is held or loaded and is not a set or a reference point of this coupon")
        if len({b[0] for b in d["boundaries"]}) != len(d["boundaries"]) or len({load[0] for load in d["loads"]}) != len(d["loads"]):
            bad("two boundary conditions or two loads have one name")
    if problems:
        raise NotACoupon(problems)

    pair = lambda p: (float(p[0]), float(p[1]))  # noqa: E731
    return {
        "format": FORMAT, "coupon": d["coupon"], "units": d["units"], "model": d["model"], "job": d["job"], "part": d["part"],
        "instance": d["instance"], "description": d["description"], "width": float(d["width"]), "length": float(d["length"]),
        "lines": tuple(float(y) for y in d["lines"]), "bands": tuple(pair(band) for band in d["bands"]), "rows": tuple(d["rows"]),
        "columns": d["columns"], "element": d["element"], "material": d["material"], "elastic": tuple(float(v) for v in d["elastic"]),
        "fail_stress": None if d["fail_stress"] is None else tuple(float(v) for v in d["fail_stress"]),
        "layup": d["layup"], "symmetric": d["symmetric"],
        "plies": tuple((name, float(thickness), float(angle)) for name, thickness, angle in d["plies"]),
        "integration_points": d["integration_points"], "section_points": tuple(d["section_points"]),
        "sets": tuple((name, kind, tuple(pair(place) for place in where)) for name, kind, where in d["sets"]),
        "points": tuple((name, pair(place)) for name, place in d["points"]),
        "couplings": tuple((name, control, held) for name, control, held in d["couplings"]),
        "boundaries": tuple((target, tuple(None if v is None else float(v) for v in values)) for target, values in d["boundaries"]),
        "loads": tuple((name, target, dof, float(value)) for name, target, dof, value in d["loads"]),
    }


def parse(body: bytes) -> dict:
    """A coupon from the bytes the site answered or a file holds: JSON of at most 2 MB, checked."""
    if len(body) > MAX_BYTES:
        raise NotACoupon(["it is larger than any coupon, so it was not read"])
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, RecursionError):
        raise NotACoupon(["it is not JSON, so it is not a coupon of Anisotropy's"]) from None
    return check(data)


def read(path: Path) -> dict:
    """A coupon file from the disk, checked."""
    try:
        with io.open(str(path), "rb") as handle:
            body = handle.read(MAX_BYTES + 1)
    except OSError:
        raise NotACoupon([f"no file at {path}"]) from None
    return parse(body)


# ------------------------------------------------------------------------------------------------------- asking Abaqus/CAE for the model

def build(data: dict) -> dict:
    """Add the coupon to the open session of Abaqus/CAE as one model and one job; nothing is saved. `data` is checked again here, so
    nothing unchecked reaches Abaqus whoever calls. Returns {"model", "job", "nodes", "elements", "element", "units"}. Raises
    `NotACoupon`, `RuntimeError` when a name is taken, or Abaqus's own error."""
    d = check(data)
    import abaqusConstants as c
    import caeModules  # noqa: F401  Abaqus/CAE's modules, which give the model its parts, its assembly and its steps
    import mesh
    import regionToolset
    from abaqus import mdb

    def unset(value):
        return c.UNSET if value is None else value

    model_name, job_name, material_name = d["model"], d["job"], d["material"]
    width, length = d["width"], d["length"]
    if model_name in mdb.models.keys():
        raise RuntimeError("a model named %s is already in this session: rename or delete it, then open the coupon again" % model_name)
    if job_name in mdb.jobs.keys():
        raise RuntimeError("a job named %s is already in this session: rename or delete it, then open the coupon again" % job_name)
    middle = 0.5 * width
    model = mdb.Model(name=model_name, description=d["description"])

    # the outline, drawn in the X-Y plane: x across the width, y along the length, the direction of the pull
    sketch = model.ConstrainedSketch(name="outline", sheetSize=2.0 * length)
    sketch.rectangle(point1=(0.0, 0.0), point2=(width, length))
    part = model.Part(name=d["part"], dimensionality=c.THREE_D, type=c.DEFORMABLE_BODY)
    part.BaseShell(sketch=sketch)
    del model.sketches["outline"]

    # the lines across the width: the ends of the tabs and of the gauge length
    for y in d["lines"]:
        plane = part.DatumPlaneByPrincipalPlane(principalPlane=c.XZPLANE, offset=y)
        part.PartitionFaceByDatumPlane(datumPlane=part.datums[plane.id], faces=part.faces.findAt(((middle, y, 0.0),)))

    material = model.Material(name=material_name)
    material.Elastic(type=c.LAMINA, table=(d["elastic"],))
    if d["fail_stress"] is not None:
        material.elastic.FailStress(table=(d["fail_stress"],))

    # the layup's axes: 1 along the length, 2 across it toward -x, 3 out of the plane, so a ply's angle is counted from the pull
    axes = part.DatumCsysByThreePoints(name="Ori-1", coordSysType=c.CARTESIAN, origin=(0.0, 0.0, 0.0), point1=(0.0, 1.0, 0.0),
                                       point2=(-1.0, 1.0, 0.0))
    layup = part.CompositeLayup(name=d["layup"], description="", elementType=c.SHELL, offsetType=c.MIDDLE_SURFACE,
                                symmetric=d["symmetric"], thicknessAssignment=c.FROM_SECTION)
    layup.Section(preIntegrate=c.OFF, integrationRule=c.SIMPSON, thicknessType=c.UNIFORM, poissonDefinition=c.DEFAULT,
                  temperature=c.GRADIENT, useDensity=c.OFF)
    layup.ReferenceOrientation(orientationType=c.SYSTEM, localCsys=part.datums[axes.id], fieldName="",
                               additionalRotationType=c.ROTATION_NONE, angle=0.0, additionalRotationField="", axis=c.AXIS_3,
                               stackDirection=c.STACK_3)
    everywhere = regionToolset.Region(faces=part.faces)
    for name, thickness, angle in d["plies"]:  # bottom first
        layup.CompositePly(suppressed=False, plyName=name, region=everywhere, material=material_name, thicknessType=c.SPECIFY_THICKNESS,
                           thickness=thickness, orientationType=c.SPECIFY_ORIENT, orientationValue=angle,
                           additionalRotationType=c.ROTATION_NONE, additionalRotationField="", axis=c.AXIS_3, angle=0.0,
                           numIntPoints=d["integration_points"])

    # the mesh: every edge seeded by number, so each stretch is divided evenly, as Anisotropy's own mesh is
    across = part.edges.findAt(*[((middle, y, 0.0),) for y in (0.0,) + d["lines"] + (length,)])
    part.seedEdgeByNumber(edges=across, number=d["columns"], constraint=c.FIXED)
    for (low, high), rows in zip(d["bands"], d["rows"]):
        along = part.edges.findAt(((0.0, 0.5 * (low + high), 0.0),), ((width, 0.5 * (low + high), 0.0),))
        part.seedEdgeByNumber(edges=along, number=rows, constraint=c.FIXED)
    part.setMeshControls(regions=part.faces, elemShape=c.QUAD, technique=c.STRUCTURED)
    element = {"S4": c.S4, "S4R": c.S4R}[d["element"]]  # one of the two the check lets through, by Abaqus's own name
    part.setElementType(regions=(part.faces,), elemTypes=(mesh.ElemType(elemCode=element, elemLibrary=c.STANDARD),))
    part.generateMesh()

    assembly = model.rootAssembly
    assembly.DatumCsysByDefault(c.CARTESIAN)
    instance = assembly.Instance(name=d["instance"], part=part, dependent=c.ON)
    for name, kind, where in d["sets"]:
        found = (instance.faces if kind == "faces" else instance.edges).findAt(*[((x, y, 0.0),) for x, y in where])
        if kind == "faces":
            assembly.Set(name=name, faces=found)
        else:
            assembly.Set(name=name, edges=found)
    for name, (x, y) in d["points"]:
        point = assembly.ReferencePoint(point=(x, y, 0.0))
        assembly.Set(name=name, referencePoints=(assembly.referencePoints[point.id],))
    for name, control, held in d["couplings"]:
        model.Coupling(name=name, controlPoint=assembly.sets[control], surface=assembly.sets[held], influenceRadius=c.WHOLE_SURFACE,
                       couplingType=c.KINEMATIC, localCsys=None, u1=c.ON, u2=c.ON, u3=c.ON, ur1=c.ON, ur2=c.ON, ur3=c.ON)

    model.StaticStep(name="Step-1", previous="Initial", nlgeom=c.OFF, timePeriod=1.0, initialInc=1.0, minInc=1e-05, maxInc=1.0)
    for target, (u1, u2, u3, ur1, ur2, ur3) in d["boundaries"]:
        model.DisplacementBC(name=target, createStepName="Step-1", region=assembly.sets[target], u1=unset(u1), u2=unset(u2),
                             u3=unset(u3), ur1=unset(ur1), ur2=unset(ur2), ur3=unset(ur3), amplitude=c.UNSET, fixed=c.OFF,
                             distributionType=c.UNIFORM, fieldName="", localCsys=None)
    for name, target, dof, value in d["loads"]:
        forces = {"cf1": c.UNSET, "cf2": c.UNSET, "cf3": c.UNSET}
        forces["cf%d" % dof] = value
        model.ConcentratedForce(name=name, createStepName="Step-1", region=assembly.sets[target], distributionType=c.UNIFORM,
                                field="", localCsys=None, **forces)

    # what is written to the ODB: Abaqus's own selection, and every ply at its middle section point, which is what is compared
    model.fieldOutputRequests["F-Output-1"].setValues(variables=c.PRESELECT)
    model.historyOutputRequests["H-Output-1"].setValues(variables=c.PRESELECT)
    model.FieldOutputRequest(name="F-Output-2", createStepName="Step-1", variables=("S", "E", "SF", "SE"),
                             sectionPoints=d["section_points"], directions=c.ON)

    mdb.Job(name=job_name, model=model_name, description=d["description"])
    return {"model": model_name, "job": job_name, "nodes": len(part.nodes), "elements": len(part.elements), "element": d["element"],
            "units": d["units"]}
