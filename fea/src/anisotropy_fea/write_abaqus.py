"""Write an FEModel as an Abaqus input deck in the dialect our own reader accepts (ADR-0030).

The deck has the structure of the team's Abaqus/CAE decks: one part with nodes, elements and the composite
shell section; one instance; assembly-level node and element sets, reference nodes, node surfaces and
kinematic couplings when the grips are couplings; the material; one linear static step with numeric boundary
conditions, concentrated loads and output requests. Numbers are written in the deck's unit system from the
model's SI values. The text is deterministic, so its SHA-256 identifies the model.

The deck is valid Abaqus/Standard input as written (ADR-0045 amendment 2): every line is at most 256 bytes, the longest
Abaqus reads, so a longer heading comment is wrapped. Abaqus counts bytes of the UTF-8 file, not characters: it truncated a
389-character comment on 2026-10-24, and on 2026-10-25 a 253-character line holding five two-byte "·" (258 bytes). Every
`*El Print` table holds one variable, because Abaqus/Standard refused the combined tables `SF, SE` and `S, E` of a composite
shell ("THERE ARE MORE THAN 9 OUTPUT REQUESTS IN A SINGLE TABLE").
"""

from __future__ import annotations

from .femodel import FEModel
from .units import from_si

PER_LINE = 16
MAX_LINE = 256  # bytes in one line of an Abaqus input file, in the UTF-8 the deck is written in


def number(value: float) -> str:
    text = f"{value:.10g}"
    return text if ("." in text or "e" in text or "inf" in text or "nan" in text) else text + "."


def _rows(labels: list[int]) -> list[str]:
    return [", ".join(str(label) for label in labels[i:i + PER_LINE]) for i in range(0, len(labels), PER_LINE)]


def line_bytes(line: str) -> int:
    return len(line.encode("utf-8"))


def _comment(line: str) -> list[str]:
    """`** line`, wrapped at spaces into lines of at most MAX_LINE bytes when longer; a continuation is indented two spaces more
    than the line it continues. A single word that cannot fit a line is refused rather than cut (a URL would break)."""
    whole = f"** {line}"
    if line_bytes(whole) <= MAX_LINE:
        return [whole]
    indent = line[:len(line) - len(line.lstrip())]
    pieces, prefix, words = [], f"** {indent}", []
    for word in line.split():
        if words and line_bytes(prefix + " ".join([*words, word])) > MAX_LINE:
            pieces.append(prefix + " ".join(words))
            prefix, words = f"** {indent}  ", []
        if line_bytes(prefix + word) > MAX_LINE:
            raise ValueError(f"a heading word of {line_bytes(word)} bytes cannot fit an Abaqus line of {MAX_LINE} bytes: {word[:60]}...")
        words.append(word)
    pieces.append(prefix + " ".join(words))
    return pieces


def write_abaqus(model: FEModel, units: str | None = None) -> str:
    """The deck text."""
    units = units or model.spec.units
    length = lambda v: from_si(v, "length", units)  # noqa: E731
    stress = lambda v: from_si(v, "stress", units)  # noqa: E731
    force = lambda v: from_si(v, "force", units)  # noqa: E731
    mesh, spec, material = model.mesh, model.spec, model.material
    out: list[str] = ["*Heading"]
    out += [piece for line in model.heading for piece in _comment(line)]
    out.append("*Preprint, echo=NO, model=NO, history=NO, contact=NO")

    out.append(f"*Part, name={model.part}")
    out.append("*Node")
    for index, (x, y) in enumerate(mesh.xy, start=1):
        out.append(f"{index}, {number(length(x))}, {number(length(y))}, 0.")
    element_type = "S4R" if mesh.order == 1 else "S8R"
    out.append(f"*Element, type={element_type}")
    for index, nodes in enumerate(mesh.connectivity(), start=1):
        out.append(f"{index}, " + ", ".join(str(int(n) + 1) for n in nodes))
    out.append(f"*Elset, elset={model.section.elset}, generate")
    out.append(f"1, {mesh.element_count}, 1")
    out.append("*Orientation, name=Ori-1")
    out.append("1., 0., 0., 0., 1., 0.")
    out.append("3, 0.")
    section = model.section
    out.append(f"*Shell Section, elset={section.elset}, composite, orientation=Ori-1, layup={section.layup}" + (", symmetric" if section.symmetric else ""))
    for ply in section.listed:
        out.append(f"{number(length(ply.thickness_m))}, 3, {ply.material}, {number(ply.angle_deg)}, {ply.name}")
    out.append("*End Part")

    out.append("*Assembly, name=Assembly")
    out.append(f"*Instance, name={model.instance}, part={model.part}")
    out.append("*End Instance")
    for point in model.reference_points:
        out.append("*Node")
        out.append(f"{point.label}, {number(length(point.xy[0]))}, {number(length(point.xy[1]))}, 0.")
        out.append(f"*Nset, nset={point.set_name}")
        out.append(f"{point.label},")
    for name, indices in model.node_sets.items():
        out.append(f"*Nset, nset={name}, instance={model.instance}")
        out += _rows([int(i) + 1 for i in indices])
    for name, indices in model.element_sets.items():
        out.append(f"*Elset, elset={name}, instance={model.instance}")
        out += _rows([int(i) + 1 for i in indices])
    for coupling in model.couplings:
        out.append(f"*Surface, type=NODE, name={coupling.node_set}_CNS_, internal")
        out.append(f"{coupling.node_set}, 1.")
    for coupling in model.couplings:
        out += _comment(f"Constraint: {coupling.name}")
        out.append(f"*Coupling, constraint name={coupling.name}, ref node={coupling.reference_set}, surface={coupling.node_set}_CNS_")
        out.append("*Kinematic")
    out.append("*End Assembly")

    out.append(f"*Material, name={material.name}")
    out.append("*Elastic, type=LAMINA")
    out.append(", ".join(number(stress(v)) for v in (material.E1, material.E2)) + f", {number(material.nu12)}, "
               + ", ".join(number(stress(v)) for v in (material.G12, material.G13, material.G23)))
    if material.strengths is not None:
        s = material.strengths
        line = ", ".join(number(stress(v)) for v in (s.F1t, -s.F1c, s.F2t, -s.F2c, s.F6))
        if material.f12_star is not None:
            line += f", {number(material.f12_star)}"
        out.append("*Fail Stress")
        out.append(line)

    out.append("*Step, name=Step-1, nlgeom=NO")
    out.append("*Static")
    out.append("1., 1., 1e-05, 1.")
    out.append("*Boundary")
    for boundary in model.boundaries:
        line = f"{boundary.target}, {boundary.dof_first}, {boundary.dof_last}"
        if boundary.value != 0.0:
            line += f", {number(length(boundary.value) if boundary.dof_last <= 3 else boundary.value)}"  # a rotation stays in radians
        out.append(line)
    if model.loads:
        out.append("*Cload")
        for load in model.loads:
            out.append(f"{load.target}, {load.dof}, {number(force(load.value))}")
    if model.pressures:
        out.append("*Dload")
        for pressure in model.pressures:
            out.append(f"{pressure.elset}, P, {number(stress(pressure.value))}")
    requests = spec.output.abaqus
    out.append("*Restart, write, frequency=0")
    if requests.field_preselect:
        out.append("*Output, field, variable=PRESELECT")
        out.append("*Output, history, variable=PRESELECT")
    if requests.node_print:
        for reaction_set in (model.support_sets if model.bending else model.support_sets[:1]):  # the moving grip, or the supports and the nose
            out.append(f"*Node Print, nset={reaction_set}, totals=YES")
            out.append("RF")
        for name in model.probe_nodes:
            out.append(f"*Node Print, nset=Probe-{name}")
            out.append("U")
    if requests.el_print:
        for name in model.probe_elements:
            for variable in ("SF", "SE", "S", "E"):
                out.append(f"*El Print, elset=Probe-{name}, position=CENTROIDAL")
                out.append(variable)
    out.append("*End Step")
    return "\n".join(out) + "\n"
