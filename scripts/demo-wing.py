#!/usr/bin/env python3
"""Builds the example wing the home page's product demo shows (ADR-0098) and records its analysis.

    python3 scripts/demo-wing.py            # the geometry and the mesh only; a recorded analysis of the same wing is kept
    python3 scripts/demo-wing.py --solve    # and the analysis (needs CalculiX's `ccx` on the path, and `uv` for the engine)

The wing is an example made for the demo, not a design of ours or of anyone's: a tapered, swept half wing with one aerofoil
along its span, two skins over two spar webs and nine ribs, each rib the aerofoil's shape but for its two tips, with the spars
running through it, and at its tip a winglet. Its only borrowed number is the span, 7 ft, which a public news story gives for
the wings of a student design class (UC San Diego Today, "Structural Engineering Students Design, Build and Test Unmanned Aerial
Vehicle Wings"); the chords and the sweep are round numbers chosen for the picture, and the aerofoil is the public NACA 2412
formula, scaled by the local chord and laid off vertically from it. The leading and the trailing edge are straight, the spars
lie at fixed shares of the local chord, and the ribs stand in planes of constant y.

The winglet (the lead, 2026-11-14: "add a wing tip to it", with a picture of a blended winglet for the look) begins at the tip
rib, where the 7 ft still end, and the two skins and the two spar webs carry on into it at the same chord shares. Its numbers
are round ones chosen for the picture; none is measured from that picture or taken from an aircraft. Seen along x, the chord
line turns up through an arc of 120 mm radius until it leans 75 degrees from the wing's plane (the bend, eight cells), then runs
straight for 250 mm (the fin, eight cells). Every station holds the same aerofoil at its local chord, laid off square to the
chord in a plane through x that is turned up as far as the chord line is, so the wing's upper skin becomes the fin's inboard
face. Out along the chord line both edges move aft: round the bend each edge's slope grows evenly from the wing's own to the
fin's, and up the fin both are straight, the leading edge 41 and the trailing edge 26 degrees aft of the fin's span line. That
puts the fin's tip, 90 mm of chord (0.4 of the wing tip's), 300 mm aft of the wing tip at its leading edge, 330.4 mm above the
wing's chord line and 180.6 mm outboard of the tip rib. One rib stands where the bend ends and one closes the fin's tip.

What it writes, in lib/demo-wing.json: the parts, the mesh the page draws (corner nodes and four-node faces, the very mesh that
is solved) and, with --solve, one value an element and the displacement of every stored node from the solver's answer. Lengths
are mm, forces N, stresses MPa, as in the fea package's coupon files. The winglet's numbers and its stations are in the record's
`wing.winglet`, each with a line that says what it measures.

The analysis (--solve) is one linear static step of CalculiX on the stored faces, written as the fea package writes a laminate
(fea/src/anisotropy_fea/write_calculix.py): every face an eight-node composite shell (S8R) with a node added in the middle of
each edge, one shared by the faces on that edge; the ply as *ELASTIC, TYPE=ENGINEERING CONSTANTS; one *ORIENTATION for each ply
angle. CalculiX's orientation is a fixed frame in space, not one that follows a shell, so a part has one section, with its own
orientations, for each direction its faces look in, all with the part's one layup. In the wing the lines of one chord share all
meet in one point beyond the tip, so the strip of skin between two of them is flat, and so is each spar web: a fixed frame is
exact for a strip but for the rounding of the stored corners, which turns a face at most SAME_WAY (0.03 degrees) from its
section's axes (the solve prints the largest turn). The fin is the same: its stations are parallel and its edges straight, so
each of its strips and webs is flat and has one section. The root's nodes are held in all six freedoms and LOAD is shared
between the points where the spars meet the upper skin at the wing's ribs outboard of the root, the tip rib the last of them.
None is put on the winglet: it is an example load, not a flight load, and stays the load of the wing before it had a winglet.

The bend is the exception to flat faces, and it is allowed for by name (FLAT_BEND), not by loosening FLAT. Where a section
turns and moves aft at once, the four corners of a face between two stations do not lie in one plane, so the face is twisted.
Flat faces there would need a bend with no sweep and no taper in it, or a section sheared as it goes round, the inside of a
bend being shorter than its outside (worked out by hand, not checked a second way); the twist was chosen so that every station
keeps the aerofoil and both edges run smoothly into the fin. Measured on this mesh (2026-11-14; the solve prints the largest of
each): a skin's face in the bend leaves the plane of its diagonals by at most 0.018 of its size and a web's by at most 0.036,
against the 0.001 that FLAT allows everywhere else and that 255 of the bend's 320 skin faces still keep (the others lie in the
first fifth of the chord and, on the upper skin, by the trailing edge). FLAT_BEND allows the bend's 352 faces 0.05. Each of
them has a section of its own, with ply axes laid on the plane of its diagonals, and its surface at a corner is turned from
that plane, so from those axes, by at most 3.4 degrees. CalculiX holds those axes fixed on a twisted face as on a flat one: its
own print of each layer's stress in the layer's orientation agrees with the ply-axis stress made here to 1e-6 MPa at the bend's
22,016 points (by hand, 2026-11-14). Nothing is loaded there: the winglet rides on the tip rib as a rigid body to within
0.002 mm (by hand on the same solve), and its largest strength used is 0.0037, in the rear spar beside the tip rib (the solve
prints it).

A part's ply angles turn counterclockwise about its faces' normal, seen from the side the normal points to, from the part's
axis laid on the face (its projection onto the face), and its plies are listed from the face behind the normal to the face it
points out of (ADR-0004). The axis is the span line for the skins and the spars and the chord (x) for the ribs. In the wing the
span line is y. In the winglet it is the winglet's own: seen along x, the straight line from one station's chord line to the
next, so 0 degrees carries on round the bend, a cell at a time, and up the fin. So 0 degrees in a skin runs straight out along
the span, within 1 degree of y in plan aft of the first 6 % of the chord and up to 8 degrees from it on the steep faces of the
nose, and crosses the swept spars at about 9 and 7 degrees; 0 degrees in a spar web runs along the spar. In the fin's skins it
runs straight up the fin: seen square on, within about 1 degree of the fin's span line aft of the first 15 % of the chord and
up to 32 degrees from it on the steep faces of the nose, where it turns towards the swept leading edge; it crosses the fin's spars,
which are swept more than the wing's, at about 38 and 32 degrees, and in a web it still runs along the spar. A face cannot take
an axis it looks nearly along: the solve stops if a face's normal comes within 45 degrees of its axis (LEAN; the winglet's
swept webs come within 51.6). The skins' normals point out of the wing, so each skin's layup reads as the skin is seen from
outside the wing, its first ply the innermost: a +45 degree ply runs outboard and towards the nose in the upper skin, outboard
and towards the tail in the lower, and in the winglet the same with up the fin for outboard. The spars' normals point aft, so
their +45 runs outboard and up, towards the upper skin; the ribs' point to the root (-y; the winglet's two back down its span
line), so theirs runs aft and up, towards the upper skin.

The value kept for a face is the strength used: the largest maximum-stress index over its plies and their integration points,
each ply's stress in its own axes against the library's strengths (0 unloaded, 1 the first ply fails). The reaction kept is the
vertical force the span cell beside the root carries to it, summed from the solver's stresses: the total CalculiX prints for
the root's nodes is not the whole reaction once their rotations are held (printed with the checks, and not used). The tip
deflection kept is the largest rise of any node. With the winglet that is the fin's tip, which stands 180.6 mm further out and
is lifted by the tip rib's slope as well as by its rise; the tip rib's own largest rise is kept beside it.

What the step does not see: buckling, the bonds between the parts, damage after the first ply fails, or large deflections. The
same deck with *BUCKLE in place of *STATIC puts the upper skin's first buckling, between the spars in the bay beside the root,
at 1099 N (CalculiX 2.21, 2026-11-14, on this mesh with its winglet, which was not refined for it; run by hand and not
recorded). That is the factor and the place found before the winglet was added, and the first four modes all lie in the wing's
upper skin in the two bays beside the root, none in the winglet. LOAD is the largest of 250, 500, 750 and 1000 N that is no
more than 0.6 of that.
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

# The winglet outboard of the tip rib, at the lead's word of 2026-11-14 ("add a wing tip to it"): round numbers chosen for the
# picture, none of them an aircraft's.
WINGLET_CANT = 75.0  # degrees: how far the fin leans up from the wing's plane, turned about the chord (x); 90 would stand upright
WINGLET_RADIUS = 120.0  # mm: the arc the chord line turns through in the bend, seen along x
WINGLET_FIN = 250.0  # mm: the fin's length along its own span line, from the end of the bend to its tip
WINGLET_SWEEP = 300.0  # mm: how far aft of the wing tip's leading edge the fin tip's lies, along x
WINGLET_TIP_CHORD = 90.0  # mm: 0.4 of the wing's tip chord
BEND_CELLS, FIN_CELLS = 8, 8  # span cells in the bend (9.375 degrees each) and in the fin (31.25 mm each)
WINGLET_RIBS = (BEND_CELLS, BEND_CELLS + FIN_CELLS)  # a rib where the bend ends and one that closes the fin's tip, in stations out from the tip rib
WINGLET_MEASURES = {
    "cant": "degrees the fin leans up from the wing's plane, turned about the chord (x); 90 would stand upright",
    "radius": "mm, the arc the chord line turns through in the bend, seen along x",
    "fin": "mm, the fin's length along its own span line, from the end of the bend to its tip",
    "sweep": "mm, how far aft of the wing tip's leading edge the fin tip's leading edge lies, along x",
    "tip_chord": "mm, the chord at the fin's tip",
    "rise": "mm, how far the fin tip's chord line stands above the wing's (z = 0)",
    "reach": "mm, how far outboard of the tip rib the fin tip's chord line lies, along y",
    "ribs": "mm out along the span line from the tip rib: the rib where the bend ends and the rib that closes the fin's tip",
    "stations": "one row a station outboard of the tip rib: mm out along the span line from the tip rib; the leading edge's x, y and z; "
                "the chord, which runs along x; the degrees the section is turned up about x",
}

# The parts, in the order the page lists them. Angles are counted from the span line (y in the wing, the winglet's own outboard
# of the tip rib), laid on the face, for the skins and the spars, and from the chord (x) for the ribs; the layups are examples in
# the library's IM7 / 8552 tape. The winglet's faces belong to these same five parts.
PARTS = [
    {"id": "upper-skin", "name": "Upper skin", "layup": "[45/0/-45/90]s", "angles": [45, 0, -45, 90, 90, -45, 0, 45]},
    {"id": "lower-skin", "name": "Lower skin", "layup": "[45/0/-45/90]s", "angles": [45, 0, -45, 90, 90, -45, 0, 45]},
    {"id": "front-spar", "name": "Front spar", "layup": "[45/-45/0]s", "angles": [45, -45, 0, 0, -45, 45]},
    {"id": "rear-spar", "name": "Rear spar", "layup": "[45/-45/0]s", "angles": [45, -45, 0, 0, -45, 45]},
    {"id": "ribs", "name": "Ribs", "layup": "[45/-45]s", "angles": [45, -45, -45, 45]},
]
LIBRARY = "im7-8552"

# The analysis.
CHORDWISE = (1.0, 0.0, 0.0)  # the ribs' angles are counted from the chord; the skins' and the spars' from the span line of their cell (build)
LOAD = 500  # N upward in all: an example of a test that loads a wing at its ribs, not a flight load. A linear static step cannot
# see buckling, so the load is the largest of 250, 500, 750 and 1000 N that is no more than 0.6 of the upper skin's first buckling
# load: one linear buckling step on this mesh, winglet and all, gave the factor 1.0985 under 1000 N (2026-11-14), as the mesh without
# the winglet had, so 1099 N and 0.6 of it 659 N. The mesh was not refined for buckling, so the factor is not a checked number.
COUPON = ROOT / "tests" / "fixtures" / "studio-standards" / "values.json"  # the public coupon example of the same material: its G13 and G23
MATERIAL = "IM7-8552-Lamina"
REFERENCE_TEMPERATURE = 293.0  # K, as the fea package's decks state it; CalculiX needs a value on the constants' second line
FLAT = 1e-3  # a face's corners may leave its plane by this share of its size: the corners are stored rounded
FLAT_BEND = 0.05  # and a face of the winglet's bend by this share: there a face is twisted (the docstring), a web's by 0.036 of its size at most
SAME_WAY = math.radians(0.03)  # faces whose normals are this close share a section and its ply axes
LEAN = math.cos(math.radians(45))  # a face's normal may come this close to the axis its angles are counted from, as the cosine between them:
# nearer than 45 degrees and the axis laid on the face would turn more than the face's own normal is uncertain. It was 0.5 (60 degrees) for the
# wing alone, whose faces reach 0.16; the fin's swept webs and nose reach 0.62, their normals 51.6 degrees from the span line.
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


def winglet_stations() -> list[dict]:
    """The stations outboard of the tip rib, the nearest first: how far out along the span line each lies (`out`), where its leading
    edge is (`nose` along x, `y`, `z`), its chord and how far its section is turned up about x (`cant`, in radians). Seen along x the
    chord line turns through an arc of WINGLET_RADIUS in BEND_CELLS equal steps until it leans WINGLET_CANT, then runs straight for
    WINGLET_FIN. Out along that line each edge moves aft: its slope grows evenly round the bend from the wing's own to the fin's,
    and in the fin it is straight. The fin's two slopes are the ones that put its tip's leading edge WINGLET_SWEEP aft of the wing
    tip's and leave WINGLET_TIP_CHORD of chord there."""
    cant = math.radians(WINGLET_CANT)
    bend = WINGLET_RADIUS * cant  # the bend's length along the chord line
    wing_edges = (SWEEP / SPAN, (SWEEP + TIP_CHORD - ROOT_CHORD) / SPAN)  # mm aft a mm of span: the leading edge, the trailing edge
    fin_edges = ((WINGLET_SWEEP - wing_edges[0] * bend / 2) / (bend / 2 + WINGLET_FIN),
                 (WINGLET_SWEEP + WINGLET_TIP_CHORD - TIP_CHORD - wing_edges[1] * bend / 2) / (bend / 2 + WINGLET_FIN))

    def aft(out: float, wing: float, fin: float) -> float:
        """How far aft an edge has moved, `out` along the span line from the tip rib."""
        if out <= bend:
            return wing * out + (fin - wing) * out * out / (2 * bend)
        return (wing + fin) * bend / 2 + fin * (out - bend)

    stations = []
    for step in range(1, BEND_CELLS + FIN_CELLS + 1):
        turned = cant * min(step, BEND_CELLS) / BEND_CELLS
        up_fin = WINGLET_FIN * max(step - BEND_CELLS, 0) / FIN_CELLS
        out = WINGLET_RADIUS * turned + up_fin
        nose, tail = SWEEP + aft(out, wing_edges[0], fin_edges[0]), SWEEP + TIP_CHORD + aft(out, wing_edges[1], fin_edges[1])
        stations.append({"out": out, "nose": nose, "y": SPAN + WINGLET_RADIUS * math.sin(turned) + up_fin * math.cos(cant),
                         "z": WINGLET_RADIUS * (1 - math.cos(turned)) + up_fin * math.sin(cant), "chord": tail - nose, "cant": turned})
    return stations


def build() -> tuple[dict, dict]:
    """The mesh: nodes as [x along the chord from the root's leading edge, y along the span, z up] in mm, four-node faces, and
    each face's part. Every station of the wing is a plane of constant y holding the aerofoil at the local chord, so the lines
    of one chord share are straight and every face of the skins and the webs is flat but for the rounding of its corners. A
    station of the winglet holds the aerofoil at its chord in a plane through x turned up by the station's cant; its nodes are
    stored to 0.001 mm, the wing's as they were. With the record comes how the analysis lays each face's plies (`lay`): the span
    cell a face of a skin or a web lies in (None for a rib's), the axis its ply angles are counted from (the cell's span line:
    seen along x, from one station's chord line straight to the next; the chord for a rib), whether it lies in the bend, and
    how far out the middle of each span cell lies."""
    wing = {"span": SPAN, "root_chord": ROOT_CHORD, "tip_chord": TIP_CHORD, "sweep": SWEEP}
    outboard = winglet_stations()
    nodes: list[list[float]] = []
    index: dict[tuple[int, int, int], int] = {}
    last_chord = len(CHORD_STATIONS) - 1

    def node(i: int, j: int, k: int) -> int:
        """The node at chord station i, span station j (the winglet's follow the wing's) and depth level k (0 the lower skin,
        DEPTH_CELLS the upper)."""
        if i in (0, last_chord):
            k = 0  # the two skins meet on the leading and the trailing edge
        key = (i, j, k)
        if key not in index:
            upper, lower = surface(CHORD_STATIONS[i])
            index[key] = len(nodes)
            if j <= SPAN_CELLS:
                y = SPAN * j / SPAN_CELLS
                nose, chord = plan(wing, y)
                z = (lower + (upper - lower) * k / DEPTH_CELLS) * chord
                nodes.append([round(nose + CHORD_STATIONS[i] * chord, 2), round(y, 2), round(z, 3)])
            else:
                station = outboard[j - SPAN_CELLS - 1]
                off = (lower + (upper - lower) * k / DEPTH_CELLS) * station["chord"]  # off the chord line, in the turned section
                nodes.append([round(station["nose"] + CHORD_STATIONS[i] * station["chord"], 3),
                              round(station["y"] - off * math.sin(station["cant"]), 3), round(station["z"] + off * math.cos(station["cant"]), 3)])
        return index[key]

    cells = SPAN_CELLS + len(outboard)
    chord_line = [(SPAN * j / SPAN_CELLS, 0.0) for j in range(SPAN_CELLS + 1)] + [(station["y"], station["z"]) for station in outboard]  # seen along x
    span_line: list[tuple[float, float, float]] = []
    for (y, z), (next_y, next_z) in zip(chord_line, chord_line[1:]):
        length = math.hypot(next_y - y, next_z - z)
        span_line.append((0.0, (next_y - y) / length, (next_z - z) / length))

    quads: list[list[int]] = []
    part: list[int] = []
    cell_of: list[int | None] = []
    where = {entry["id"]: number for number, entry in enumerate(PARTS)}

    def face(name: str, corners: list[int], cell: int | None) -> None:
        quads.append(corners)
        part.append(where[name])
        cell_of.append(cell)

    # The skins: every face is listed so that its normal points out of the wing.
    for j in range(cells):
        for i in range(last_chord):
            face("upper-skin", [node(i, j, DEPTH_CELLS), node(i + 1, j, DEPTH_CELLS), node(i + 1, j + 1, DEPTH_CELLS), node(i, j + 1, DEPTH_CELLS)], j)
    for j in range(cells):
        for i in range(last_chord):
            face("lower-skin", [node(i, j, 0), node(i, j + 1, 0), node(i + 1, j + 1, 0), node(i + 1, j, 0)], j)
    # The spar webs, from the lower skin to the upper.
    for name, share in SPARS.items():
        i = CHORD_STATIONS.index(share)
        for j in range(cells):
            for k in range(DEPTH_CELLS):
                face(name, [node(i, j, k), node(i, j + 1, k), node(i, j + 1, k + 1), node(i, j, k + 1)], j)
    # The ribs: whole aerofoils through the spars, from the first chord station behind the leading edge to the last before the
    # trailing edge, where the skins are still apart. The winglet's two follow the wing's nine.
    rib_stations = list(range(0, SPAN_CELLS + 1, RIB_EVERY))
    for j in rib_stations + [SPAN_CELLS + step for step in WINGLET_RIBS]:
        for i in range(1, last_chord - 1):
            for k in range(DEPTH_CELLS):
                face("ribs", [node(i, j, k), node(i + 1, j, k), node(i + 1, j, k + 1), node(i, j, k + 1)], None)

    parts = []
    for number, entry in enumerate(PARTS):
        members = [element for element, owner in enumerate(part) if owner == number]
        parts.append({**entry, "first": members[0], "count": len(members)})
        assert members == list(range(members[0], members[0] + len(members))), "a part's faces are stored together"
    upper_max = max(surface(share)[0] for share in CHORD_STATIONS)
    lower_min = min(surface(share)[1] for share in CHORD_STATIONS)
    tip = outboard[-1]
    record = {
        "what": "An example wing made for the demo: a tapered, swept half wing that ends in a blended winglet, two skins over two spar webs and eleven ribs",
        "units": {"length": "mm", "force": "N", "stress": "MPa"},
        "wing": {
            "span": SPAN,  # to the tip rib, where the winglet begins
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
            "winglet": {
                "cant": WINGLET_CANT,
                "radius": WINGLET_RADIUS,
                "fin": WINGLET_FIN,
                "sweep": WINGLET_SWEEP,
                "tip_chord": WINGLET_TIP_CHORD,
                "rise": round(tip["z"], 3),
                "reach": round(tip["y"] - SPAN, 3),
                "ribs": [round(outboard[step - 1]["out"], 3) for step in WINGLET_RIBS],
                "stations": [[round(station[key], 3) for key in ("out", "nose", "y", "z", "chord")] + [round(math.degrees(station["cant"]), 3)] for station in outboard],
                "measures": WINGLET_MEASURES,
            },
        },
        "parts": parts,
        "mesh": {"nodes": nodes, "quads": quads, "part": part},
    }
    outs = [0.0] + [station["out"] for station in outboard]
    lay = {"cell": cell_of, "axis": [CHORDWISE if cell is None else span_line[cell] for cell in cell_of],
           "bend": [cell is not None and SPAN_CELLS <= cell < SPAN_CELLS + BEND_CELLS for cell in cell_of],
           # the middle of each span cell: mm from the root along y in the wing, and on along the span line in the winglet
           "out": [SPAN * (j + 0.5) / SPAN_CELLS for j in range(SPAN_CELLS)] + [SPAN + (inner + outer) / 2 for inner, outer in zip(outs, outs[1:])]}
    return record, lay


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
    return {"total": LOAD, "unit": "N", "how": f"Pushed up at the {len(SPARS) * ribs} points where the {len(SPARS)} spars meet the upper skin at the wing's {ribs} ribs "
                                               "outboard of the root, the tip rib the last of them, in equal shares; none on the winglet; the root is held."}


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


def turned(a: Vector, b: Vector) -> float:
    """The angle between two directions, in radians."""
    across = cross(a, b)
    return math.atan2(math.sqrt(dot(across, across)), dot(a, b))


def shell_model(record: dict, lay: dict) -> dict:
    """The stored faces as the model that is solved: a node in the middle of every edge, one shared by the faces on that edge (the
    corners keep their numbers); the faces by section, one for each direction a part's faces look in, with the axes of each of its
    ply angles (1 along the fibres: the face's axis, laid on the face, turned by the angle about the normal; 2 across them, in the
    face); the root's nodes; and the loaded ones, where the upper skin, a spar and a rib of the wing outboard of the root meet. A
    face joins the first section of its part whose normal and whose axis, laid on the face, are both within SAME_WAY of its own:
    the corners are stored rounded, so the faces of one flat strip look in directions a little apart, and `off_axes` is the most
    any face is turned from its section's axes. A face's normal is that of the plane of its diagonals. In the winglet's bend a face
    is twisted and has that plane only on average: `bend_warp` is the most one leaves it, and `bend_turn` the most its surface at a
    corner is turned from it, so from the ply axes laid on it."""
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
    off_axes = warp = bend_warp = bend_turn = 0.0
    for element, corners in enumerate(mesh["quads"]):
        p = [nodes[n] for n in corners]
        normal = cross(tuple(p[2][i] - p[0][i] for i in range(3)), tuple(p[3][i] - p[1][i] for i in range(3)))
        size = math.sqrt(dot(normal, normal))
        normal = tuple(value / size for value in normal)
        areas.append(size / 2)  # a flat four-sided face: half the cross product of its diagonals
        leaves = abs(dot(normal, tuple(p[1][i] - p[0][i] for i in range(3)))) / math.sqrt(size / 2)  # how far a corner leaves the plane of the diagonals, over the face's size
        entry = parts[mesh["part"][element]]
        if lay["bend"][element]:
            if leaves > FLAT_BEND:
                raise SystemExit(f"face {element} of {entry['name']}, in the bend, is twisted more than allowed ({leaves:.2g} of its size out of plane)")
            bend_warp = max(bend_warp, leaves)
            for corner in range(4):  # the surface at a corner lies in the plane of the two edges that meet there
                here = cross(tuple(p[(corner + 1) % 4][i] - p[corner][i] for i in range(3)), tuple(p[corner - 1][i] - p[corner][i] for i in range(3)))
                bend_turn = max(bend_turn, turned(here, normal))
        else:
            if leaves > FLAT:
                raise SystemExit(f"face {element} is not flat ({leaves:.2g} of its size out of plane): its plies' axes would not lie in it")
            warp = max(warp, leaves)
        named = lay["axis"][element]
        lean = dot(named, normal)
        if abs(lean) > LEAN:
            raise SystemExit(f"face {element} of {entry['name']} is too far from the axis its angles are counted from to lay it on the face")
        axis = tuple((named[i] - lean * normal[i]) / math.sqrt(1 - lean * lean) for i in range(3))  # the named axis laid on the face
        home = next((number for number, other in enumerate(sections) if other["part"] == entry["id"] and dot(normal, other["normal"]) >= math.cos(SAME_WAY)
                     and dot(axis, other["axis"]) >= math.cos(SAME_WAY)), None)
        if home is None:
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
        off_axes = max(off_axes, turned(normal, sections[home]["normal"]), turned(axis, sections[home]["axis"]))

    owners: dict[int, set[str]] = {}
    for element, corners in enumerate(mesh["quads"]):
        for n in corners:
            owners.setdefault(n, set()).add(parts[mesh["part"][element]]["id"])
    loaded = sorted(n for n, names in owners.items() if {"upper-skin", "ribs"} <= names and names & set(SPARS) and 0 < nodes[n][1] <= record["wing"]["span"])
    stations = len(record["wing"]["ribs"]) - 1
    if len(loaded) != len(SPARS) * stations:
        raise SystemExit(f"{len(loaded)} points where a spar, a rib of the wing outboard of the root and the upper skin meet, not {len(SPARS) * stations}")
    return {"nodes": nodes, "elements": elements, "sections": sections, "section_of": section_of, "areas": areas, "off_axes": off_axes, "warp": warp,
            "bend_warp": bend_warp, "bend_turn": bend_turn, "root": [n for n, place in enumerate(nodes) if place[1] == 0.0], "loaded": loaded}


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


def solve(record: dict, lay: dict, keep: Path | None) -> dict:
    """Solves the wing and returns what is recorded of the answer: the load, the field, the stored nodes' displacements and the
    solve's numbers. Prints the checks."""
    ply = lamina()
    model = shell_model(record, lay)
    with tempfile.TemporaryDirectory() as scratch:
        folder = Path(scratch) if keep is None else keep
        folder.mkdir(parents=True, exist_ok=True)
        version, seconds, dat = run_ccx(deck(model, ply), folder)
    blocks = read_dat(dat)
    mesh, parts, sections, section_of = record["mesh"], record["parts"], model["sections"], model["section_of"]
    span = record["wing"]["span"]
    count = len(mesh["quads"])
    if len(blocks.get("total", [])) != 1 or len(blocks.get("displacements", [])) != len(model["nodes"]):
        raise SystemExit("CalculiX's .dat does not hold the root's total force and every node's displacement")

    # Each ply's stress in its own axes at each of its integration points, from CalculiX's global stress (sxx, syy, szz, sxy, sxz, syz).
    def resolved(a: Vector, b: Vector) -> tuple[float, ...]:
        return (a[0] * b[0], a[1] * b[1], a[2] * b[2], a[0] * b[1] + a[1] * b[0], a[0] * b[2] + a[2] * b[0], a[1] * b[2] + a[2] * b[1])

    axes = [[(resolved(along, along), resolved(across, across), resolved(along, across)) for along, across in (section["frames"][angle] for angle in section["angles"])]
            for section in sections]
    worst: list[tuple[float, str, int]] = [(0.0, "", 0)] * count  # the index, its mode and its ply (from 0)
    # syy summed over a face's integration points; the upward stress on a cut across the face's span line (syz in the wing, where
    # that line is y); and their number
    spanwise, lifting, points = [0.0] * count, [0.0] * count, [0] * count
    for row in blocks.get("stresses", []):
        element, point, stress = int(row[0]) - 1, int(row[1]) - 1, row[2:8]
        layer = point // POINTS_A_PLY
        value, mode = strength_used(tuple(sum(c * s for c, s in zip(axis, stress)) for axis in axes[section_of[element]][layer]), ply)
        worst[element] = max(worst[element], (value, mode, layer))
        spanwise[element] += stress[1]
        lifting[element] += stress[5] * lay["axis"][element][1] + stress[2] * lay["axis"][element][2]
        points[element] += 1
    for element in range(count):
        expected = POINTS_A_PLY * len(sections[section_of[element]]["angles"])
        if points[element] != expected:
            raise SystemExit(f"CalculiX printed {points[element]} integration points for face {element}, not {expected}")
        spanwise[element] /= expected  # the plies are one thickness, so the mean over the points is the mean through the laminate
        lifting[element] /= expected

    # The vertical force each span cell carries across its section, from the solver's stresses: the mean upward stress of a face
    # on a cut across its span line times its section (its area by its thickness over its length along that line). Between two
    # ribs of the wing it is the load outboard of the cell; in the winglet, which carries no load, it should be nothing.
    carried: dict[int, float] = {}
    for element, corners in enumerate(mesh["quads"]):
        cell = lay["cell"][element]
        if cell is not None:  # a rib lies in a section and carries nothing across it
            along = [dot(lay["axis"][element], model["nodes"][n]) for n in corners]
            thickness = ply["thickness"] * len(sections[section_of[element]]["angles"])
            carried[cell] = carried.get(cell, 0.0) + lifting[element] * model["areas"][element] * thickness / (max(along) - min(along))
    share = LOAD / len(model["loaded"])
    out = lay["out"]  # the middle of each cell: mm from the root along y in the wing, and on along the span line in the winglet
    wing_cells = [cell for cell in sorted(carried) if out[cell] < span]
    winglet_cells = [cell for cell in sorted(carried) if out[cell] > span]
    outboard = {cell: sum(share for n in model["loaded"] if model["nodes"][n][1] > out[cell]) for cell in carried}
    beside_root = wing_cells[0]

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
            "tip_rib_deflection": round(max(moved[n][2] for n in range(len(mesh["nodes"])) if mesh["nodes"][n][1] == span), 2),
            "parts": [{"id": part["id"], "max": values[element], "at": round(centre[element], 1)} for part, element in zip(parts, largest)],
            "governing": {"part": entry["id"], "value": values[governs], "at": round(centre[governs], 1), "ply": layer + 1, "angle": entry["angles"][layer], "mode": mode},
        },
    }

    # The checks, printed with every solve.
    print(f"solved by CalculiX {version} in {seconds:.1f} s: {len(model['nodes'])} nodes, {count} elements, {len(sections)} sections; a face is turned at most "
          f"{math.degrees(model['off_axes']):.4f} degrees from its section's ply axes; outside the winglet's bend a face leaves its own plane by at most "
          f"{model['warp']:.1g} of its size")
    print(f"  the bend: its {sum(lay['bend'])} faces are twisted, each with a section of its own: one leaves the plane of its diagonals by at most "
          f"{model['bend_warp']:.3f} of its size, and its surface at a corner is turned at most {math.degrees(model['bend_turn']):.2f} degrees from the ply axes laid on that plane")
    print("  the ply: " + ", ".join(f"{name} {ply[name]:.6g}" for name in ("E1", "E2", "E3", "G12", "G13", "G23", "F1t", "F1c", "F2t", "F2c", "F6")) + " MPa; "
          + ", ".join(f"{name} {ply[name]:g}" for name in ("nu12", "nu13", "nu23")) + f"; ply thickness {ply['thickness']:.5g} mm")
    for source in ply["sources"]:
        print(f"    {source}")
    off = max(wing_cells, key=lambda cell: abs(carried[cell] - outboard[cell]))
    print(f"  1 balance: the span cell beside the root carries {carried[beside_root]:.3f} N to it, summed from the solver's stresses, against {LOAD} N applied, "
          f"a difference of {carried[beside_root] - LOAD:+.3f} N; of the wing's {len(wing_cells)} cells the one {out[off]:.1f} mm out is furthest from the load outboard of it, "
          f"{carried[off]:.3f} N against {outboard[off]:.3f} N")
    print(f"    CalculiX's own total of the reactions printed for the root's nodes is {-blocks['total'][0][2]:.3f} N and is not used: on shell nodes whose rotations "
          f"are held it is not the whole reaction (fea/checks/calculix-conventions.toml, shell_set_totals)")
    # Near the root, clear of the held edge: the skins' faces between the spars in the second span cell, at the local chord.
    near = out[wing_cells[1]]
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
    stored = range(len(mesh["nodes"]))
    top = max(stored, key=lambda n: moved[n][2])
    tip_rib = [n for n in stored if mesh["nodes"][n][1] == span]
    wing_tip = max(tip_rib, key=lambda n: moved[n][2])
    place = "on the winglet" if mesh["nodes"][top][1] > span else "on the wing"
    print(f"  4 deflection: the largest rise is {rise:.2f} mm, {100 * rise / span:.2f} % of the span to the tip rib; of the stored nodes the highest riser is {place}, at "
          f"x {mesh['nodes'][top][0]:.1f}, y {mesh['nodes'][top][1]:.1f}, z {mesh['nodes'][top][2]:.1f} mm ({moved[top][2]:.2f} mm); the tip rib rises {moved[wing_tip][2]:.2f} mm at most "
          f"and {min(moved[n][2] for n in tip_rib):.2f} mm at least")
    idle = max(winglet_cells, key=lambda cell: abs(carried[cell]))
    winglet = [element for element in range(count) if min(mesh["nodes"][n][1] for n in mesh["quads"][element]) >= span and centre[element] > span]
    busiest = max(winglet, key=values.__getitem__)
    print(f"  5 the winglet: no load lies on it, and of its {len(winglet_cells)} cells the one {out[idle] - span:.1f} mm out along the span line from the tip rib carries the "
          f"most upward force across it, {carried[idle]:+.3f} N; its largest strength used is {values[busiest]:.4g}, in the {parts[mesh['part'][busiest]]['name'].lower()} "
          f"{centre[busiest] - span:.1f} mm outboard of the tip rib, ply {worst[busiest][2] + 1} in {worst[busiest][1]}")
    for part, element in zip(parts, largest):
        print(f"  {part['name']}: strength used at most {values[element]:.4g}, {centre[element]:.1f} mm from the root")
    print(f"  governing: {entry['name']}, {values[governs]:.4g} of its strength used {centre[governs]:.1f} mm from the root, ply {layer + 1} ({entry['angles'][layer]} degrees) in {mode}")
    return answer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--solve", action="store_true", help="also solve the wing with CalculiX and record the answer")
    parser.add_argument("--keep", type=Path, metavar="FOLDER", help="with --solve: keep the deck and the solver's files in this folder")
    args = parser.parse_args()
    record, lay = build()
    record["built"] = datetime.date.today().isoformat()
    if args.solve:
        record.update(solve(record, lay, args.keep))
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
    winglet = record["wing"]["winglet"]
    beyond = sum(1 for corners in mesh["quads"] if max(mesh["nodes"][n][1] for n in corners) > SPAN)
    print(f"  the winglet: {sum(1 for place in mesh['nodes'] if place[1] > SPAN)} of the nodes and {beyond} of the faces lie outboard of the tip rib; its tip stands "
          f"{winglet['rise']} mm up and {winglet['reach']} mm out, its leading edge {winglet['sweep']:g} mm aft of the wing tip's")
    low, high = ([edge(place[axis] for place in mesh["nodes"]) for axis in range(3)] for edge in (min, max))
    print(f"  the mesh fills x {low[0]:g} to {high[0]:g}, y {low[1]:g} to {high[1]:g}, z {low[2]:g} to {high[2]:g} mm")


if __name__ == "__main__":
    main()
