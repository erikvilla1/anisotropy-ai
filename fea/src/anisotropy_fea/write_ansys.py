"""Write an FEModel as an Ansys Mechanical APDL input file (ADR-0129).

The file is the model the Abaqus deck states, in Mechanical APDL's own commands: the nodes, elements and components as the blocks an
archive file holds (`NBLOCK`, `EBLOCK`, `CMBLOCK`, the form `CDWRITE` writes), and the element type, the material, the layered section,
the supports, the loads and one linear static solution as plain commands. Numbers are written in the deck's unit system from the model's
SI values, and the text is deterministic. Each convention below is stated from the command and element reference, and the tests of this
repository check it only by reading the text back.

What Mechanical APDL does differently from Abaqus, and what this file does about it:

- One numbering for every node and one name space for every component. A node set is the component `N_<NAME>` and an element set
  `E_<NAME>`, upper case, every character that is not a letter or a digit written as `_`; a name over 32 characters is refused.
- No kinematic coupling keyword of the same meaning. A grip tied to a reference point that does not turn moves as one, so the grip's
  nodes carry the reference point's supports themselves: `D` where the point is held or moved, and a coupled set (`CP`) with the force
  on its first node where the point is free and loaded. A reference point that turns is refused.
- A layer's angle is counted from the element's x axis, which `ESYS` sets. Coordinate system 11 is the global one turned 90 degrees
  about z, so x is the coupon's length axis (global y) and y is global -x, the same frame as the Abaqus deck's `Ori-1`: the `SECDATA`
  lines carry the angles as the coupon states them (ADR-0065). Layers are listed from the bottom face up, along the element normal
  (+z: a mesh of ours counts every element counter-clockwise, `Mesh2D` refuses any other).
- A pressure on face 2 of a shell (its top) is positive pressing into the element, against the normal, which is the spec's own sign.
- Strength limits (`TB,FCLI`) are stated for three directions. A lamina's strengths give none through the thickness, so those limits are
  written a million times the fibre strength, which leaves those directions out of every criterion, as the Abaqus deck's plane
  `*Fail Stress` does. Compressive limits are negative. The Tsai-Wu coefficient XYCP is twice our f12*; zero is written 1E-14 because a
  zero there means Ansys's own default of -1.
- Failure measures are worked out after the solution, for the criteria `FCTYP` names. Its own choice includes the maximum strain
  criterion, and with stress limits alone Mechanical APDL then stops at an error and lists none, so the file names the maximum
  stress criterion alone (ADR-0129 amendment 2).
"""

from __future__ import annotations

import re

from .femodel import FEModel
from .units import deck_units_of, from_si
from .write_abaqus import SECTION_POINTS, number

EXTENSION = ".cdb"  # read by /INPUT or CDREAD,DB in Mechanical APDL, and as an archive by Workbench's External Model
ORIENTATION_SYSTEM = 11  # the local coordinate system whose x is the coupon's length axis; 11 is the first number a user may give
PER_LINE = 8  # labels on one line of a CMBLOCK, its (8i10) format
MAX_NAME = 32  # characters in a component name
MAX_LINE = 240  # characters in a comment line here; Mechanical APDL reads 640
UNITS_LABEL = {"mm-MPa": "MPA", "m-Pa": "SI"}  # /UNITS: a label kept with the model, it converts nothing
DOF_LABEL = {1: "UX", 2: "UY", 3: "UZ", 4: "ROTX", 5: "ROTY", 6: "ROTZ"}
FORCE_LABEL = {1: "FX", 2: "FY", 3: "FZ", 4: "MX", 5: "MY", 6: "MZ"}
NOT_CHECKED = 1e6  # times the fibre strength: a limit no stress reaches, for the directions a lamina's strengths do not state
EFFECTIVE_ZERO = 1e-14  # a coupling coefficient of zero, as the FC command's page says to write it
PLAIN = {"·": "*", "°": " deg", "²": "^2", "³": "^3", "×": "x", "–": "-", "—": "-", "−": "-", "’": "'", "‘": "'", "“": '"', "”": '"', "≤": "<=", "≥": ">=",
         "±": "+/-", "µ": "u", "μ": "u", "ν": "nu", "σ": "sigma", "τ": "tau", "ε": "epsilon", "γ": "gamma", "é": "e", "…": "..."}


class AnsysWriterError(ValueError):
    """The model asks for something this file cannot state, or that we have not written for Mechanical APDL yet."""


def component_name(kind: str, name: str) -> str:
    """The component that stands for a node set (`kind` "N") or an element set ("E")."""
    text = f"{kind}_" + re.sub(r"[^A-Za-z0-9]", "_", name).upper()
    if len(text) > MAX_NAME:
        raise AnsysWriterError(f"the set {name!r} gives the component name {text}, {len(text)} characters; Mechanical APDL takes {MAX_NAME}")
    return text


def ascii_text(line: str) -> str:
    """A line in ASCII: the signs we write get their plain form and anything else its code, so nothing is dropped without a trace."""
    for sign, plain in PLAIN.items():
        line = line.replace(sign, plain)
    return line.encode("ascii", "backslashreplace").decode("ascii")


def _comment(line: str) -> list[str]:
    """`! line`, in ASCII, wrapped at spaces into lines of at most MAX_LINE characters."""
    pieces, prefix, words = [], "! ", []
    for word in ascii_text(line).split():
        if words and len(prefix + " ".join([*words, word])) > MAX_LINE:
            pieces.append(prefix + " ".join(words))
            prefix, words = "!   ", []
        words.append(word)
    pieces.append(prefix + " ".join(words))
    return pieces


def _real(value: float) -> str:
    """One number of an NBLOCK line, the Fortran field e21.13e3 as CDWRITE fills it: ` 2.5000000000000E-001`."""
    mantissa, exponent = f"{value:.13E}".split("E")
    return f"{mantissa}E{exponent[0]}{int(exponent[1:]):03d}".rjust(21)


def _block(labels: list[int]) -> list[str]:
    return ["".join(f"{label:10d}" for label in labels[i:i + PER_LINE]) for i in range(0, len(labels), PER_LINE)]


def element_type(model: FEModel) -> tuple[str, list[tuple[int, int, str]]]:
    """The Mechanical APDL element and its key options. A four-node shell is SHELL181, with reduced integration as S4R or full as S4; an
    eight-node shell is SHELL281, whose node order (corners, then midsides) is S8R's."""
    if model.mesh.order == 2:
        return "SHELL281", [(1, 0, "bending and membrane stiffness"), (8, 2, "results kept at the bottom, top and middle of every layer")]
    full = model.spec.output.abaqus.element == "S4"
    return "SHELL181", [(1, 0, "bending and membrane stiffness"),
                        (3, 2 if full else 0, "full integration with incompatible modes, as S4" if full else "reduced integration with hourglass control, as S4R"),
                        (8, 2, "results kept at the bottom, top and middle of every layer")]


def grip_ties(model: FEModel) -> dict[str, str]:
    """Each coupled reference set and the node set that stands in for it. A reference point that is turned, or loaded by a moment, is
    refused: its grip would rotate as a rigid body, which a coupled set does not state."""
    ties = {}
    for coupling in model.couplings:
        reference = coupling.reference_set
        held = {dof for b in model.boundaries if b.target == reference and b.value == 0.0 for dof in range(b.dof_first, b.dof_last + 1)}
        if not {4, 5, 6} <= held or any(load.target == reference and load.dof > 3 for load in model.loads):
            raise AnsysWriterError(f"the reference point {reference} of the grip {coupling.node_set} may turn; a grip that rotates as a rigid body is not "
                                   "written for Ansys yet")
        ties[reference] = coupling.node_set
    return ties


def write_ansys(model: FEModel, units: str | None = None) -> str:
    """The file's text."""
    units = units or deck_units_of(model.spec.units)  # written in a deck system, whatever the coupon is stated in (ADR-0061)
    length = lambda v: from_si(v, "length", units)  # noqa: E731
    stress = lambda v: from_si(v, "stress", units)  # noqa: E731
    force = lambda v: from_si(v, "force", units)  # noqa: E731
    mesh, spec, material, section = model.mesh, model.spec, model.material, model.section
    ties = grip_ties(model)
    name, options = element_type(model)
    node_components = {component_name("N", set_name): indices for set_name, indices in model.node_sets.items()}
    element_components = {component_name("E", set_name): indices for set_name, indices in model.element_sets.items()}
    if len(node_components) != len(model.node_sets) or len(element_components) != len(model.element_sets):
        raise AnsysWriterError("two sets of this model give the same component name; Mechanical APDL reads names without case and without signs")

    out: list[str] = []
    out += [piece for line in model.heading for piece in _comment(line)]
    out += _comment("Ansys Mechanical APDL input, written as the model's Abaqus deck is: read it with /INPUT (File > Read Input from) or CDREAD,DB. "
                    "It builds the model, solves one linear static load step and lists the reactions and the probes.")
    out += _comment(f"A node set is the component N_<NAME>, an element set E_<NAME>. Units: {units} ({'mm, MPa, N' if units == 'mm-MPa' else 'm, Pa, N'}).")
    out.append("/PREP7")
    out.append("/TITLE," + re.sub(r"[^A-Za-z0-9 .;:()/\[\]+=_-]", " ", ascii_text(spec.title).replace(",", ";"))[:72].rstrip())
    out.append(f"/UNITS,{UNITS_LABEL[units]}")

    out += _comment(f"Element type: {name}, a {'four' if mesh.order == 1 else 'eight'}-node layered shell.")
    out.append(f"ET,1,{name.removeprefix('SHELL')}")  # by its number, as an archive file states it
    for key, value, words in options:  # a comment on a line of its own: other readers of this format do not take one after a command
        out += _comment(f"KEYOPT({key}) = {value}: {words}")
        out.append(f"KEYOPT,1,{key},{value}")

    out.append(f"NBLOCK,6,SOLID,{mesh.node_count:10d},{mesh.node_count:10d}")
    out.append("(3i9,6e21.13e3)")
    for index, (x, y) in enumerate(mesh.xy, start=1):
        out.append(f"{index:9d}{0:9d}{0:9d}{_real(length(x))}{_real(length(y))}{_real(0.0)}")
    out.append("N,R5.3,LOC,       -1,")

    out += _comment(f"Coordinate system {ORIENTATION_SYSTEM} is the global one turned 90 degrees about z: its x is the length axis (global y) and its y is "
                    "global -x. Every element takes it as its element system (ESYS), so a layer's angle is counted from the length axis toward "
                    "global -x, as the coupon states it.")
    out.append(f"LOCAL,{ORIENTATION_SYSTEM},0,0.,0.,0.,90.")
    out.append("CSYS,0")

    per_element = 4 if mesh.order == 1 else 8
    out += _comment("Elements: material, type, real constant, section, element system, birth, solid model, shape, node count, unused, number, nodes.")
    out.append(f"EBLOCK,19,SOLID,{mesh.element_count:10d},{mesh.element_count:10d}")
    out.append("(19i10)")
    for index, nodes in enumerate(mesh.connectivity(), start=1):
        fields = [1, 1, 1, 1, ORIENTATION_SYSTEM, 0, 0, 0, per_element, 0, index, *[int(n) + 1 for n in nodes]]
        out.append("".join(f"{value:10d}" for value in fields))
    out.append("-1")

    for component, indices in node_components.items():
        out.append(f"CMBLOCK,{component},NODE,{len(indices):10d}")
        out.append("(8i10)")
        out += _block([int(i) + 1 for i in indices])
    for component, indices in element_components.items():
        out.append(f"CMBLOCK,{component},ELEM,{len(indices):10d}")
        out.append("(8i10)")
        out += _block([int(i) + 1 for i in indices])

    out += _comment(f"Material 1: {material.name}. x is the fibre direction, z the thickness.")
    if material.isotropic:
        out.append(f"MP,EX,1,{number(stress(material.E1))}")
        out.append(f"MP,PRXY,1,{number(material.nu12)}")
    else:
        for label, value in (("EX", stress(material.E1)), ("EY", stress(material.E2)), ("EZ", stress(material.E3)), ("PRXY", material.nu12),
                             ("PRYZ", material.nu23), ("PRXZ", material.nu13), ("GXY", stress(material.G12)), ("GYZ", stress(material.G23)),
                             ("GXZ", stress(material.G13))):
            out.append(f"MP,{label},1,{number(value)}")
    if material.strengths is not None:
        s = material.strengths
        far = NOT_CHECKED * s.F1t
        out += _comment("Strength limits (stress): tension and compression along x, y and z, then shear xy, yz and xz. Compression is negative. The "
                        "lamina states no strength through the thickness, so z, yz and xz are written a million times the fibre strength: those "
                        "directions are not checked, as in the Abaqus deck.")
        out.append("TB,FCLI,1,1,20,1")
        out.append("TBDATA,1," + ",".join(number(stress(v)) for v in (s.F1t, -s.F1c, s.F2t, -s.F2c, far, -far)))
        out.append("TBDATA,7," + ",".join(number(stress(v)) for v in (s.F6, far, far)))
        if material.f12_star is not None:
            out += _comment(f"Tsai-Wu coefficient XYCP = 2 f12* = 2 x {material.f12_star:g}; a zero is written {EFFECTIVE_ZERO:g}, because 0 there means -1.")
            out.append(f"TBDATA,10,{number(2.0 * material.f12_star if material.f12_star != 0.0 else EFFECTIVE_ZERO)}")
        else:
            out += _comment("The coupon states no Tsai-Wu interaction term, so none is written: Ansys's own default (XYCP = -1) would apply to a Tsai-Wu "
                            "check made here, and that value is not ours.")

    if section.homogeneous:
        out += _comment("Section 1: one layer of the one material, its x along the length axis.")
    else:
        out += _comment(f"Section 1: the layup {section.layup}, every layer from the bottom face up: thickness, material, angle, integration points.")
    out.append("SECTYPE,1,SHELL")
    for ply in section.plies:
        out.append(f"SECDATA,{number(length(ply.thickness_m))},1,{number(ply.angle_deg)},{SECTION_POINTS}")
    out.append("SECOFFSET,MID")

    onto = lambda target: component_name("N", ties.get(target, target))  # noqa: E731  what holds a reference point holds its grip's nodes
    out += _comment("Supports and prescribed movements.")
    stated: dict[str, set[int]] = {}
    for boundary in model.boundaries:
        for dof in range(boundary.dof_first, boundary.dof_last + 1):
            stated.setdefault(boundary.target, set()).add(dof)
            value = length(boundary.value) if dof <= 3 else boundary.value  # a rotation stays in radians
            out.append(f"D,{onto(boundary.target)},{DOF_LABEL[dof]},{number(value)}")
    for reference, grip in ties.items():
        free = [dof for dof in (1, 2, 3) if dof not in stated.get(reference, set())]
        for dof in free:
            out += _comment(f"The grip {grip} moves as one along {DOF_LABEL[dof]}: a coupled set of its nodes. A force on the set acts on the whole grip.")
            out.append(f"CMSEL,S,{component_name('N', grip)}")
            out.append(f"CP,NEXT,{DOF_LABEL[dof]},ALL")
            out.append("ALLSEL,ALL")
    if model.loads:
        out += _comment("Forces at nodes.")
        for load in model.loads:
            if load.target in ties:  # the force on a reference point goes to the first node of its grip's coupled set
                target = str(int(model.node_sets[ties[load.target]].min()) + 1)
            elif "." in load.target:
                target = load.target.rsplit(".", 1)[-1]
            else:
                target = component_name("N", load.target)
            out.append(f"F,{target},{FORCE_LABEL[load.dof]},{number(force(load.value))}")
    if model.pressures:
        out += _comment("Pressures on face 2, the top face: positive presses on the top, against the element normal, which is the coupon's own sign.")
        for pressure in model.pressures:
            out.append(f"SFE,{component_name('E', pressure.elset)},2,PRES,,{number(stress(pressure.value))}")
    out.append("FINISH")

    out += _comment("One linear static load step.")
    out += ["/SOLU", "ANTYPE,STATIC", "NLGEOM,OFF", "OUTRES,ALL,ALL", "SOLVE", "FINISH"]

    out += _comment("The reactions of each support, with their totals, and the movement of each probe.")
    out += ["/POST1", "SET,LAST"]
    if material.strengths is not None:
        out += _comment("Failure measures: the maximum stress criterion alone, the one the stress limits above serve. Left at its own choice, "
                        "Mechanical APDL also asks for strain limits, which the lamina does not state, and then lists no failure measure at all.")
        out += ["FCTYP,DELE,ALL", "FCTYP,ADD,SMAX"]
    for support in model.support_sets:
        out += [f"CMSEL,S,{onto(support)}", "PRRSOL", "ALLSEL,ALL"]
    for probe in model.probe_nodes:
        out += [f"CMSEL,S,{component_name('N', f'Probe-{probe}')}", "PRNSOL,U,COMP", "ALLSEL,ALL"]
    out.append("FINISH")
    return "\n".join(out) + "\n"
