#!/usr/bin/env python3
"""Builds the example wing the home page's product demo shows (ADR-0098) and records its analysis.

    python3 scripts/demo-wing.py            # the geometry and the mesh only; a recorded analysis of the same wing is kept
    python3 scripts/demo-wing.py --solve    # and the analysis (needs CalculiX's `ccx` on the path, and `uv` for the engine)

The wing is an example made for the demo, not a design of ours or of anyone's: a tapered, swept half wing with one aerofoil
along its span, two skins over two spar webs and nine ribs, each rib the aerofoil's shape but for its two tips, with the spars
running through it. Its only borrowed number is the span, 7 ft, which a public news story gives for the wings of a student
design class (UC San Diego Today, "Structural Engineering Students Design, Build and Test Unmanned Aerial Vehicle Wings"); the
chords and the sweep are round numbers chosen for the picture, and the aerofoil is the public NACA 2412 formula, scaled by the
local chord and laid off vertically from it. The leading and the trailing edge are straight, the spars lie at fixed shares of
the local chord, and the ribs stand in planes of constant y.

What it writes, in lib/demo-wing.json: the parts, the mesh the page draws (corner nodes and four-node faces, the very mesh that
is solved) and, with --solve, one value an element and the displacement of every stored node from the solver's answer. Lengths
are mm, forces N, stresses MPa, as in the fea package's coupon files.

The analysis (--solve) is one linear static step of CalculiX on the stored faces, written as the fea package writes a laminate
(fea/src/anisotropy_fea/write_calculix.py): every face an eight-node composite shell (S8R) with a node added in the middle of
each edge, one shared by the faces on that edge; the ply as *ELASTIC, TYPE=ENGINEERING CONSTANTS; one *ORIENTATION for each ply
angle. CalculiX's orientation is a fixed frame in space, not one that follows a shell, so a part has one section, with its own
orientations, for each direction its faces look in, all with the part's one layup. The lines of one chord share all meet in one
point beyond the tip, so the strip of skin between two of them is flat, and so is each spar web: a fixed frame is exact for a
strip but for the rounding of the stored corners, which turns a face at most SAME_WAY (0.03 degrees) from its section's axes
(the solve prints the largest turn). The root's nodes are held in all six freedoms and LOAD is shared between the points where
the spars meet the upper skin at the ribs outboard of the root. It is an example load, not a flight load.

A part's ply angles turn counterclockwise about its faces' normal, seen from the side the normal points to, from the axis
ANGLES_FROM names laid on the face (its projection onto the face), and its plies are listed from the face behind the normal to
the face it points out of (ADR-0004). So 0 degrees in a skin runs straight out along the span, within 1 degree of y in plan aft
of the first 6 % of the chord and up to 8 degrees from it on the steep faces of the nose, and crosses the swept spars at about
9 and 7 degrees; 0 degrees in a spar web runs along the spar. The skins' normals point out of the wing, so each skin's layup
reads as the skin is seen from outside the wing, its first ply the innermost: a +45 degree ply runs outboard and towards the
nose in the upper skin, outboard and towards the tail in the lower. The spars' normals point aft, so their +45 runs outboard
and up; the ribs' point to the root (-y), so theirs runs aft and up.

The value kept for a face is the strength used: the largest maximum-stress index over its plies and their integration points,
each ply's stress in its own axes against the library's strengths (0 unloaded, 1 the first ply fails). The reaction kept is the
vertical force the span cell beside the root carries to it, summed from the solver's stresses: the total CalculiX prints for
the root's nodes is not the whole reaction once their rotations are held (printed with the checks, and not used).

What the step does not see: buckling, the bonds between the parts, damage after the first ply fails, or large deflections. The
same deck with *BUCKLE in place of *STATIC puts the upper skin's first buckling, between the spars in the bay beside the root,
at 1099 N (CalculiX 2.21, 2026-11-14, on this mesh, which was not refined for it; run by hand and not recorded). LOAD is the
largest of 250, 500, 750 and 1000 N that is no more than 0.6 of that.
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "lib" / "demo-wing.json"

SPAN = 2133.6  # mm: 7 ft, the one number taken from the public story
ROOT_CHORD, TIP_CHORD = 450.0, 225.0  # mm: the chord narrows evenly from the root to the tip
SWEEP = 400.0  # mm: how far aft of the root's leading edge the tip's lies; both edges are straight
SWEEP_MEASURES = "how far aft of the root's leading edge the tip's leading edge lies, along x"
AEROFOIL = "NACA 2412"
CAMBER, CAMBER_AT, THICKNESS = 0.02, 0.4, 0.12
# Stations along the chord, as shares of the local chord: closer at the nose, with one on each spar.
CHORD_STATIONS = [0.0, 0.0125, 0.03, 0.06, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.72, 0.79, 0.86, 0.93, 1.0]
SPARS = {"front-spar": 0.25, "rear-spar": 0.65}  # as shares of the local chord: straight lines in plan
SPAN_CELLS = 40  # 53.34 mm (2.1 in) each
RIB_EVERY = 5  # a rib every fifth station, in a plane of constant y: nine ribs, the root's and the tip's among them
DEPTH_CELLS = 2  # cells through the depth of a spar web or a rib

# The parts, in the order the page lists them. Angles are counted from the span (y), laid on the face, for the skins and the
# spars, and from the chord (x) for the ribs; the layups are examples in the library's IM7 / 8552 tape.
PARTS = [
    {"id": "upper-skin", "name": "Upper skin", "layup": "[45/0/-45/90]s", "angles": [45, 0, -45, 90, 90, -45, 0, 45]},
    {"id": "lower-skin", "name": "Lower skin", "layup": "[45/0/-45/90]s", "angles": [45, 0, -45, 90, 90, -45, 0, 45]},
    {"id": "front-spar", "name": "Front spar", "layup": "[45/-45/0]s", "angles": [45, -45, 0, 0, -45, 45]},
    {"id": "rear-spar", "name": "Rear spar", "layup": "[45/-45/0]s", "angles": [45, -45, 0, 0, -45, 45]},
    {"id": "ribs", "name": "Ribs", "layup": "[45/-45]s", "angles": [45, -45, -45, 45]},
]
LIBRARY = "im7-8552"

# The analysis.
SPANWISE, CHORDWISE = (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)
ANGLES_FROM = {"upper-skin": SPANWISE, "lower-skin": SPANWISE, "front-spar": SPANWISE, "rear-spar": SPANWISE, "ribs": CHORDWISE}
LOAD = 500  # N upward in all: an example of a test that loads a wing at its ribs, not a flight load. A linear static step cannot
# see buckling, so the load is the largest of 250, 500, 750 and 1000 N that is no more than 0.6 of the upper skin's first buckling
# load: one linear buckling step on this mesh gave the factor 1.0985 under 1000 N, so 1099 N and 0.6 of it 659 N. The mesh was
# not refined for buckling, so the factor is not a checked number.
COUPON = ROOT / "tests" / "fixtures" / "studio-standards" / "values.json"  # the public coupon example of the same material: its G13 and G23
MATERIAL = "IM7-8552-Lamina"
REFERENCE_TEMPERATURE = 293.0  # K, as the fea package's decks state it; CalculiX needs a value on the constants' second line
FLAT = 1e-3  # a face's corners may leave its plane by this share of its size: the corners are stored rounded
SAME_WAY = math.radians(0.03)  # faces whose normals are this close share a section and its ply axes
POINTS_A_PLY = 8  # an S8R composite shell's integration points in one ply, numbered from the first ply up (fea/checks/calculix-conventions.toml)
MODES = ("fibre tension", "fibre compression", "transverse tension", "transverse compression", "shear")
RECORDED = ("load", "field", "displacement", "solve")  # what --solve adds to the record; kept together or not at all


def surface(share: float) -> tuple[float, float]:
    """The aerofoil's upper and lower height at a share of the chord, as shares of the chord: NACA's four-digit camber line and
    thickness, the closed trailing edge, laid off vertically."""
    x = share
    half = 5 * THICKNESS * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4)
    if x < CAMBER_AT:
        camber = CAMBER / CAMBER_AT**2 * (2 * CAMBER_AT * x - x**2)
    else:
        camber = CAMBER / (1 - CAMBER_AT) ** 2 * ((1 - 2 * CAMBER_AT) + 2 * CAMBER_AT * x - x**2)
    return camber + half, camber - half


def plan(wing: dict, y: float) -> tuple[float, float]:
    """Where the leading edge lies along x and how long the chord is, y out from the root, for a record's `wing` block."""
    out = y / wing["span"]
    return wing["sweep"] * out, wing["root_chord"] + (wing["tip_chord"] - wing["root_chord"]) * out


def build() -> dict:
    """The mesh: nodes as [x along the chord from the root's leading edge, y along the span, z up] in mm, four-node faces, and
    each face's part. Every station along the span is a plane of constant y holding the aerofoil at the local chord, so the lines
    of one chord share are straight and every face of the skins and the webs is flat but for the rounding of its corners."""
    wing = {"span": SPAN, "root_chord": ROOT_CHORD, "tip_chord": TIP_CHORD, "sweep": SWEEP}
    nodes: list[list[float]] = []
    index: dict[tuple[int, int, int], int] = {}
    last_chord = len(CHORD_STATIONS) - 1

    def node(i: int, j: int, k: int) -> int:
        """The node at chord station i, span station j and depth level k (0 the lower skin, DEPTH_CELLS the upper)."""
        if i in (0, last_chord):
            k = 0  # the two skins meet on the leading and the trailing edge
        key = (i, j, k)
        if key not in index:
            y = SPAN * j / SPAN_CELLS
            nose, chord = plan(wing, y)
            upper, lower = surface(CHORD_STATIONS[i])
            z = (lower + (upper - lower) * k / DEPTH_CELLS) * chord
            index[key] = len(nodes)
            nodes.append([round(nose + CHORD_STATIONS[i] * chord, 2), round(y, 2), round(z, 3)])
        return index[key]

    quads: list[list[int]] = []
    part: list[int] = []
    where = {entry["id"]: number for number, entry in enumerate(PARTS)}

    def face(name: str, corners: list[int]) -> None:
        quads.append(corners)
        part.append(where[name])

    # The skins: every face is listed so that its normal points out of the wing.
    for j in range(SPAN_CELLS):
        for i in range(last_chord):
            face("upper-skin", [node(i, j, DEPTH_CELLS), node(i + 1, j, DEPTH_CELLS), node(i + 1, j + 1, DEPTH_CELLS), node(i, j + 1, DEPTH_CELLS)])
    for j in range(SPAN_CELLS):
        for i in range(last_chord):
            face("lower-skin", [node(i, j, 0), node(i, j + 1, 0), node(i + 1, j + 1, 0), node(i + 1, j, 0)])
    # The spar webs, from the lower skin to the upper.
    for name, share in SPARS.items():
        i = CHORD_STATIONS.index(share)
        for j in range(SPAN_CELLS):
            for k in range(DEPTH_CELLS):
                face(name, [node(i, j, k), node(i, j + 1, k), node(i, j + 1, k + 1), node(i, j, k + 1)])
    # The ribs: whole aerofoils through the spars, from the first chord station behind the leading edge to the last before the
    # trailing edge, where the skins are still apart.
    rib_stations = list(range(0, SPAN_CELLS + 1, RIB_EVERY))
    for j in rib_stations:
        for i in range(1, last_chord - 1):
            for k in range(DEPTH_CELLS):
                face("ribs", [node(i, j, k), node(i + 1, j, k), node(i + 1, j, k + 1), node(i, j, k + 1)])

    parts = []
    for number, entry in enumerate(PARTS):
        members = [element for element, owner in enumerate(part) if owner == number]
        parts.append({**entry, "first": members[0], "count": len(members)})
        assert members == list(range(members[0], members[0] + len(members))), "a part's faces are stored together"
    upper_max = max(surface(share)[0] for share in CHORD_STATIONS)
    lower_min = min(surface(share)[1] for share in CHORD_STATIONS)
    return {
        "what": "An example wing made for the demo: a tapered, swept half wing, two skins over two spar webs and nine ribs",
        "units": {"length": "mm", "force": "N", "stress": "MPa"},
        "wing": {
            "span": SPAN,
            "root_chord": ROOT_CHORD,
            "tip_chord": TIP_CHORD,
            "chord": ROOT_CHORD,  # the root's again, under its old name, until the page's checker reads root_chord
            "sweep": SWEEP,
            "sweep_measures": SWEEP_MEASURES,
            "depth": round((upper_max - lower_min) * ROOT_CHORD, 2),  # the largest, at the root
            "aerofoil": AEROFOIL,
            "spars": list(SPARS.values()),
            "ribs": [round(SPAN * j / SPAN_CELLS, 2) for j in rib_stations],
            "library": LIBRARY,
        },
        "parts": parts,
        "mesh": {"nodes": nodes, "quads": quads, "part": part},
    }


# --- the analysis ---------------------------------------------------------------------------------

Vector = tuple[float, float, float]


def dot(a: Vector, b: Vector) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vector, b: Vector) -> Vector:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def number(value: float) -> str:
    """A number as the fea package's decks write it."""
    text = f"{value:.10g}"
    return text if ("." in text or "e" in text) else text + "."


def load_of(record: dict) -> dict:
    """The load as the record states it."""
    ribs = len(record["wing"]["ribs"]) - 1
    return {"total": LOAD, "unit": "N", "how": f"Pushed up at the {len(SPARS) * ribs} points where the {len(SPARS)} spars meet the upper skin at the {ribs} ribs "
                                               "outboard of the root, in equal shares; the root is held."}


def lamina() -> dict:
    """The ply's numbers in mm, N and MPa, each with where it comes from. E1, E2, G12, nu12, the five strengths and the ply
    thickness are the library's primary dataset for LIBRARY, read by the engine's own reader (anisotropy_engine.library, the one
    place a library value is converted, ADR-0002). That dataset has no out-of-plane shear stiffness, so G13 and G23 are the ones
    the public coupon example states for the same material (COUPON), as the fea package takes them for a coupon. E3 = E2 and
    nu13 = nu23 = 0 are the fea package's stated choices for a CalculiX deck (spec.Transverse: transverse isotropy, plane stress)."""
    code = (f"import json; from anisotropy_engine.library import library_material; m = library_material({LIBRARY!r}); "
            "print(json.dumps({'dataset': m.dataset_id, 'citation': m.citation, 'thickness': m.ply_thickness_m, "
            "'values': {v.role: v.value for v in m.values}, 'keys': {v.role: v.key for v in m.values}}))")
    try:
        done = subprocess.run(["uv", "run", "-q", "python", "-c", code], cwd=ROOT / "engine", capture_output=True, text=True, check=True)
    except FileNotFoundError:
        raise SystemExit("--solve reads the material library through the engine and needs `uv` on the path") from None
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"the engine could not read {LIBRARY} from its library:\n{error.stderr}") from None
    library = json.loads(done.stdout)
    values = library["values"]
    missing = [role for role in ("E1", "E2", "G12", "nu12", "F1t", "F1c", "F2t", "F2c", "F6", "tply") if role not in values]
    if missing:
        raise SystemExit(f"the library's {LIBRARY} ({library['dataset']}) does not state {', '.join(missing)}")
    coupon = json.loads(COUPON.read_text(encoding="utf-8"))
    if coupon.get("library") != LIBRARY:
        raise SystemExit(f"{COUPON.relative_to(ROOT)} is a coupon of {coupon.get('library')}, not of {LIBRARY}: it cannot lend its G13 and G23")
    ply = {role: values[role] / 1e6 for role in ("E1", "E2", "G12", "F1t", "F1c", "F2t", "F2c", "F6")}  # Pa to MPa
    ply.update(nu12=values["nu12"], thickness=library["thickness"] * 1e3, G13=float(coupon["G13"]), G23=float(coupon["G23"]), E3=ply["E2"], nu13=0.0, nu23=0.0)
    ply["sources"] = [f"library {LIBRARY} / {library['dataset']}: " + ", ".join(f"{role} from {key}" for role, key in library["keys"].items()),
                      f"  {library['citation']}", f"{COUPON.relative_to(ROOT)}: G13, G23", "the fea package's choices for a CalculiX deck: E3 = E2, nu13 = nu23 = 0"]
    return ply


def shell_model(record: dict) -> dict:
    """The stored faces as the model that is solved: a node in the middle of every edge, one shared by the faces on that edge (the
    corners keep their numbers); the faces by section, one for each direction a part's faces look in, with the axes of each of its
    ply angles (1 along the fibres: the part's axis, laid on the face, turned by the angle about the normal; 2 across them, in the
    face); the root's nodes; and the loaded ones, where the upper skin, a spar and a rib outboard of the root meet. A face joins
    the first section of its part whose normal is within SAME_WAY of its own: the corners are stored rounded, so the faces of one
    flat strip look in directions a little apart, and `off_axes` is the most any face is turned from its section's axes."""
    mesh, parts = record["mesh"], record["parts"]
    nodes: list[Vector] = [tuple(node) for node in mesh["nodes"]]
    middle: dict[tuple[int, int], int] = {}
    elements: list[list[int]] = []
    for corners in mesh["quads"]:
        mids = []
        for a, b in zip(corners, corners[1:] + corners[:1]):
            edge = (min(a, b), max(a, b))
            if edge not in middle:
                middle[edge] = len(nodes)
                nodes.append(tuple((nodes[a][i] + nodes[b][i]) / 2 for i in range(3)))
            mids.append(middle[edge])
        elements.append(corners + mids)

    sections: list[dict] = []
    section_of: list[int] = []
    areas: list[float] = []
    off_axes = warp = 0.0
    for element, corners in enumerate(mesh["quads"]):
        p = [nodes[n] for n in corners]
        normal = cross(tuple(p[2][i] - p[0][i] for i in range(3)), tuple(p[3][i] - p[1][i] for i in range(3)))
        size = math.sqrt(dot(normal, normal))
        normal = tuple(value / size for value in normal)
        areas.append(size / 2)  # a flat four-sided face: half the cross product of its diagonals
        bend = abs(dot(normal, tuple(p[1][i] - p[0][i] for i in range(3)))) / math.sqrt(size / 2)  # how far a corner leaves the plane of the diagonals, over the face's size
        if bend > FLAT:
            raise SystemExit(f"face {element} is not flat ({bend:.2g} of its size out of plane): its plies' axes would not lie in it")
        warp = max(warp, bend)
        entry = parts[mesh["part"][element]]
        home = next((number for number, other in enumerate(sections) if other["part"] == entry["id"] and dot(normal, other["normal"]) >= math.cos(SAME_WAY)), None)
        if home is None:
            named = ANGLES_FROM[entry["id"]]
            lean = dot(named, normal)
            if abs(lean) > 0.5:
                raise SystemExit(f"face {element} of {entry['name']} is too far from the axis its angles are counted from to lay it on the face")
            axis = tuple((named[i] - lean * normal[i]) / math.sqrt(1 - lean * lean) for i in range(3))  # the named axis laid on the face
            across = cross(normal, axis)
            frames = {}
            for angle in sorted(set(entry["angles"])):
                c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
                along = tuple(c * axis[i] + s * across[i] for i in range(3))
                frames[angle] = (along, cross(normal, along))
            home = len(sections)
            sections.append({"name": f"{entry['id']}-{sum(1 for other in sections if other['part'] == entry['id']) + 1:02d}", "part": entry["id"],
                             "angles": entry["angles"], "normal": normal, "axis": axis, "frames": frames, "elements": []})
        sections[home]["elements"].append(element)
        section_of.append(home)
        turn = cross(normal, sections[home]["normal"])
        off_axes = max(off_axes, math.atan2(math.sqrt(dot(turn, turn)), dot(normal, sections[home]["normal"])))

    owners: dict[int, set[str]] = {}
    for element, corners in enumerate(mesh["quads"]):
        for n in corners:
            owners.setdefault(n, set()).add(parts[mesh["part"][element]]["id"])
    loaded = sorted(n for n, names in owners.items() if {"upper-skin", "ribs"} <= names and names & set(SPARS) and nodes[n][1] > 0)
    stations = len(record["wing"]["ribs"]) - 1
    if len(loaded) != len(SPARS) * stations:
        raise SystemExit(f"{len(loaded)} points where a spar, a rib outboard of the root and the upper skin meet, not {len(SPARS) * stations}")
    return {"nodes": nodes, "elements": elements, "sections": sections, "section_of": section_of, "areas": areas, "off_axes": off_axes, "warp": warp,
            "root": [n for n, place in enumerate(nodes) if place[1] == 0.0], "loaded": loaded}


def orientation_name(section: str, angle: float) -> str:
    """A section's name and the ply angle, the fea package's way ("m45" for -45); within the 20 characters CalculiX prints of a name."""
    return f"{section}-{'m' if angle < 0 else ''}{abs(angle):g}"


def deck(model: dict, ply: dict) -> str:
    """The CalculiX input: numbers from 1, the faces' numbers the stored ones plus one."""
    out = ["*HEADING", "The demo's example wing, written by scripts/demo-wing.py: mm, N, MPa"]
    out += [f"** {line}" for line in ply["sources"]]
    out.append("*NODE, NSET=Nall")
    out += [f"{n + 1}, {number(x)}, {number(y)}, {number(z)}" for n, (x, y, z) in enumerate(model["nodes"])]
    for section in model["sections"]:
        out.append(f"*ELEMENT, TYPE=S8R, ELSET={section['name']}")
        out += [f"{element + 1}, " + ", ".join(str(n + 1) for n in model["elements"][element]) for element in section["elements"]]
    out += ["*ELSET, ELSET=Eall, GENERATE", f"1, {len(model['elements'])}, 1", "*NSET, NSET=Root"]
    out += [", ".join(str(n + 1) for n in model["root"][i:i + 16]) for i in range(0, len(model["root"]), 16)]
    out += [f"*MATERIAL, NAME={MATERIAL}", "*ELASTIC, TYPE=ENGINEERING CONSTANTS",
            ", ".join(number(ply[name]) for name in ("E1", "E2", "E3", "nu12", "nu13", "nu23", "G12", "G13")),
            f"{number(ply['G23'])}, {number(REFERENCE_TEMPERATURE)}"]
    out.append("** One *ORIENTATION for each ply angle of each section: axis 1 along the fibres, axis 2 across them in the face, so axis 3 is the face's normal.")
    for section in model["sections"]:
        for angle, (along, across) in section["frames"].items():
            out += [f"*ORIENTATION, NAME={orientation_name(section['name'], angle)}", ", ".join(number(value) for value in along + across)]
    out.append("** Layer lines are listed from the face the normal leaves, the first ply of the part's layup, to the face it points out of.")
    for section in model["sections"]:
        out.append(f"*SHELL SECTION, ELSET={section['name']}, COMPOSITE")
        out += [f"{number(ply['thickness'])}, , {MATERIAL}, {orientation_name(section['name'], angle)}" for angle in section["angles"]]
    out += ["*BOUNDARY", "Root, 1, 6", "*STEP", "*STATIC", "*CLOAD"]
    out += [f"{n + 1}, 3, {number(LOAD / len(model['loaded']))}" for n in model["loaded"]]
    out += ["*NODE PRINT, NSET=Root, TOTALS=ONLY", "RF", "*NODE PRINT, NSET=Nall", "U", "*EL PRINT, ELSET=Eall, GLOBAL=YES", "S", "*END STEP"]
    return "\n".join(out) + "\n"


def find_ccx() -> str:
    """The solver, as the fea package looks for it: ANISOTROPY_CCX, then `ccx` or `ccx_dynamic` on the path."""
    named = os.environ.get("ANISOTROPY_CCX")
    if named:
        if not Path(named).is_file():
            raise SystemExit(f"CalculiX executable not found at {named} (from ANISOTROPY_CCX)")
        return named
    solver = next((path for path in map(shutil.which, ("ccx", "ccx_dynamic", "ccx_static")) if path), None)
    if solver is None:
        raise SystemExit("--solve needs CalculiX: put `ccx` on the path or name it in ANISOTROPY_CCX (docs/installation-fea-tools.md)")
    return solver


def run_ccx(text: str, folder: Path) -> tuple[str, float, str]:
    """Runs the deck in the folder; the solver's version, the seconds the solve took and what it printed (the .dat). One thread for
    the equation solver, as the fea package runs it: SPOOLES on several gives a different answer on every run."""
    solver = find_ccx()
    told = subprocess.run([solver, "-v"], capture_output=True, text=True, check=False)
    version = re.search(r"Version\s+([\d.]+)", told.stdout + told.stderr)
    (folder / "wing.inp").write_text(text, encoding="utf-8", newline="\n")
    start = time.perf_counter()
    done = subprocess.run([solver, "-i", "wing"], cwd=folder, capture_output=True, text=True, check=False,
                          env={**os.environ, "OMP_NUM_THREADS": "1", "CCX_NPROC_EQUATION_SOLVER": "1"})
    seconds = time.perf_counter() - start
    console = done.stdout + done.stderr
    (folder / "wing.log").write_text(console, encoding="utf-8", newline="\n")
    dat = folder / "wing.dat"
    if done.returncode != 0 or "*ERROR" in console or not dat.exists():
        raise SystemExit(f"CalculiX failed on the wing (exit {done.returncode}):\n{console[-3000:]}")
    return (version.group(1) if version else "of an unknown version"), seconds, dat.read_text(encoding="utf-8", errors="replace")


def read_dat(text: str) -> dict[str, list[list[float]]]:
    """The .dat's blocks by their first word ("total", "displacements", "stresses"): the rows of numbers under each heading."""
    blocks: dict[str, list[list[float]]] = {}
    rows: list[list[float]] | None = None
    for line in text.splitlines():
        if " for set " in line:
            rows = blocks.setdefault(line.split()[0], [])
        elif line.strip() and rows is not None:
            rows.append([float(value) for value in line.split()])
    return blocks


def strength_used(stress: Vector, ply: dict) -> tuple[float, str]:
    """The maximum-stress index of a ply's stress in its own axes (along the fibres, across them, in shear), and its mode."""
    s1, s2, t12 = stress
    return max(zip((s1 / ply["F1t"], -s1 / ply["F1c"], s2 / ply["F2t"], -s2 / ply["F2c"], abs(t12) / ply["F6"]), MODES))


def solve(record: dict, keep: Path | None) -> dict:
    """Solves the wing and returns what is recorded of the answer: the load, the field, the stored nodes' displacements and the
    solve's numbers. Prints the checks."""
    ply = lamina()
    model = shell_model(record)
    with tempfile.TemporaryDirectory() as scratch:
        folder = Path(scratch) if keep is None else keep
        folder.mkdir(parents=True, exist_ok=True)
        version, seconds, dat = run_ccx(deck(model, ply), folder)
    blocks = read_dat(dat)
    mesh, parts, sections, section_of = record["mesh"], record["parts"], model["sections"], model["section_of"]
    count = len(mesh["quads"])
    if len(blocks.get("total", [])) != 1 or len(blocks.get("displacements", [])) != len(model["nodes"]):
        raise SystemExit("CalculiX's .dat does not hold the root's total force and every node's displacement")

    # Each ply's stress in its own axes at each of its integration points, from CalculiX's global stress (sxx, syy, szz, sxy, sxz, syz).
    def resolved(a: Vector, b: Vector) -> tuple[float, ...]:
        return (a[0] * b[0], a[1] * b[1], a[2] * b[2], a[0] * b[1] + a[1] * b[0], a[0] * b[2] + a[2] * b[0], a[1] * b[2] + a[2] * b[1])

    axes = [[(resolved(along, along), resolved(across, across), resolved(along, across)) for along, across in (section["frames"][angle] for angle in section["angles"])]
            for section in sections]
    worst: list[tuple[float, str, int]] = [(0.0, "", 0)] * count  # the index, its mode and its ply (from 0)
    spanwise, lifting, points = [0.0] * count, [0.0] * count, [0] * count  # syy and syz summed over a face's integration points, and their number
    for row in blocks.get("stresses", []):
        element, point, stress = int(row[0]) - 1, int(row[1]) - 1, row[2:8]
        layer = point // POINTS_A_PLY
        value, mode = strength_used(tuple(sum(c * s for c, s in zip(axis, stress)) for axis in axes[section_of[element]][layer]), ply)
        worst[element] = max(worst[element], (value, mode, layer))
        spanwise[element] += stress[1]
        lifting[element] += stress[5]
        points[element] += 1
    for element in range(count):
        expected = POINTS_A_PLY * len(sections[section_of[element]]["angles"])
        if points[element] != expected:
            raise SystemExit(f"CalculiX printed {points[element]} integration points for face {element}, not {expected}")
        spanwise[element] /= expected  # the plies are one thickness, so the mean over the points is the mean through the laminate
        lifting[element] /= expected

    # The vertical force each span cell carries across its section, from the solver's stresses: the mean syz of a face times its
    # section (its area by its thickness over its length along the span). Between two ribs it is the load outboard of the cell.
    carried: dict[float, float] = {}
    for element, corners in enumerate(mesh["quads"]):
        ys = [mesh["nodes"][n][1] for n in corners]
        if max(ys) > min(ys):  # a rib lies in a section and carries nothing across it
            thickness = ply["thickness"] * len(sections[section_of[element]]["angles"])
            station = round(sum(ys) / 4, 6)
            carried[station] = carried.get(station, 0.0) + lifting[element] * model["areas"][element] * thickness / (max(ys) - min(ys))
    share = LOAD / len(model["loaded"])
    outboard = {station: sum(share for n in model["loaded"] if model["nodes"][n][1] > station) for station in carried}
    beside_root = min(carried)

    values = [float(f"{value:.4g}") for value, _, _ in worst]
    centre = [sum(mesh["nodes"][n][1] for n in corners) / 4 for corners in mesh["quads"]]
    largest = [max(range(entry["first"], entry["first"] + entry["count"]), key=values.__getitem__) for entry in parts]
    governs = max(largest, key=values.__getitem__)
    entry = parts[mesh["part"][governs]]
    _, mode, layer = worst[governs]
    moved = {int(row[0]) - 1: row[1:4] for row in blocks["displacements"]}
    rise = max(move[2] for move in moved.values())
    answer = {
        "load": load_of(record),
        "field": {"key": "strength_used", "label": "Strength used", "unit": "", "min": min(values), "max": max(values), "values": values},
        "displacement": {"unit": "mm", "values": [[round(value, 2) + 0.0 for value in moved[n]] for n in range(len(mesh["nodes"]))]},  # the stored nodes, in their order; + 0.0 so no -0.0
        "solve": {
            "solver": f"CalculiX {version}",
            "recorded": datetime.date.today().isoformat(),
            "nodes": len(model["nodes"]),
            "elements": count,
            "seconds": round(seconds, 1),
            "reaction": round(carried[beside_root], 2),
            "tip_deflection": round(rise, 2),
            "parts": [{"id": part["id"], "max": values[element], "at": round(centre[element], 1)} for part, element in zip(parts, largest)],
            "governing": {"part": entry["id"], "value": values[governs], "at": round(centre[governs], 1), "ply": layer + 1, "angle": entry["angles"][layer], "mode": mode},
        },
    }

    # The checks, printed with every solve.
    print(f"solved by CalculiX {version} in {seconds:.1f} s: {len(model['nodes'])} nodes, {count} elements, {len(sections)} sections; a face is turned at most "
          f"{math.degrees(model['off_axes']):.4f} degrees from its section's ply axes and leaves its own plane by at most {model['warp']:.1g} of its size")
    print("  the ply: " + ", ".join(f"{name} {ply[name]:.6g}" for name in ("E1", "E2", "E3", "G12", "G13", "G23", "F1t", "F1c", "F2t", "F2c", "F6")) + " MPa; "
          + ", ".join(f"{name} {ply[name]:g}" for name in ("nu12", "nu13", "nu23")) + f"; ply thickness {ply['thickness']:.5g} mm")
    for source in ply["sources"]:
        print(f"    {source}")
    off = max(carried, key=lambda station: abs(carried[station] - outboard[station]))
    print(f"  1 balance: the span cell beside the root carries {carried[beside_root]:.3f} N to it, summed from the solver's stresses, against {LOAD} N applied, "
          f"a difference of {carried[beside_root] - LOAD:+.3f} N; of the {len(carried)} cells the one {off:.1f} mm out is furthest from the load outboard of it, "
          f"{carried[off]:.3f} N against {outboard[off]:.3f} N")
    print(f"    CalculiX's own total of the reactions printed for the root's nodes is {-blocks['total'][0][2]:.3f} N and is not used: on shell nodes whose rotations "
          f"are held it is not the whole reaction (fea/checks/calculix-conventions.toml, shell_set_totals)")
    # Near the root, clear of the held edge: the skins' faces between the spars in the second span cell, at the local chord.
    near = sorted(carried)[1]
    nose, chord = plan(record["wing"], near)
    front, rear = (nose + chord_share * chord for chord_share in record["wing"]["spars"])
    sample = {name: [element for element in range(count) if parts[mesh["part"][element]]["id"] == name and abs(centre[element] - near) < 1e-6
                     and front < sum(mesh["nodes"][n][0] for n in mesh["quads"][element]) / 4 < rear] for name in ("upper-skin", "lower-skin")}
    mean = {name: sum(spanwise[element] for element in faces) / len(faces) for name, faces in sample.items()}
    height = {name: sum(mesh["nodes"][n][2] for element in faces for n in mesh["quads"][element]) / (4 * len(faces)) for name, faces in sample.items()}
    print(f"  2 signs: the stress along the span, averaged through the laminate, between the spars {near:.1f} mm from the root: "
          f"upper skin {mean['upper-skin']:+.2f} MPa, lower skin {mean['lower-skin']:+.2f} MPa")
    moment = sum(share * (model["nodes"][n][1] - near) for n in model["loaded"])
    depth = height["upper-skin"] - height["lower-skin"]
    area = (rear - front) * ply["thickness"] * len(parts[0]["angles"])
    estimate, solved = moment / (depth * area), (mean["lower-skin"] - mean["upper-skin"]) / 2
    print(f"  3 by hand: the bending moment there is {moment:.0f} N mm ({sum(share * model['nodes'][n][1] for n in model['loaded']):.0f} at the root) and the chord "
          f"{chord:.1f} mm; as a box of two skins {depth:.2f} mm apart, each {area:.1f} mm2 between the spars, that is {estimate:.1f} MPa; the solver's two skins average "
          f"{solved:.1f} MPa, {solved / estimate:.2f} of it (the estimate leaves out the skin outside the spars and the webs, which carry the rest)")
    print(f"  4 deflection: the tip rises {rise:.2f} mm, {100 * rise / record['wing']['span']:.2f} % of the span")
    for part, element in zip(parts, largest):
        print(f"  {part['name']}: strength used at most {values[element]:.4g}, {centre[element]:.1f} mm from the root")
    print(f"  governing: {entry['name']}, {values[governs]:.4g} of its strength used {centre[governs]:.1f} mm from the root, ply {layer + 1} ({entry['angles'][layer]} degrees) in {mode}")
    return answer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--solve", action="store_true", help="also solve the wing with CalculiX and record the answer")
    parser.add_argument("--keep", type=Path, metavar="FOLDER", help="with --solve: keep the deck and the solver's files in this folder")
    args = parser.parse_args()
    record = build()
    record["built"] = datetime.date.today().isoformat()
    if args.solve:
        record.update(solve(record, args.keep))
    elif OUT.exists():
        # The analysis already recorded stays only while it is the analysis of this wing and this load.
        old = json.loads(OUT.read_text(encoding="utf-8"))
        recorded = {key: old[key] for key in RECORDED if key in old}
        same = all(old.get(key) == record[key] for key in ("wing", "parts", "mesh")) and old.get("load") == load_of(record)
        if len(recorded) == len(RECORDED) and same:
            record.update(recorded)
            print(f"the analysis recorded on {old['solve']['recorded']} is kept: the wing and its load are unchanged")
        elif recorded:
            print("the wing or its load changed, so the recorded analysis is dropped: record it again with --solve")
    OUT.write_text(json.dumps(record, separators=(",", ":")) + "\n", encoding="utf-8")
    mesh = record["mesh"]
    print(f"{OUT.relative_to(ROOT)}: {len(mesh['nodes'])} nodes, {len(mesh['quads'])} faces, {OUT.stat().st_size // 1024} KB")
    for entry in record["parts"]:
        print(f"  {entry['name']}: {entry['count']} faces, {entry['layup']}")


if __name__ == "__main__":
    main()
