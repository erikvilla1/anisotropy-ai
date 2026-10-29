"""Write an FEModel as a CalculiX input deck (ADR-0030).

CalculiX's dialect differs from Abaqus's where it matters for a laminate: composite shells are S8R only, a
layer line is `thickness, <unused>, material, orientation` with no `symmetric` keyword, there is no LAMINA
material (ENGINEERING CONSTANTS carries E3, nu13, nu23 too), each ply angle is an *ORIENTATION, the reaction
at a coupled reference node cannot be printed (so grips must be direct constraints), and print requests use
CalculiX's own keys. The deck is flat (no parts), numeric boundaries only, and deterministic.
"""

from __future__ import annotations

import math

from .femodel import FEModel
from .units import from_si
from .write_abaqus import PER_LINE, _rows, number

REFERENCE_TEMPERATURE = 293.0  # K, the temperature the constants are stated at; CalculiX needs a value on the second line


class CalculixWriterError(ValueError):
    """The model asks for something CalculiX cannot do or we have not verified."""


def orientation_name(angle_deg: float) -> str:
    whole = int(round(angle_deg))
    text = f"{abs(whole)}" if abs(angle_deg - whole) < 1e-9 else f"{abs(angle_deg):g}".replace(".", "p")
    return f"Ori-{'m' if angle_deg < 0 else ''}{text}"


def write_calculix(model: FEModel, units: str | None = None, el_print_coord: bool = True) -> str:
    """The deck text. `el_print_coord` adds COORD to the element print so each integration point carries its z, which is how a
    result is mapped to its ply; it is on by default because every comparison needs it."""
    units = units or model.spec.units
    mesh, spec, material, section = model.mesh, model.spec, model.material, model.section
    if mesh.order != 2:
        raise CalculixWriterError("CalculiX composite shells are S8R only: set mesh.element_order = 2 in the spec")
    if model.couplings:
        raise CalculixWriterError("CalculiX cannot print the reaction at a coupled reference node (*NODE PRINT manual page); "
                                  "use grips.kind = \"nodal\" for the CalculiX deck")
    if model.loads and spec.grips is not None and spec.grips.kind == "nodal":
        raise CalculixWriterError("force control with nodal grips is not written for CalculiX yet: a rigid grip under force needs a reference node")
    length = lambda v: from_si(v, "length", units)  # noqa: E731
    stress = lambda v: from_si(v, "stress", units)  # noqa: E731
    out: list[str] = ["*HEADING"]
    out.append(f"CalculiX deck written by anisotropy_fea from {spec.title}")
    out += [f"** {line}" for line in model.heading]
    out.append("** Layer lines are listed bottom-first; CalculiX's own convention is detected by the conventions run and recorded in fea/checks/calculix-conventions.toml.")
    out.append("*NODE, NSET=Nall")
    for index, (x, y) in enumerate(mesh.xy, start=1):
        out.append(f"{index}, {number(length(x))}, {number(length(y))}, 0.")
    out.append(f"*ELEMENT, TYPE=S8R, ELSET={section.elset}")
    for index, nodes in enumerate(mesh.connectivity(), start=1):
        out.append(f"{index}, " + ", ".join(str(int(n) + 1) for n in nodes))
    for name, indices in model.node_sets.items():
        out.append(f"*NSET, NSET={name}")
        out += _rows([int(i) + 1 for i in indices])
    for name, indices in model.element_sets.items():
        out.append(f"*ELSET, ELSET={name}")
        out += _rows([int(i) + 1 for i in indices])
    out.append(f"*MATERIAL, NAME={material.name}")
    out.append("*ELASTIC, TYPE=ENGINEERING CONSTANTS")
    out.append(", ".join(number(stress(v)) for v in (material.E1, material.E2, material.E3)) + f", {number(material.nu12)}, {number(material.nu13)}, "
               f"{number(material.nu23)}, " + ", ".join(number(stress(v)) for v in (material.G12, material.G13)))
    out.append(f"{number(stress(material.G23))}, {number(REFERENCE_TEMPERATURE)}")
    for angle in model.orientation_angles:
        c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        out.append(f"*ORIENTATION, NAME={orientation_name(angle)}")
        out.append(f"{number(c)}, {number(s)}, 0., {number(-s)}, {number(c)}, 0.")
    out.append(f"*SHELL SECTION, ELSET={section.elset}, COMPOSITE")
    for ply in section.plies:
        out.append(f"{number(length(ply.thickness_m))}, , {ply.material}, {orientation_name(ply.angle_deg)}")
    fixed = [b for b in model.boundaries if b.value == 0.0]
    moving = [b for b in model.boundaries if b.value != 0.0]
    if fixed:
        out.append("*BOUNDARY")
        out += [f"{b.target}, {b.dof_first}, {b.dof_last}" for b in fixed]
    out.append("*STEP")
    out.append("*STATIC")
    if moving:
        out.append("*BOUNDARY")
        out += [f"{b.target}, {b.dof_first}, {b.dof_last}, {number(length(b.value) if b.dof_last <= 3 else b.value)}" for b in moving]
    if model.loads:
        out.append("*CLOAD")
        out += [f"{load.target.rsplit('.', 1)[-1] if '.' in load.target else load.target}, {load.dof}, {number(from_si(load.value, 'force', units))}" for load in model.loads]
    if model.pressures:
        out.append("** A CalculiX shell pressure is positive along the element normal, the opposite of the Abaqus P label (fea/checks/calculix-conventions.toml): the sign is flipped here.")
        out.append("*DLOAD")
        out += [f"{pressure.elset}, P, {number(-stress(pressure.value))}" for pressure in model.pressures]
    requests = spec.output.calculix
    if requests.node_print:
        for grip in model.support_sets:
            if grip in model.node_sets:
                out.append(f"*NODE PRINT, NSET={grip}, TOTALS=YES")
                out.append("RF")
        for name in model.probe_nodes:
            out.append(f"*NODE PRINT, NSET=Probe-{name}")
            out.append("U")
    if requests.el_print:
        for name in model.probe_elements:
            out.append(f"*EL PRINT, ELSET=Probe-{name}" + (", GLOBAL=YES" if requests.el_print_global else ""))
            out.append("S, E" + (", COORD" if el_print_coord else ""))
    if requests.frd:
        out.append("*NODE FILE")
        out.append("U")
        out.append("*EL FILE")
        out.append("S, E")
    out.append("*END STEP")
    return "\n".join(out) + "\n"
