"""The rebuild guide of a model comparison document: how to recreate the model, step by step, in Abaqus/CAE and in PrePoMax.

Follows the structure of the team's FEA model report template (local copy under `.local/fea/<coupon>/from-team/<date>/template/`, 2026-10-18):
document control, evidence tags, a summary card, then one section per modelling step with a settings table, the GUI steps
for both tools, and the input-file keywords. Every value carries an evidence tag; a value that cannot carry one is written
[OPEN], never filled in from memory (the template's rule for authors). The PrePoMax steps cite the page of the PrePoMax 2.6.0
manual (prepomax.fs.um.si, September 2026) they come from.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from anisotropy_fea.model import Deck
from anisotropy_fea.report import ModelFacts
from anisotropy_fea.units import from_si

# Evidence tags, in the template's words.
TAGS = [
    ("INP", "Read directly from the input deck the kernel solved. Highest confidence."),
    ("INP-derived", "Computed from the deck's data (node coordinates, set membership) by `anisotropy\\_fea.report.model\\_facts`. Reproducible by script."),
    ("SPEC", "Stated in the spec the decks were generated from (ADR-0030); the generator wrote it into the deck."),
    ("CALC", "Calculated by the generator outside the solver (a hash, a nominal strain, a ply fraction). The method is shown."),
    ("CAE-CHECK", "An Abaqus/CAE click path or setting that the deck does not store. Confirm it in Abaqus/CAE before release."),
    ("MANUAL p.N", "A PrePoMax click path quoted from page N of the PrePoMax 2.6.0 manual. Not stored in any file of this model."),
    ("GUI-SEEN", "A PrePoMax step this project has performed on this model (the generated deck imported and run, the results opened)."),
    ("ASSUMED", "Not stated in the files. Written here so the reader can accept or reject it."),
    ("OPEN", "Information is missing. Not filled in from memory."),
]
PREPOMAX_MANUAL = "PrePoMax 2.6.0 manual, v1.0.0, 6 September 2026 (prepomax.fs.um.si/documentation)"


@dataclass(frozen=True)
class Helpers:
    """The LaTeX helpers of docs/models/build.py, passed in so this module does not import the build script."""

    escape: Callable[[str], str]
    code: Callable[[str], str]
    inline: Callable[[str], str]
    number: Callable[..., str]
    heading: Callable[[int, str], str]
    kv_table: Callable[..., str]
    long_table: Callable[..., str]
    listing_text: Callable[[str], str]
    tools: tuple[str, ...] = ("Abaqus/CAE", "PrePoMax 2.6")  # the GUIs whose steps are written; the coupon document asks for Abaqus/CAE only


@dataclass(frozen=True)
class Context:
    facts: ModelFacts
    deck: Deck
    units: str
    kernel_deck: Path
    reference_deck: Path
    kernel_sha256: str
    reference_sha256: str
    solver_name: str  # calculix | abaqus
    spec_path: Path | None
    spec_material_lines: tuple[str, ...]  # the citation lines of a library material, or ()
    spec_material_source: str | None
    spec_transverse: str | None  # the spec's out-of-plane statement, or None
    record_title: str
    report_date: str


def tag(name: str) -> str:
    return r"\evidence{" + name + "}"


def keyword_blocks(path: Path, keyword: str, data_lines: int | None = 12, first_only: bool = False) -> list[str]:
    """The deck's lines for a keyword (case-insensitive) with up to `data_lines` data lines each; comments skipped."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    blocks, i = [], 0
    pattern = re.compile(r"^\*" + re.escape(keyword) + r"\b", re.I)
    while i < len(lines):
        if pattern.match(lines[i].strip()):
            block = [lines[i].rstrip()]
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("*"):
                if not lines[j].strip().startswith("**") and lines[j].strip():
                    block.append(lines[j].rstrip())
                j += 1
            data = block[1:]
            if data_lines is not None and len(data) > data_lines:
                data = data[:data_lines] + [f"... ({len(block) - 1 - data_lines} more lines)"]
            blocks.append("\n".join([block[0], *data]))
            if first_only:
                return blocks
            i = j
        else:
            i += 1
    return blocks


def keyword_box(h: Helpers, title: str, text: str) -> str:
    return (rf"\par\smallskip\noindent{{\sffamily\footnotesize\color{{muted}}Input-file keywords: \textcolor{{ink}}{{{h.escape(title)}}}}}\par\nopagebreak"
            + "\n" + r"\begin{plainfile}" + "\n" + h.listing_text(text) + "\n" + r"\end{plainfile}")


def gui_steps(h: Helpers, tool: str, steps: list[str], tag_name: str) -> str:
    if tool not in h.tools:
        return ""
    return (rf"\textbf{{{h.escape(tool)}}} {tag(tag_name)}" + "\n" + r"\begin{enumerate}" + "\n"
            + "\n".join(r"\item " + step for step in steps) + "\n" + r"\end{enumerate}")


def partition_steps(h: Helpers, f: ModelFacts, length: Callable[[float], float], L: str) -> list[str]:
    """The Abaqus/CAE steps that cut the coupon face at the partition lines, with the points to type in the sketcher.

    A sketch on a face measures from the centre of that face, not from the part origin (seen in the founder's Abaqus/CAE
    session on 2026-10-21: the sketch axis ran through the middle of the coupon), so every point is shifted by the centre.
    The step tells the reader how to confirm the origin before typing, and gives a datum-plane route that needs no shift.
    """
    e = h.escape
    inner = [length(v) for v in f.partition_lines_y[1:-1]]
    if not inner:
        return [e("No partition: the deck has no inner partition line, so the part stays one face.")]
    x0, x1 = (length(v) for v in f.extent_x)
    y0, y1 = (length(v) for v in f.extent_y)
    xc, yc = (x0 + x1) / 2, (y0 + y1) / 2
    g = lambda v: f"{round(v, 9) + 0.0:g}"  # noqa: E731  (+ 0.0 turns -0.0 into 0)
    m = lambda v: g(v).replace("-", "−")  # noqa: E731  a minus sign in the prose; the typed points keep the hyphen
    typed = lambda text: r"\texttt{" + e(text) + "}"  # noqa: E731
    rows = "\n".join(rf"{g(y)} & {typed(f'{g(x0 - xc)},{g(y - yc)}')} & {typed(f'{g(x1 - xc)},{g(y - yc)}')} \\" for y in inner)
    table = (r"\par\smallskip{\small\begin{tabular}{lll}\toprule" + "\n"
             + rf"\textbf{{Part y ({e(L)})}} & \textbf{{Start point}} & \textbf{{End point}} \\ \midrule" + "\n"
             + rows + "\n" + r"\bottomrule\end{tabular}}")
    lines_text = ", ".join(g(y) for y in inner)
    return [
        e("Tools > Partition > Face > Sketch. If asked, pick the coupon face and click Done."),
        e(f"At “Select an edge or axis that will appear”, keep “vertical and on the right” and click the right long edge (x = {m(x1)}). "
          "The coupon then stands upright in the sketcher: sketch x runs along part x, sketch y along part y."),
        e(f"The sketcher measures from the centre of the face, ({m(xc)}, {m(yc)}), not from the part origin: sketch x = part x − {m(xc)}, "
          f"sketch y = part y − {m(yc)}. Check it first: hold the pointer on the bottom-left corner of the coupon; the readout at the "
          f"top left of the viewport shows x {m(x0 - xc)}, y {m(y0 - yc)}. If it shows 0, 0, type the part coordinates instead: "
          f"({m(x0)}, y) and ({m(x1)}, y)."),
        e(f"Draw one line across the full width at each partition line (y = {lines_text} {L}) with Create Lines: Connected: type the "
          "start point, Enter, the end point, Enter, then end the line (middle mouse button or Esc) so that the next line does not "
          "join it. The points, in sketch coordinates:") + "\n" + table,
        e(f"Click Done in the prompt area. The part now has {len(inner) + 1} faces, one per row of “Regions by element label” above."),
        e(f"Alternative without sketch coordinates: Tools > Datum > Plane > Offset From Principal Plane > XZ Plane, one plane at each "
          f"offset {lines_text} {L}. Then Tools > Partition > Face > Use Datum Plane: pick the face the plane crosses, pick the plane, "
          "Create Partition; repeat for each plane."),
    ]


def render(ctx: Context, h: Helpers) -> str:
    """The rebuild guide as LaTeX, to be placed as one section of the document (subsections inside)."""
    f, units = ctx.facts, ctx.units
    L = {"mm-MPa": "mm", "m-Pa": "m"}[units]
    S = {"mm-MPa": "MPa", "m-Pa": "Pa"}[units]
    length = lambda v: from_si(v, "length", units)  # noqa: E731
    stress = lambda v: from_si(v, "stress", units)  # noqa: E731
    n = lambda v, d=6: h.number(v, d)  # noqa: E731
    e = h.escape
    out: list[str] = []
    open_items: list[str] = []
    generated = ctx.spec_path is not None
    abaqus_ref = ctx.solver_name == "abaqus"

    # ---------------------------------------------------------------- document control and tags
    out.append("This guide is written so that an engineer can rebuild the model by hand in " + " or in ".join(h.tools) + " and get the same deck. "
               "It follows the team's FEA model report template: each step has a settings table, the GUI steps, and the "
               "input-file keywords the deck holds. Every value carries an evidence tag; a value that cannot is written "
               + tag("OPEN") + " and listed at the end.")
    out.append(h.heading(1, "Document control"))
    heading_lines = [line.strip() for line in ctx.deck.heading.splitlines() if line.strip()] if ctx.deck.heading else []
    # Abaqus/CAE writes the job and model names as comments under *Heading; the reader keeps only the heading's text lines
    comments = [line.strip()[2:].strip() for line in ctx.kernel_deck.read_text(encoding="utf-8", errors="replace").splitlines()[:40] if line.strip().startswith("**")]
    cae_job = next((c for c in comments if "job name" in c.lower()), None)
    cae_tool = next((c for c in comments if c.lower().startswith("generated by")), None)
    if heading_lines:
        job = e(heading_lines[0]) + " " + tag("INP")
    elif cae_job:
        job = e(cae_job) + " " + tag("INP") + " (heading comment)"
    elif generated:
        job = e(f"no CAE job: the deck {ctx.kernel_deck.name} is generated from the spec, and its file name is the job name") + " " + tag("SPEC")
    else:
        job = e("not stated in the deck") + " " + tag("OPEN")
        open_items.append("Model and job name.")
    control = [
        ("Model / job", job),
        ("Generated by", (e("anisotropy_fea from the spec " + ctx.spec_path.name) + " " + tag("SPEC")) if generated
         else ((e(cae_tool) + " " + tag("INP") + " (heading comment)") if cae_tool else (e("not stated") + " " + tag("OPEN")))),
        ("Kernel deck", h.code(ctx.kernel_deck.name) + ", SHA-256 " + h.code(ctx.kernel_sha256) + " " + tag("CALC")),
        ("Reference deck", (h.code(ctx.reference_deck.name) + ", SHA-256 " + h.code(ctx.reference_sha256) + " " + tag("CALC"))
         if ctx.reference_deck != ctx.kernel_deck else "the same deck " + tag("INP")),
        ("Source CAE file", ("none: the deck is generated, not drawn " + tag("SPEC")) if generated else ("not supplied; the GUI steps below are therefore " + tag("CAE-CHECK"))),
        ("Unit system", (e(f"{units}: stated in the spec and written in the deck header") + " " + tag("SPEC")) if generated
         else (e(f"{units}: not stored by Abaqus; stated by the person who read the deck (ADR-0002)") + " " + tag("ASSUMED"))),
        ("Report date", e(ctx.report_date) + " " + tag("CALC")),
        ("Author / reviewer", tag("OPEN") + " / " + tag("OPEN")),
    ]
    if not generated:
        open_items.append("Source CAE file: not supplied, so every Abaqus/CAE click path is CAE-CHECK.")
        open_items.append("Unit system: assumed, not stored in the deck.")
    open_items.append("Author and reviewer names.")
    out.append(h.kv_table(control))
    out.append(h.heading(1, "Evidence tags"))
    out.append(h.long_table(["Tag", "Meaning"], [rf"{tag(name)} & {h.inline(meaning)} \\" for name, meaning in TAGS], r"lY", r"\small"))
    out.append("Rule for authors: a value is never written unless it can carry one of these tags. If it cannot, write " + tag("OPEN") + ".")

    # ---------------------------------------------------------------- summary card
    out.append(h.heading(1, "Model summary card"))
    (part_name, n_nodes, n_elements, element_type) = f.parts[0]
    section = f.sections[0] if f.sections else None
    width = length(f.extent_x[1] - f.extent_x[0])
    total_length = length(f.extent_y[1] - f.extent_y[0])
    free = (length(f.partition_lines_y[-2] - f.partition_lines_y[1]) if len(f.partition_lines_y) >= 3 else None)
    pull = next((length(b.value) for b in f.boundaries if b.dof_first <= 2 <= b.dof_last and b.value), None)
    load_total = sum(l.value for l in f.loads if l.dof == 2)
    grips = ("two reference points, each kinematically coupled to a grip node set" if f.couplings
             else "direct constraints on the grip node sets (no reference points)")
    materials = ", ".join(f"{name} ({m.elastic.kind})" for name, m in ctx.deck.materials.items() if m.elastic)
    layup = (f"[{'/'.join(f'{p.angle_deg:g}' for p in section.listed)}]" + ("s" if section.symmetric else "")
             + f", {len(section.expanded)} plies x {length(section.expanded[0].thickness_m):g} = {length(section.total_thickness_m):g} {L}"
             + f", {section.expanded[0].integration_points} integration points per ply") if section else "no shell section"
    card = [
        ("Purpose", e(f"Linear-elastic response of a {width:g} {L} by {total_length:g} {L} composite coupon with gripped end zones") + " " + tag("INP-derived")),
        ("Analysis", e(f"Static, general, one step ({f.step[0]}), geometric nonlinearity {'ON' if f.step[1] else 'OFF'}") + " " + tag("INP")),
        ("Unit system", e(units) + " " + tag("SPEC" if generated else "ASSUMED")),
        ("Geometry", e(f"Planar deformable shell, x = {length(f.extent_x[0]):g} to {length(f.extent_x[1]):g}, y = {length(f.extent_y[0]):g} to {length(f.extent_y[1]):g}, z = 0") + " " + tag("INP")),
        ("Material", e(materials) + " " + tag("INP")),
        ("Layup", e(layup) + " " + tag("INP")),
        ("Element / mesh", e(f"{element_type}, {n_elements} elements, {n_nodes} nodes, edge lengths {length(f.edge_length_range[0]):.4g} to {length(f.edge_length_range[1]):.4g} {L}") + " " + tag("INP-derived")),
        ("Grips", e(grips) + " " + tag("INP")),
        ("Free length", (e(f"{free:g} {L} (y = {length(f.partition_lines_y[1]):g} to {length(f.partition_lines_y[-2]):g})") + " " + tag("INP-derived")) if free is not None else tag("OPEN")),
        ("Loading", (e(f"prescribed displacement {pull:g} {L} along y at the top grip") + " " + tag("INP")) if pull is not None
         else (e(f"concentrated loads along y summing to {load_total:g} N") + " " + tag("INP")) if load_total else tag("OPEN")),
        ("Damage / failure model", e("none in the deck; first-ply failure is computed afterwards by the kernel from *Fail Stress" if any(m.fail_stress for m in ctx.deck.materials.values()) else "none") + " " + tag("INP")),
    ]
    out.append(h.kv_table(card))

    # ---------------------------------------------------------------- part geometry
    out.append(h.heading(1, "Part geometry"))
    out.append(r"\textbf{Purpose.} Define the coupon outline and the partition lines that separate the gripped zones from the free length.")
    lines_text = ", ".join(f"{length(v):g}" for v in f.partition_lines_y[1:-1]) or "none"
    bands = "; ".join(f"{a}--{b}: y {length(y0):g} to {length(y1):g} {L} ({count} elements)" for y0, y1, count, a, b in f.element_bands)
    out.append(h.kv_table([
        ("Part name", e(part_name) + " " + tag("INP")),
        ("Type", e("3D, deformable, planar shell (every node has z = 0)") + " " + tag("INP") + "; the modelling-space choice in the GUI " + tag("CAE-CHECK")),
        ("Extent", e(f"width (x) {width:g} {L}, length (y) {total_length:g} {L}") + " " + tag("INP")),
        ("Load axis", e("global y (dof 2 is prescribed or loaded)") + " " + tag("INP")),
        ("Partition lines (y)", e(f"{lines_text} {L}: the inner edges of the gripped node groups and every y where the node-row spacing changes") + " " + tag("INP-derived")),
        ("Regions by element label", e(bands) + " " + tag("INP-derived")),
    ]))
    out.append(gui_steps(h, "Abaqus/CAE", [
        e(f"Part module > Create Part. Name {part_name}, 3D, Deformable, Shell, Planar, approximate size {2 * total_length:g}."),
        e(f"Sketch a rectangle with corners ({length(f.extent_x[0]):g}, {length(f.extent_y[0]):g}) and ({length(f.extent_x[1]):g}, {length(f.extent_y[1]):g}); Done."),
        *partition_steps(h, f, length, L),
    ], "CAE-CHECK"))
    out.append(gui_steps(h, "PrePoMax 2.6", [
        e("File > New: model space 3D, unit system mm, ton, s, °C (the mm-MPa system of the deck). ") + tag("MANUAL p.8"),
        e("PrePoMax has no sketcher: a part comes from a CAD file (File > Import: STEP, IGES, B-rep, STL) or from a mesh file (.inp, .unv, .vol). ") + tag("MANUAL p.9")
        + e(" Route A, the one this project uses: File > Import the CalculiX deck of this model; the mesh, sets, material, section, boundary conditions and step come with it. ") + tag("GUI-SEEN"),
        e(f"Route B, geometry by hand: draw the {width:g} by {total_length:g} {L} rectangle as a surface in a CAD tool, split it at y = {lines_text} {L} (Geometry > CAD Part > Split a Face Using Two Points, or split in CAD), export STEP and File > Import it. ") + tag("MANUAL p.17"),
    ], "MANUAL"))
    out.append(keyword_box(h, ctx.kernel_deck.name, "\n".join(keyword_blocks(ctx.kernel_deck, "Part", 0) + keyword_blocks(ctx.kernel_deck, "Node", 3, first_only=True)
                                                        + keyword_blocks(ctx.kernel_deck, "Element", 3, first_only=True))))

    # ---------------------------------------------------------------- material
    out.append(h.heading(1, "Material"))
    out.append(r"\textbf{Purpose.} Provide the lamina stiffness (and strengths) used by every ply.")
    for name, material in ctx.deck.materials.items():
        if material.elastic is None:
            continue
        el = material.elastic
        constants = [("E1", el.E1, "stress"), ("E2", el.E2, "stress"), ("nu12", el.nu12, ""), ("G12", el.G12, "stress")]
        if el.G13 is not None:
            constants += [("G13", el.G13, "stress"), ("G23", el.G23, "stress")]
        rows = [rf"{e(name)}: {lbl} & {n(stress(val) if kind == 'stress' else val)} {e(S) if kind == 'stress' else ''} & {tag('INP')} \\"
                for lbl, val, kind in constants]
        if material.fail_stress:
            fs = material.fail_stress
            rows += [rf"{e(name)}: {lbl} & {n(stress(val))} {e(S)} & {tag('INP')} \\" for lbl, val in (("Xt", fs.Xt), ("Xc", fs.Xc), ("Yt", fs.Yt), ("Yc", fs.Yc), ("S", fs.S))]
            if fs.f_star is not None:
                rows.append(rf"{e(name)}: f* (Tsai-Wu interaction) & {n(fs.f_star)} & {tag('INP')} \\")
        if generated and ctx.spec_material_source:
            rows.append(rf"Origin of values & {e(ctx.spec_material_source)} & {tag('SPEC')} \\")
            for line in ctx.spec_material_lines:
                text, _, url = line.partition(": http")
                url = "http" + url if url else ""
                safe = url.replace("%", r"\%").replace("#", r"\#")  # neither % nor # may appear raw inside a tabularx body
                cite = h.inline(text) + (rf": \href{{{safe}}}{{{h.code(url)}}}" if url else "")  # a breakable, clickable URL
                rows.append(rf"\quad citation & {cite} & {tag('SPEC')} \\")
        else:
            rows.append(rf"Origin of values (datasheet, test, supplier) & not stated in the deck & {tag('OPEN')} \\")
            open_items.append(f"Origin of the material values of {name}.")
        if ctx.spec_transverse:
            rows.append(rf"Out-of-plane constants for CalculiX & {e(ctx.spec_transverse)} & {tag('SPEC')} \\")
        out.append(h.long_table(["Constant", "Value", "Source"], rows, r"lYl", r"\small"))
        if el.kind == "LAMINA" and abs(el.E1 - el.E2) < 1e-9 * el.E1:
            out.append(r"\textbf{Note.} $E_1 = E_2$: this lamina behaves like a balanced fabric, not like a unidirectional tape. State the material form in the final report. " + tag("CALC"))
    out.append(gui_steps(h, "Abaqus/CAE", [
        e("Property module > Create Material, enter the name > Mechanical > Elasticity > Elastic, Type Lamina, one row: E1, E2, Nu12, G12, G13, G23 in the order of the table."),
        e("Mechanical > Damage for Fiber-Reinforced Composites is NOT used; the strengths go to Fail Stress: Mechanical > Elasticity > Elastic > Suboptions > Fail Stress, one row Xt, Xc, Yt, Yc, S, and the sixth value f* (write 0 explicitly; ADR-0021 never assumes it).")
        if any(m.fail_stress for m in ctx.deck.materials.values()) else e("No strengths are in the deck."),
    ], "CAE-CHECK"))
    out.append(gui_steps(h, "PrePoMax 2.6", [
        e("Property > Material > Create offers Density, Elasticity (Young's modulus and Poisson's ratio only), Plasticity and thermal properties: no orthotropic or lamina type in the dialog. ") + tag("MANUAL p.30"),
        e("Route A: the imported CalculiX deck carries *ELASTIC, TYPE=ENGINEERING CONSTANTS and the material appears in the model tree. ") + tag("GUI-SEEN"),
        e("Route B: Model > Edit CalculiX Keywords, add the *MATERIAL and *ELASTIC, TYPE=ENGINEERING CONSTANTS block quoted below (nine constants and a temperature on two lines), or Property > Material > Import from .inp with the CalculiX deck. ") + tag("MANUAL p.23") + " " + tag("MANUAL p.30"),
    ], "MANUAL"))
    out.append(keyword_box(h, ctx.kernel_deck.name, "\n".join(keyword_blocks(ctx.kernel_deck, "Material") + keyword_blocks(ctx.kernel_deck, "Elastic") + keyword_blocks(ctx.kernel_deck, "Fail Stress"))))
    if ctx.reference_deck != ctx.kernel_deck:
        out.append(keyword_box(h, ctx.reference_deck.name + " (CalculiX)", "\n".join(keyword_blocks(ctx.reference_deck, "Material") + keyword_blocks(ctx.reference_deck, "Elastic"))))

    # ---------------------------------------------------------------- layup
    if section is not None:
        out.append(h.heading(1, "Composite layup"))
        out.append(r"\textbf{Purpose.} Define ply thickness, material, angle and stacking for the whole part.")
        axes = (f"axis a = {section.orientation_axes[0]}, axis b = {section.orientation_axes[1]}, rotation about axis {section.orientation_rotation[0]} = {section.orientation_rotation[1]:g} degrees"
                if section.orientation_axes else "global axes (no *Orientation)")
        out.append(h.kv_table([
            ("Layup name", e(section.layup_name or "none in the deck") + " " + tag("INP")),
            ("Element type", e("conventional shell (*Shell Section, composite); continuum shell is NOT used") + " " + tag("INP")),
            ("Symmetric flag", (e("yes: the listed plies are the lower half, mirrored above the midplane") if section.symmetric else e("no: every ply is listed")) + " " + tag("INP")),
            ("Region", e(f"element set {section.elset}, {section.elements} elements") + " " + tag("INP")),
            ("Orientation", e(f"{section.orientation or 'none'}: {axes}. Local direction 1 is global x, ACROSS the width; a 0-degree ply has its fibres across the load") + " " + tag("INP")),
            ("Integration points per ply", e(str(section.expanded[0].integration_points)) + " " + tag("INP")),
            ("Section integration", e(section.section_integration or "default (Simpson)") + " " + (tag("INP") if section.section_integration else tag("ASSUMED"))),
        ]))
        out.append(h.heading(2, f"Ply table as entered ({len(section.listed)} rows)"))
        out.append(h.long_table(["Ply", "Material", f"Thickness ({L})", "Angle (deg)", "Int. points"],
                                [rf"{e(p.name or str(p.index))} & {e(p.material)} & {n(length(p.thickness_m))} & {p.angle_deg:g} & {p.integration_points} \\" for p in section.listed],
                                r"lYrrr", r"\small"))
        out.append("All values " + tag("INP") + ".")
        out.append(h.heading(2, f"Expanded stack ({len(section.expanded)} plies, bottom to top)"))
        out.append(h.long_table(["Ply", "Angle (deg)", f"t ({L})", f"z bottom ({L})", f"z top ({L})"],
                                [rf"{p.index} & {p.angle_deg:g} & {n(length(p.thickness_m))} & {n(length(p.z_bottom_m), 5)} & {n(length(p.z_top_m), 5)} \\" for p in section.expanded],
                                r"lrrrr", r"\small"))
        fractions = ", ".join(f"{angle:g} degrees {100 * count / len(section.expanded):.0f}% ({count} plies)" for angle, count in section.angle_fractions)
        mid = section.expanded[len(section.expanded) // 2 - 1], section.expanded[len(section.expanded) // 2]
        double = (f" Plies {mid[0].index} and {mid[1].index} are both {mid[0].angle_deg:g} degrees, forming a {length(mid[0].thickness_m + mid[1].thickness_m):g} {L} double layer at the midplane."
                  if section.symmetric and mid[0].angle_deg == mid[1].angle_deg else "")
        out.append(e(f"Expansion by mirroring and z from the midplane: ") + tag("CALC") + e(double) + " " + e(f"Ply fractions: {fractions}. Total thickness {length(section.total_thickness_m):g} {L}.") + " " + tag("CALC"))
        out.append(gui_steps(h, "Abaqus/CAE", [
            e(f"Property module > Composite Layup Manager > Create. Name {section.layup_name or 'Layup-1'}, Initial ply count {len(section.listed)}, Element type Conventional Shell."),
            e("Section tab: Section integration Simpson (the deck writes no override), Thickness integration points as the table, Poisson definition Default, Temperature Gradient, Density off; Offset Middle surface, Thickness Specify (per ply)."),
            e(f"Plies tab: one row per listed ply with Material, Thickness {length(section.listed[0].thickness_m):g}, CSys <Layup>, Rotation angle = the ply angle, Integration points {section.listed[0].integration_points}; "
              + ("tick the option that makes the calculated section symmetric. " if section.symmetric else "leave symmetric unticked. ")),
            e("Layup orientation: Definition Coordinate system, CSys Global (axis 1 along global x), Additional rotation None, Normal direction Axis 3. Region: the whole part (all faces)."),
        ], "CAE-CHECK"))
        out.append(gui_steps(h, "PrePoMax 2.6", [
            e("Property > Section > Create offers Solid, Shell (one material, one thickness, offset), Membrane, Point mass and Distributed mass sections: no composite layup dialog. ") + tag("MANUAL p.31"),
            e("Route A: the imported CalculiX deck carries *SHELL SECTION, ELSET=..., COMPOSITE with one line per ply (thickness, blank, material, orientation) and one *ORIENTATION per ply angle; PrePoMax keeps them and shows the part laminated. ") + tag("GUI-SEEN"),
            e("Route B: Model > Edit CalculiX Keywords, add the *ORIENTATION and *SHELL SECTION, COMPOSITE block quoted below after the material. The first layer line is the bottom ply (CalculiX convention, detected and recorded in the conventions file). ") + tag("MANUAL p.23"),
        ], "MANUAL"))
        out.append(keyword_box(h, ctx.kernel_deck.name, "\n".join(keyword_blocks(ctx.kernel_deck, "Orientation") + keyword_blocks(ctx.kernel_deck, "Shell Section", 20))))
        if ctx.reference_deck != ctx.kernel_deck:
            out.append(keyword_box(h, ctx.reference_deck.name + " (CalculiX)", "\n".join(keyword_blocks(ctx.reference_deck, "Orientation") + keyword_blocks(ctx.reference_deck, "Shell Section", 20))))

    # ---------------------------------------------------------------- assembly and sets
    out.append(h.heading(1, "Assembly, sets and reference points"))
    out.append(r"\textbf{Purpose.} Place the part, name the node and element groups the constraints and loads act on, and create the reference points that carry the grip motion.")
    rows = [rf"Instance & {e(f'{name} of part {part} at the origin, no rotation (dependent: the mesh lives in the part)')} & {tag('INP')} \\" for name, part in f.instances]
    for name, (x, y) in f.reference_nodes:
        rows.append(rf"Reference point & {e(f'{name} at ({length(x):g}, {length(y):g}, 0)')} & {tag('INP')} \\")
    used_sets = {b.target for b in f.boundaries} | {l.target for l in f.loads} | {s[2] for s in f.surfaces if s[1] == 'node'}
    for s in f.node_sets:
        where = (f"y = {length(s.y_range[0]):g}" if abs(s.y_range[1] - s.y_range[0]) < 1e-12 else f"y = {length(s.y_range[0]):g} to {length(s.y_range[1]):g}")
        use = "" if s.name in used_sets else "; not referenced by a boundary, load or coupling"
        rows.append(rf"Node set {e(s.name)} & {e(f'{s.count} nodes, {where} {L}{use}')} & {tag('INP-derived')} \\")
    for name, count, scope in f.element_sets:
        rows.append(rf"Element set {e(name)} & {e(f'{count} elements ({scope})')} & {tag('INP')} \\")
    for name, kind, names in f.surfaces:
        rows.append(rf"Surface {e(name)} & {e(f'{kind}-based, from {names}')} & {tag('INP')} \\")
    out.append(h.long_table(["Item", "Value", "Source"], rows, r"lYl", r"\small"))
    out.append(gui_steps(h, "Abaqus/CAE", [
        e("Assembly module > Create Instance, Dependent (mesh on part)."),
        e("Tools > Reference Point at each coordinate above (the generator places them at the middle of the end edges)." if f.reference_nodes else "No reference points: the grips are direct constraints on node sets."),
        e("Tools > Set > Create (Node) for each node set above, Tools > Set > Create (Element) for each element set; the generator's sets are selected by coordinate ranges, which is what the y ranges above state."),
    ], "CAE-CHECK"))
    out.append(gui_steps(h, "PrePoMax 2.6", [
        e("Route A: node sets, element sets and surfaces arrive with the imported deck and are listed under Model > Node sets / Element sets / Surfaces. ") + tag("GUI-SEEN"),
        e("Route B: Model > Node set > Create opens the Set selection window; select by location (box) the rows of the ranges above; Model > Element set > Create likewise. ") + tag("MANUAL p.25") + " " + tag("MANUAL p.26"),
        e("Reference points: Model > Features > Reference point > Create, method Coordinates, enter the coordinates above. ") + tag("MANUAL p.27") if f.reference_nodes else e("No reference points are needed."),
    ], "MANUAL"))
    out.append(keyword_box(h, ctx.kernel_deck.name, "\n".join(keyword_blocks(ctx.kernel_deck, "Assembly", 0) + keyword_blocks(ctx.kernel_deck, "Instance", 0)
                                                        + keyword_blocks(ctx.kernel_deck, "Nset", 1) + keyword_blocks(ctx.kernel_deck, "Elset", 1) + keyword_blocks(ctx.kernel_deck, "Surface", 1))))

    # ---------------------------------------------------------------- step
    out.append(h.heading(1, "Step"))
    static = keyword_blocks(ctx.kernel_deck, "Static", 1, first_only=True)
    static_line = static[0].splitlines()[1] if static and len(static[0].splitlines()) > 1 else None
    out.append(h.kv_table([
        ("Step name / procedure", e(f"{f.step[0]}, Static, General") + " " + tag("INP")),
        ("Nlgeom", e("ON" if f.step[1] else "OFF") + " " + tag("INP")),
        ("Time period / increments", (e(f"{static_line} (period, initial, minimum, maximum)") + " " + tag("INP")) if static_line else (e("defaults (no data line)") + " " + tag("INP"))),
        ("Other settings", e("defaults; the deck writes no override") + " " + tag("INP-derived")),
    ]))
    out.append(gui_steps(h, "Abaqus/CAE", [
        e(f"Step module > Create Step > Static, General, name {f.step[0]}. Basic tab: Nlgeom {'On' if f.step[1] else 'Off'}. Incrementation tab: " + (f"enter {static_line}." if static_line else "defaults.")),
    ], "CAE-CHECK"))
    out.append(gui_steps(h, "PrePoMax 2.6", [
        e(f"Step > Step > Create > Static step: Solver Default, Nlgeom {'On' if f.step[1] else 'Off'}, Incrementation Default. ") + tag("MANUAL p.41"),
    ], "MANUAL"))
    out.append(keyword_box(h, ctx.kernel_deck.name, "\n".join(keyword_blocks(ctx.kernel_deck, "Step", 0) + static)))

    # ---------------------------------------------------------------- constraints
    out.append(h.heading(1, "Interactions and constraints"))
    if f.couplings:
        out.append(r"\textbf{Purpose.} Make each grip zone move rigidly with its reference point.")
        rows = [rf"{e(c.name)} & {e(c.reference)} at ({length(c.reference_xy[0]):g}, {length(c.reference_xy[1]):g}) & {e(f'{c.slaves} nodes, y = {length(c.y_range[0]):g} to {length(c.y_range[1]):g} {L}')} & "
                rf"{e('kinematic, dofs ' + ', '.join(map(str, c.dofs)))} \\" for c in f.couplings]
        out.append(h.long_table(["Name", "Control point", "Coupled nodes", "Type"], rows, r"lYYY", r"\small"))
        out.append("Names and dofs " + tag("INP") + "; node counts and y ranges " + tag("INP-derived") + ". Consequence: a kinematic coupling of the whole grip zone prevents width contraction and rotation there, stiffer than a real gripped specimen; "
                   "the kernel represents it as one rigid translation of the coupled nodes with the reference node's rotations fixed (theory, Section 3). " + tag("CALC"))
        out.append(gui_steps(h, "Abaqus/CAE", [
            e("Interaction module > Create Constraint > Coupling. Control point: the reference point (Set). Surface: the grip node set (Node Region). Coupling type Kinematic, Influence radius To outermost point on the region, all six dofs ticked."),
        ], "CAE-CHECK"))
        out.append(gui_steps(h, "PrePoMax 2.6", [
            e("Interaction > Constraint > Create > Kinematic Coupling: Reference point, Region (a node-based surface; the manual says shells need node-based surfaces), DOF U1-U3 Coupled. ") + tag("MANUAL p.33") + " " + tag("MANUAL p.34"),
            e("CalculiX cannot print the reference node's reaction of a coupling (*NODE PRINT does not report it), so the CalculiX deck of this model uses direct constraints on the grip node sets instead (ADR-0030); the reaction is then the printed total over the set. ") + tag("INP"),
        ], "MANUAL"))
        out.append(keyword_box(h, ctx.kernel_deck.name, "\n".join(keyword_blocks(ctx.kernel_deck, "Coupling", 0) + keyword_blocks(ctx.kernel_deck, "Kinematic", 1))))
    else:
        out.append("No couplings, contact or ties: the grips are direct constraints on the grip node sets (next section). " + tag("INP")
                   + " Consequence: every gripped node is held in all its dofs, which prevents width contraction in the tabs exactly as a kinematic coupling with fixed reference rotations does. " + tag("CALC"))

    # ---------------------------------------------------------------- boundary conditions and loads
    out.append(h.heading(1, "Boundary conditions and loading"))
    grouped: dict[str, list] = {}
    for b in f.boundaries:
        grouped.setdefault(b.target, []).append(b)
    rows = []
    for target, items in grouped.items():
        fixed = sorted({d for b in items if not b.value for d in range(b.dof_first, b.dof_last + 1)})
        prescribed = [(d, b.value) for b in items if b.value for d in range(b.dof_first, b.dof_last + 1)]
        meaning = ("fully fixed" if fixed == [1, 2, 3, 4, 5, 6] and not prescribed else
                   ("held in " + ", ".join(f"U{d}" if d <= 3 else f"UR{d - 3}" for d in fixed) if fixed else "")
                   + ("; " if fixed and prescribed else "") + "; ".join(f"U{d} = {length(v):g} {L}" for d, v in prescribed))
        rows.append(rf"{e(target)} & {items[0].nodes} & {e(meaning)} & {tag('INP')} \\")
    for l in f.loads:
        rows.append(rf"{e(l.target)} & {l.nodes} & {e(f'concentrated load dof {l.dof}, {l.value:g} N per node')} & {tag('INP')} \\")
    out.append(h.long_table(["Applied to", "Nodes", "Constrained dofs / value", "Source"], rows, r"lrYl", r"\small"))
    if pull is not None and free:
        out.append(e(f"Loading is displacement-controlled: {pull:g} {L} over the {free:g} {L} free length is a nominal strain of {pull / free:.4g}. ") + tag("CALC")
                   + (e(" Flag: far larger than any realistic tensile test; meaningful only because the model is linear.") if pull / free > 0.05 else ""))
    out.append(gui_steps(h, "Abaqus/CAE", [
        e(f"Load module > Create Boundary Condition in {f.step[0]}: Symmetry/Antisymmetry/Encastre for a fully fixed set; Displacement/Rotation for the others, ticking the dofs in the table and typing the prescribed value."),
        e("Load module > Create Load > Concentrated force on the loaded set, CF2 = the per-node value.") if f.loads else e("No concentrated or distributed load is defined."),
    ], "CAE-CHECK"))
    out.append(gui_steps(h, "PrePoMax 2.6", [
        e("Step > BC > Create > Fixed for a fully fixed set; Displacement/Rotation for the others: each dof Unconstrained, Fixed or Value (length units). ") + tag("MANUAL p.50") + " " + tag("MANUAL p.51"),
        e("Route A: the boundary conditions arrive with the imported deck under the step. ") + tag("GUI-SEEN"),
    ], "MANUAL"))
    out.append(keyword_box(h, ctx.kernel_deck.name, "\n".join(keyword_blocks(ctx.kernel_deck, "Boundary", 8) + keyword_blocks(ctx.kernel_deck, "Cload", 4))))

    # ---------------------------------------------------------------- mesh
    out.append(h.heading(1, "Mesh"))
    seeds = (e(f"{f.grid[0]} across the width; along the length from the bottom: {', '.join(map(str, f.row_counts))} (total {f.grid[1]})") + " " + tag("INP-derived")) if f.grid else (e("not a rectangular grid") + " " + tag("INP-derived"))
    out.append(h.kv_table([
        ("Element type", e(f"{element_type} ({'4-node reduced-integration conventional shell' if element_type == 'S4R' else '4-node conventional shell'}); the kernel solves it as a bilinear membrane") + " " + tag("INP")),
        ("Counts", e(f"{n_elements} elements, {n_nodes} nodes") + " " + tag("INP-derived")),
        ("Size", e(f"edge lengths {length(f.edge_length_range[0]):.5g} to {length(f.edge_length_range[1]):.5g} {L}") + " " + tag("INP-derived")),
        ("Seeds by number", seeds),
        ("Stack direction", e("not applicable to a conventional shell section") + " " + tag("CAE-CHECK")),
        ("Element controls", e("defaults (none written)") + " " + tag("INP-derived")),
    ]))
    out.append(gui_steps(h, "Abaqus/CAE", [
        e("Mesh module (Object: Part) > Seed > Edges, By number: the counts above on the width edges and on each length segment between partition lines (Seed Part by size gives the same mesh only when the partitions divide evenly)."),
        e(f"Mesh > Element Type: Standard, Linear, Shell, {element_type}" + (", reduced integration, hourglass control default." if element_type == "S4R" else ".")),
        e("Mesh > Mesh Part. Check the counts above in the Mesh module's query tool."),
    ], "CAE-CHECK"))
    out.append(gui_steps(h, "PrePoMax 2.6", [
        e("Route A: the mesh is the imported deck's; nothing to mesh. ") + tag("GUI-SEEN"),
        e("Route B: Mesh > Mesh Setup Item > Create > Shell Gmsh on the imported surface: Transfinite 4-sided faces Yes, Recombine algorithm Simple full-quad; then Local Mesh Size > Create, Defined by Number of elements, on the width edges and on each length segment with the counts above; Mesh > Create Mesh. ") + tag("MANUAL p.19") + " " + tag("MANUAL p.21"),
        e("Route B element type: Model > Part > Edit, Element type; CalculiX composite shells must be S8R (second order), so the CalculiX deck of this model is the order-2 twin of this mesh on the same corner nodes. ") + tag("MANUAL p.25") + " " + tag("INP"),
    ], "MANUAL"))

    # ---------------------------------------------------------------- job and outputs
    out.append(h.heading(1, "Job and outputs"))
    outputs = "\n".join(keyword_blocks(ctx.kernel_deck, "Restart", 0) + keyword_blocks(ctx.kernel_deck, "Output", 0)
                        + keyword_blocks(ctx.kernel_deck, "Node Print", 2) + keyword_blocks(ctx.kernel_deck, "El Print", 2))
    out.append(h.kv_table([
        ("Job", job),
        ("Output requests in the deck", e(", ".join(f.ignored_keywords) + ": skipped by the kernel, since they cannot change the solution; quoted below") + " " + tag("INP")),
        ("What the comparison needs", e("reactions summed over each grip set, displacements at the probe nodes, stresses and strains at the probe elements per ply (the export recipe)") + " " + tag("SPEC" if generated else "INP")),
    ]))
    out.append(gui_steps(h, "Abaqus/CAE", [
        e("Step module > Field Output Requests: Preselected defaults (the deck writes variable=PRESELECT); add S, E, SF at all section points for the comparison."),
        e("Step module > History Output Requests: add RF and U at the reference points or grip sets."),
        e("Job module > Create Job, name as above > Submit > Monitor. Check the .msg and .sta files for warnings. Export per docs/abaqus-export-recipe.md."),
    ], "CAE-CHECK"))
    out.append(gui_steps(h, "PrePoMax 2.6", [
        e("Step > History Output > Create > Node output: RF, Totals Yes, region the grip node set (one per grip); Node output U at the probe nodes; Element output S, E at the probe elements, Global Yes. ") + tag("MANUAL p.47"),
        e("Step > Field Output: the default node (U, RF) and element (S, E) outputs are created with the step. ") + tag("MANUAL p.48") + " " + tag("MANUAL p.49"),
        e("Analysis > Create (solver CalculiX) > Run > Monitor (shows the .dat contents) > Results. The .dat is what tools/record_from_dat.py reads. ") + tag("MANUAL p.57") + " " + tag("MANUAL p.58") + " " + tag("GUI-SEEN"),
    ], "MANUAL"))
    out.append(keyword_box(h, ctx.kernel_deck.name, outputs))
    if ctx.reference_deck != ctx.kernel_deck:
        out.append(keyword_box(h, ctx.reference_deck.name + " (CalculiX)", "\n".join(keyword_blocks(ctx.reference_deck, "Boundary", 8) + keyword_blocks(ctx.reference_deck, "Node Print", 2)
                                                                                     + keyword_blocks(ctx.reference_deck, "El Print", 2) + keyword_blocks(ctx.reference_deck, "Node File", 2) + keyword_blocks(ctx.reference_deck, "El File", 2))))

    # ---------------------------------------------------------------- open items
    out.append(h.heading(1, "Open items of this guide"))
    out.append("Every click path tagged " + tag("CAE-CHECK") + " or " + tag("MANUAL") + " is a procedure, not a stored setting, and must be confirmed in the tool before release. Values that could not be tagged:")
    out.append(r"\begin{itemize}" + "\n" + "\n".join(r"\item " + e(item) for item in open_items) + "\n" + r"\end{itemize}")
    return "\n\n".join(out)
