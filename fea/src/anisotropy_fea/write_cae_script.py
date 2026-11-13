"""Write an FEModel as a script that Abaqus/CAE runs to build the same coupon as a native, editable model (ADR-0094, step 3).

The input deck (`write_abaqus`) gives Abaqus a mesh without geometry. This script gives it the model as an engineer would draw it:
the outline as a sketch, the partition lines, the material, the composite layup ply by ply on its own axes, the grips, the step, the
seeds and the structured mesh, the output requests and a job. Every number in it is a literal our code wrote from the same FEModel
the deck is written from (ADR-0001), in the deck's unit system; the script computes nothing but midpoints to pick faces and edges.

    File > Run Script in Abaqus/CAE                       the model and its job appear in the open session; nothing is saved
    abaqus cae noGUI=<script>.py -- save=<model>.cae      also saves the model there and writes the job's input file beside it

An Abaqus/CAE mesh seeded by number divides each edge evenly, which is how our structured mesh places its rows (`spec.row_coordinates`),
so the two meshes have their nodes at the same places. Abaqus numbers them its own way; the comparison pairs by position.

Scope (ADR-0089, anything else is refused with every reason, ADR-0003): the unnotched tension coupon, a flat rectangle with a structured
mesh of first-order shells and a composite layup, nodal or coupled grips on the tabs or the end rows, pulled by a displacement (or by a
force on a coupled grip). The probes' printed tables (`*Node Print`, `*El Print`) are left out: Abaqus/CAE has no object for them, and
what comes back is read from the ODB.

What the script does to the user's session is small on purpose: it adds one model and one job under the coupon's name and refuses to
run when either name is taken; it saves only when started with `save=`, and never over a file that exists. Inside Abaqus/CAE without its
window an error is written where nobody looks and the exit code is 0 (seen on Abaqus 2025), so the script says its own ending on the
terminal. It is written for Python 2.7 and 3 alike, the languages inside Abaqus before and after 2024.
"""

from __future__ import annotations

import re

import numpy as np

from . import __version__
from .femodel import FEModel
from .units import deck_units_of, from_si
from .write_abaqus import SECTION_POINTS, number

EVEN = 1e-9  # rows and columns count as evenly spaced within this fraction of the coupon's length
NAME = re.compile(r"[^A-Za-z0-9_-]+")
ELEMENTS = ("S4", "S4R")


class CaeScriptError(ValueError):
    """The model is outside what the build script draws; `problems` lists every reason."""

    def __init__(self, problems):
        self.problems = tuple(problems)
        super().__init__("; ".join(self.problems))


def cae_name(text: str, fallback: str) -> str:
    """A name Abaqus/CAE takes for a model and a job: letters, digits, hyphen and underscore, starting with a letter, 38 characters."""
    name = NAME.sub("-", text or "").strip("-_")
    if not name or not name[0].isalpha():
        name = f"{fallback}-{name}".rstrip("-")
    return name[:38].rstrip("-_")


def _even_counts(values: np.ndarray, lines: list[float], size: float, what: str, problems: list[str]) -> list[int]:
    """How many equal divisions lie between each pair of consecutive lines, or a problem when a stretch is not evenly divided."""
    counts = []
    for low, high in zip(lines, lines[1:]):
        inside = values[(values >= low - EVEN * size) & (values <= high + EVEN * size)]
        count = len(inside) - 1
        if count < 1 or np.max(np.abs(inside - np.linspace(low, high, count + 1))) > EVEN * size:
            problems.append(f"the {what} between {low:g} and {high:g} m are not evenly spaced, so seeding an edge by number cannot place them")
            counts.append(max(count, 1))
        else:
            counts.append(count)
    return counts


def cae_facts(model: FEModel, units: str | None = None) -> dict:
    """Everything the script states, as plain values in the deck's unit system. Raises `CaeScriptError` with every reason when the
    model is out of scope."""
    spec, mesh, material, section = model.spec, model.mesh, model.material, model.section
    units = units or deck_units_of(spec.units)
    length = lambda v: float(from_si(v, "length", units))  # noqa: E731
    stress = lambda v: float(from_si(v, "stress", units))  # noqa: E731
    force = lambda v: float(from_si(v, "force", units))  # noqa: E731
    problems: list[str] = []
    if spec.kind != "unnotched_tension":
        problems.append(f"the build script draws the unnotched tension coupon only, not {spec.kind} (ADR-0089)")
    if mesh.mesher != "structured" or mesh.order != 1:
        problems.append(f"it meshes a structured mesh of first-order shells, not {mesh.mesher} of order {mesh.order}")
    g = spec.geometry
    if getattr(g, "hole_diameter", None) or getattr(g, "dogbone", None) is not None:
        problems.append("it draws a plain rectangle: no hole and no dog-bone")
    if section.homogeneous or material.isotropic:
        problems.append("it writes a composite layup, not one isotropic material")
    element = spec.output.abaqus.element
    if element not in ELEMENTS:
        problems.append(f"it sets the element type S4 or S4R, not {element}")
    if model.pressures or model.pins or spec.grips is None:
        problems.append("it holds the coupon by its two grips only")
    if problems:
        raise CaeScriptError(problems)
    coupled = bool(model.couplings)
    if model.loads and not coupled:
        problems.append("a force on nodal grips is a set of nodal loads that Abaqus/CAE has no one object for: pull by a displacement, or couple the grips")

    # the node rows and columns, from the mesh itself: between the lines they must be evenly spaced, as a seed by number places them
    xs, ys = np.unique(np.round(mesh.xy[:, 0], 12)), np.unique(np.round(mesh.xy[:, 1], 12))
    if abs(xs[0]) > EVEN * g.length or abs(ys[0]) > EVEN * g.length or abs(xs[-1] - g.width) > EVEN * g.length or abs(ys[-1] - g.length) > EVEN * g.length:
        problems.append("the mesh does not span the rectangle from the origin to (width, length)")
    interior = set(spec.mesh.y_partitions or ())
    if g.tab_length:
        interior |= {g.tab_length, g.length - g.tab_length}
    lines = [0.0, *sorted(y for y in interior if EVEN * g.length < y < g.length * (1 - EVEN)), g.length]
    lines = [lines[0]] + [b for a, b in zip(lines, lines[1:]) if b - a > EVEN * g.length]  # a line stated twice is one line
    rows = _even_counts(ys, lines, g.length, "node rows", problems)
    columns = _even_counts(xs, [0.0, g.width], g.length, "node columns", problems)[0]
    if sum(rows) * columns != mesh.element_count:
        problems.append(f"the seeds give {sum(rows) * columns} elements and the mesh has {mesh.element_count}")
    bands = list(zip(lines, lines[1:]))

    # the regions by name: a stretch of the length as faces, or an end as its edge
    def stretch(low: float, high: float) -> list[tuple[float, float]]:
        return [(a, b) for a, b in bands if a >= low - EVEN * g.length and b <= high + EVEN * g.length]

    tab = g.tab_length or 0.0
    sets: dict[str, tuple[str, list]] = {}
    if tab:
        sets["Tab-Bottom"] = ("faces", stretch(0.0, tab))
        sets["Gauge"] = ("faces", stretch(tab, g.length - tab))
        sets["Tab-Top"] = ("faces", stretch(g.length - tab, g.length))
    if spec.grips.region == "tabs":
        if not tab:
            problems.append("the grips hold the tabs and the coupon states no tab length")
        sets["Grip-Bottom"] = ("faces", stretch(0.0, tab))
        sets["Grip-Top"] = ("faces", stretch(g.length - tab, g.length))
    else:
        sets["Grip-Bottom"] = ("edges", [0.0])
        sets["Grip-Top"] = ("edges", [g.length])
    for name, (kind, where) in sets.items():
        if not where:
            problems.append(f"no stretch of the coupon between its lines makes up {name}")

    held: dict[str, list] = {}
    for boundary in model.boundaries:
        values = held.setdefault(boundary.target, [None] * 6)
        for dof in range(boundary.dof_first, boundary.dof_last + 1):
            values[dof - 1] = length(boundary.value) if dof <= 3 else float(boundary.value)  # a rotation stays in radians
    known = set(sets) | {point.set_name for point in model.reference_points}
    for target in [*held, *(load.target for load in model.loads)]:
        if target not in known:
            problems.append(f"{target} is held or loaded and is not a grip or a reference point of this coupon")
    if problems:
        raise CaeScriptError(problems)

    designation = spec.coupon.designation if spec.coupon is not None else ""
    name = cae_name(designation, "Coupon")
    strengths = material.strengths
    half = length(g.width) / 2
    return {
        "units": units,
        "model": name, "job": name, "part": model.part, "instance": model.instance,
        "description": f"Built by anisotropy_fea {__version__} from {designation or 'a coupon'}, spec sha256 {spec.source_sha256[:16]}, units {units}",
        "title": spec.title,
        "width": length(g.width), "length": length(g.length),
        "lines": [length(y) for y in lines[1:-1]], "bands": [(length(a), length(b)) for a, b in bands], "rows": rows, "columns": columns,
        "element": element,
        "material": material.name,
        "elastic": [stress(material.E1), stress(material.E2), float(material.nu12), stress(material.G12), stress(material.G13), stress(material.G23)],
        # Abaqus's table: the four direct strengths with compression negative, the shear strength, the cross-product coefficient, the
        # stress limit; the last two are 0.0 when not stated, as Abaqus/CAE holds a deck's five-value line (seen on Abaqus 2025)
        "fail_stress": None if strengths is None else [stress(strengths.F1t), -stress(strengths.F1c), stress(strengths.F2t), -stress(strengths.F2c),
                                                      stress(strengths.F6), float(material.f12_star) if material.f12_star is not None else 0.0, 0.0],
        "layup": section.layup, "symmetric": bool(section.symmetric),
        "plies": [(ply.name, length(ply.thickness_m), float(ply.angle_deg)) for ply in section.listed],
        "integration_points": SECTION_POINTS,
        "section_points": [SECTION_POINTS * k + (SECTION_POINTS + 1) // 2 for k in range(len(section.plies))],
        "sets": [(set_name, kind, [(half, (length(a) + length(b)) / 2) for a, b in where] if kind == "faces" else [(half, length(y)) for y in where])
                 for set_name, (kind, where) in sets.items()],
        "points": [(point.set_name, (length(point.xy[0]), length(point.xy[1]))) for point in model.reference_points],
        "couplings": [(coupling.name, coupling.reference_set, coupling.node_set) for coupling in model.couplings],
        "boundaries": [(target, values) for target, values in held.items()],
        "loads": [(f"Pull-{k}", load.target, int(load.dof), force(load.value)) for k, load in enumerate(model.loads, start=1)],
    }


def _value(value) -> str:
    """A Python literal: a number as the deck writes it, text quoted, a list as a tuple."""
    if value is None or isinstance(value, bool):
        return repr(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return number(value)
    if isinstance(value, str):
        if not value.isascii() or "\\" in value or "'" in value or "\n" in value:
            raise CaeScriptError([f"{value!r} cannot be a name in an Abaqus/CAE script: plain ASCII without quotes or backslashes only"])
        return f"'{value}'"
    items = [_value(v) for v in value]
    return "(" + ", ".join(items) + ("," if len(items) == 1 else "") + ")"


def _ascii(text: str) -> str:
    return text.encode("ascii", "replace").decode("ascii").replace("\n", " ")


BODY = r'''

def say(text):
    """A line for the user: in the message area, and on the terminal when Abaqus/CAE runs without its window."""
    print(text)
    stream = getattr(sys, '__stdout__', None)
    if SAVE and stream is not None and stream is not sys.stdout:
        stream.write(text + '\n')
        stream.flush()


def unset(value):
    return UNSET if value is None else value


def build():
    if MODEL in mdb.models.keys():
        raise RuntimeError('a model named %s is already in this session: rename or delete it, then run the script again' % MODEL)
    if JOB in mdb.jobs.keys():
        raise RuntimeError('a job named %s is already in this session: rename or delete it, then run the script again' % JOB)
    middle = 0.5 * WIDTH
    model = mdb.Model(name=MODEL, description=DESCRIPTION)

    # the outline, drawn in the X-Y plane: x across the width, y along the length, the direction of the pull
    sketch = model.ConstrainedSketch(name='outline', sheetSize=2.0 * LENGTH)
    sketch.rectangle(point1=(0.0, 0.0), point2=(WIDTH, LENGTH))
    part = model.Part(name=PART, dimensionality=THREE_D, type=DEFORMABLE_BODY)
    part.BaseShell(sketch=sketch)
    del model.sketches['outline']

    # the lines across the width: the ends of the tabs and of the gauge length
    for y in LINES:
        plane = part.DatumPlaneByPrincipalPlane(principalPlane=XZPLANE, offset=y)
        part.PartitionFaceByDatumPlane(datumPlane=part.datums[plane.id], faces=part.faces.findAt(((middle, y, 0.0),)))

    material = model.Material(name=MATERIAL)
    material.Elastic(type=LAMINA, table=(ELASTIC,))
    if FAIL_STRESS is not None:
        material.elastic.FailStress(table=(FAIL_STRESS,))

    # the layup's axes: 1 along the length, 2 across it toward -x, 3 out of the plane, so a ply's angle is counted from the pull
    axes = part.DatumCsysByThreePoints(name='Ori-1', coordSysType=CARTESIAN, origin=(0.0, 0.0, 0.0), point1=(0.0, 1.0, 0.0),
                                       point2=(-1.0, 1.0, 0.0))
    layup = part.CompositeLayup(name=LAYUP, description='', elementType=SHELL, offsetType=MIDDLE_SURFACE, symmetric=SYMMETRIC,
                                thicknessAssignment=FROM_SECTION)
    layup.Section(preIntegrate=OFF, integrationRule=SIMPSON, thicknessType=UNIFORM, poissonDefinition=DEFAULT, temperature=GRADIENT,
                  useDensity=OFF)
    layup.ReferenceOrientation(orientationType=SYSTEM, localCsys=part.datums[axes.id], fieldName='',
                               additionalRotationType=ROTATION_NONE, angle=0.0, additionalRotationField='', axis=AXIS_3,
                               stackDirection=STACK_3)
    everywhere = regionToolset.Region(faces=part.faces)
    for name, thickness, angle in PLIES:  # bottom first
        layup.CompositePly(suppressed=False, plyName=name, region=everywhere, material=MATERIAL, thicknessType=SPECIFY_THICKNESS,
                           thickness=thickness, orientationType=SPECIFY_ORIENT, orientationValue=angle,
                           additionalRotationType=ROTATION_NONE, additionalRotationField='', axis=AXIS_3, angle=0.0,
                           numIntPoints=INTEGRATION_POINTS)

    # the mesh: every edge seeded by number, so each stretch is divided evenly, as our own mesh is
    across = part.edges.findAt(*[((middle, y, 0.0),) for y in (0.0,) + tuple(LINES) + (LENGTH,)])
    part.seedEdgeByNumber(edges=across, number=COLUMNS, constraint=FIXED)
    for (low, high), rows in zip(BANDS, ROWS):
        along = part.edges.findAt(((0.0, 0.5 * (low + high), 0.0),), ((WIDTH, 0.5 * (low + high), 0.0),))
        part.seedEdgeByNumber(edges=along, number=rows, constraint=FIXED)
    part.setMeshControls(regions=part.faces, elemShape=QUAD, technique=STRUCTURED)
    part.setElementType(regions=(part.faces,), elemTypes=(mesh.ElemType(elemCode=ELEMENT, elemLibrary=STANDARD),))
    part.generateMesh()

    assembly = model.rootAssembly
    assembly.DatumCsysByDefault(CARTESIAN)
    instance = assembly.Instance(name=INSTANCE, part=part, dependent=ON)
    for name, kind, places in SETS:
        found = getattr(instance, kind).findAt(*[((x, y, 0.0),) for x, y in places])
        if kind == 'faces':
            assembly.Set(name=name, faces=found)
        else:
            assembly.Set(name=name, edges=found)
    for name, (x, y) in POINTS:
        point = assembly.ReferencePoint(point=(x, y, 0.0))
        assembly.Set(name=name, referencePoints=(assembly.referencePoints[point.id],))
    for name, control, held in COUPLINGS:
        model.Coupling(name=name, controlPoint=assembly.sets[control], surface=assembly.sets[held], influenceRadius=WHOLE_SURFACE,
                       couplingType=KINEMATIC, localCsys=None, u1=ON, u2=ON, u3=ON, ur1=ON, ur2=ON, ur3=ON)

    model.StaticStep(name='Step-1', previous='Initial', nlgeom=OFF, timePeriod=1.0, initialInc=1.0, minInc=1e-05, maxInc=1.0)
    for target, (u1, u2, u3, ur1, ur2, ur3) in BOUNDARIES:
        model.DisplacementBC(name=target, createStepName='Step-1', region=assembly.sets[target], u1=unset(u1), u2=unset(u2),
                             u3=unset(u3), ur1=unset(ur1), ur2=unset(ur2), ur3=unset(ur3), amplitude=UNSET, fixed=OFF,
                             distributionType=UNIFORM, fieldName='', localCsys=None)
    for name, target, dof, value in LOADS:
        forces = {'cf1': UNSET, 'cf2': UNSET, 'cf3': UNSET}
        forces['cf%d' % dof] = value
        model.ConcentratedForce(name=name, createStepName='Step-1', region=assembly.sets[target], distributionType=UNIFORM,
                                field='', localCsys=None, **forces)

    # what is written to the ODB: Abaqus's own selection, and every ply at its middle section point, which is what is compared
    model.fieldOutputRequests['F-Output-1'].setValues(variables=PRESELECT)
    model.historyOutputRequests['H-Output-1'].setValues(variables=PRESELECT)
    model.FieldOutputRequest(name='F-Output-2', createStepName='Step-1', variables=('S', 'E', 'SF', 'SE'),
                             sectionPoints=SECTION_POINTS, directions=ON)

    mdb.Job(name=JOB, model=MODEL, description=DESCRIPTION)
    return part


SAVE = [argument.split('=', 1)[1] for argument in sys.argv if argument.lower().startswith('save=')]
try:
    if SAVE and os.path.exists(SAVE[0]):
        raise RuntimeError('%s is already there: this script does not save over a file' % SAVE[0])
    built = build()
    if SAVE:
        mdb.saveAs(pathName=SAVE[0])
        mdb.jobs[JOB].writeInput(consistencyChecking=OFF)
    say('built: model %s, %d nodes and %d %s elements, job %s, units %s%s' % (
        MODEL, len(built.nodes), len(built.elements), ELEMENT_NAME, JOB, UNITS,
        '; saved as %s, input file %s.inp' % (SAVE[0], JOB) if SAVE else '; nothing is saved until you save it'))
except Exception:
    if SAVE:
        say('not built:\n' + traceback.format_exc())
    raise
'''


def write_cae_script(model: FEModel, units: str | None = None) -> str:
    """The script text, the same for the same model, so its SHA-256 identifies it."""
    f = cae_facts(model, units)
    head = [
        "# -*- coding: utf-8 -*-",
        f"# {_ascii(f['description'])}; do not edit by hand.",
        f"# {_ascii(f['title'])}",
        "#",
        "# Builds this coupon in Abaqus/CAE as a native model: the outline, its partition lines, the material, the composite layup ply by",
        "# ply, the grips, the step, the mesh, the output requests and a job. Lengths, stresses and forces are in the units named below:",
        "# Abaqus carries none.",
        "#",
        "#   In Abaqus/CAE: File > Run Script. The model and its job appear in the session; nothing is saved until you save it.",
        "#   From a terminal: abaqus cae noGUI=<this file> -- save=<model>.cae   (also saves the model and writes the job's input file)",
        "#",
        "# The script adds one model and one job, and stops when either name is taken. It never saves over a file.",
        "from __future__ import print_function",
        "",
        "import os",
        "import sys",
        "import traceback",
        "",
        "from abaqus import *",
        "from abaqusConstants import *",
        "from caeModules import *",
        "import mesh",
        "import regionToolset",
        "",
    ]
    constants = [
        ("UNITS", f["units"]), ("MODEL", f["model"]), ("JOB", f["job"]), ("PART", f["part"]), ("INSTANCE", f["instance"]),
        ("DESCRIPTION", _ascii(f["description"])),
        ("WIDTH", f["width"]), ("LENGTH", f["length"]),
        ("LINES", f["lines"]),
        ("BANDS", f["bands"]),
        ("ROWS", f["rows"]),
        ("COLUMNS", f["columns"]),
        ("ELEMENT_NAME", f["element"]),
        ("MATERIAL", f["material"]),
        ("ELASTIC", f["elastic"]),
        ("FAIL_STRESS", f["fail_stress"]),
        ("LAYUP", f["layup"]), ("SYMMETRIC", f["symmetric"]),
        ("PLIES", f["plies"]),
        ("INTEGRATION_POINTS", f["integration_points"]),
        ("SECTION_POINTS", f["section_points"]),
        ("SETS", f["sets"]),
        ("POINTS", f["points"]),
        ("COUPLINGS", f["couplings"]),
        ("BOUNDARIES", f["boundaries"]),
        ("LOADS", f["loads"]),
    ]
    notes = {"LINES": "y of each line across the width", "BANDS": "the stretches of the length between the lines, bottom first",
             "ROWS": "elements along the length in each stretch", "COLUMNS": "elements across the width",
             "ELASTIC": "E1, E2, nu12, G12, G13, G23", "FAIL_STRESS": "Xt, Xc, Yt, Yc, S, cross-product coefficient, stress limit",
             "PLIES": "name, thickness, angle from the length axis; bottom first; the lower half when SYMMETRIC",
             "SECTION_POINTS": "the middle of every ply through the thickness", "SETS": "name, faces or edges, a point on each",
             "POINTS": "reference points: set name, (x, y)", "COUPLINGS": "name, the reference point's set, the set it carries",
             "BOUNDARIES": "set, (u1, u2, u3, ur1, ur2, ur3): None leaves a direction free", "LOADS": "name, set, direction, force"}
    lines = list(head)
    for name, value in constants:
        if name in notes:
            lines.append(f"# {notes[name]}")
        lines.append(f"{name} = {_value(value)}")
    lines.append(f"ELEMENT = {f['element']}  # Abaqus's own name for the element type")
    return "\n".join(lines) + BODY
