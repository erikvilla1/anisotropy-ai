"""Write an FEModel as a CalculiX input deck (ADR-0030).

CalculiX's dialect differs from Abaqus's where it matters for a laminate: composite shells are S8R only, a
layer line is `thickness, <unused>, material, orientation` with no `symmetric` keyword, there is no LAMINA
material (ENGINEERING CONSTANTS carries E3, nu13, nu23 too), each ply angle is an *ORIENTATION, the reaction
at a coupled reference node cannot be printed (so grips must be direct constraints), and print requests use
CalculiX's own keys. The deck is flat (no parts), numeric boundaries only, and deterministic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .femodel import FEModel, build_model
from .units import deck_units_of, from_si
from .write_abaqus import PER_LINE, _rows, number

REFERENCE_TEMPERATURE = 293.0  # K, the temperature the constants are stated at; CalculiX needs a value on the second line


class CalculixWriterError(ValueError):
    """The model asks for something CalculiX cannot do or we have not verified."""


def orientation_name(angle_deg: float) -> str:
    whole = int(round(angle_deg))
    text = f"{abs(whole)}" if abs(angle_deg - whole) < 1e-9 else f"{abs(angle_deg):g}".replace(".", "p")
    return f"Ori-{'m' if angle_deg < 0 else ''}{text}"


@dataclass(frozen=True)
class TiedGrip:
    """A grip the model ties to a reference point that carries a force (ADR-0030 amendment 7), as this deck writes it: the grip's nodes
    held node by node, and moved along the force by the travel our kernel finds for it."""

    node_set: str
    reference_set: str
    dof: int
    force: float  # N
    travel: float  # m


def grip_travel(model: FEModel, reference_set: str, dof: int) -> float:
    """How far the reference point of a tied grip travels along `dof` under the model's loads, in metres: our kernel's solution of the
    same model on the corner nodes, the order-1 twin a record compares with."""
    from .abaqus_reader import parse_deck, to_si  # the kernel reads the deck we write, as every comparison does
    from .kernel import solve_deck
    from .write_abaqus import write_abaqus

    spec = model.spec.model_copy(update={"mesh": model.spec.mesh.model_copy(update={"element_order": 1})})
    twin = build_model(spec, model.mesh.corner_mesh() if model.mesh.order == 2 else model.mesh)
    units = deck_units_of(spec.units)
    deck = to_si(parse_deck(write_abaqus(twin, units)), units)
    [reference] = deck.nsets[reference_set]
    return float(solve_deck(deck).displacement_of(reference)[dof - 1])


def tied_grips(model: FEModel) -> tuple[TiedGrip, ...]:
    """The model's couplings as CalculiX can take them: a reference point held in every dof but the one its force acts along. CalculiX
    expands a composite shell into one brick per ply, holds or moves a shell node through all of them, and ties one (*EQUATION,
    *RIGID BODY) by its two faces alone, which leaves the plies between free to lag at the tab line (seen on CalculiX 2.21, 2026-11-17).
    So the grip is written held node by node and moved by the travel our kernel finds for the force: the same grip a displacement
    states, and CalculiX's reaction says what it carries there. A reference point that is moved, turned or free in a second dof is
    refused: CalculiX prints no reaction at a reference node."""
    out = []
    for coupling in model.couplings:
        loads = [load for load in model.loads if load.target == coupling.reference_set]
        held = {dof for b in model.boundaries if b.target == coupling.reference_set and b.value == 0.0 for dof in range(b.dof_first, b.dof_last + 1)}
        moved = any(b.target == coupling.reference_set and b.value != 0.0 for b in model.boundaries)
        if len(loads) != 1 or moved or held != set(range(1, 7)) - {loads[0].dof}:
            raise CalculixWriterError("CalculiX cannot print the reaction at a coupled reference node (*NODE PRINT manual page); "
                                      "use grips.kind = \"nodal\" for the CalculiX deck")
        dof = loads[0].dof
        out.append(TiedGrip(coupling.node_set, coupling.reference_set, dof, loads[0].value, grip_travel(model, coupling.reference_set, dof)))
    return tuple(out)


def write_calculix(model: FEModel, units: str | None = None, el_print_coord: bool = True) -> str:
    """The deck text. `el_print_coord` adds COORD to the element print so each integration point carries its z, which is how a
    result is mapped to its ply; it is on by default because every comparison needs it."""
    units = units or deck_units_of(model.spec.units)  # a deck is written in a deck system, whatever the coupon is stated in (ADR-0061)
    mesh, spec, material, section = model.mesh, model.spec, model.material, model.section
    if mesh.order != 2:
        raise CalculixWriterError("CalculiX composite shells are S8R only: set mesh.element_order = 2 in the spec")
    ties = tied_grips(model)
    if model.loads and spec.grips is not None and spec.grips.kind == "nodal" and not ties:
        raise CalculixWriterError("force control with nodal grips is written for CalculiX as a rigid grip only: a traction spread along the grip is not "
                                  "verified there; set loading.rigid_grip = true in the spec")
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
    if material.isotropic:  # ADR-0075
        out.append("*ELASTIC, TYPE=ISO")
        out.append(f"{number(stress(material.E1))}, {number(material.nu12)}, {number(REFERENCE_TEMPERATURE)}")
    else:
        out.append("*ELASTIC, TYPE=ENGINEERING CONSTANTS")
        out.append(", ".join(number(stress(v)) for v in (material.E1, material.E2, material.E3)) + f", {number(material.nu12)}, {number(material.nu13)}, "
                   f"{number(material.nu23)}, " + ", ".join(number(stress(v)) for v in (material.G12, material.G13)))
        out.append(f"{number(stress(material.G23))}, {number(REFERENCE_TEMPERATURE)}")
    out.append("** Each *ORIENTATION is named by the ply angle the coupon states, counted from its length axis (y, ADR-0065); its axes are the fibre "
               "direction from global x, the stated angle plus 90 degrees.")
    for angle, fibre in zip(model.orientation_angles, model.orientation_fibres):
        c, s = math.cos(math.radians(fibre)), math.sin(math.radians(fibre))
        out.append(f"*ORIENTATION, NAME={orientation_name(angle)}")
        out.append(f"{number(c)}, {number(s)}, 0., {number(-s)}, {number(c)}, 0.")
    if section.homogeneous:  # one isotropic material (ADR-0075): a homogeneous section, its axis 1 along the length as a 0-degree layer's
        ply = section.plies[0]
        out.append(f"*SHELL SECTION, ELSET={section.elset}, MATERIAL={ply.material}, ORIENTATION={orientation_name(ply.angle_deg)}")
        out.append(f"{number(length(ply.thickness_m))}")
    else:
        out.append(f"*SHELL SECTION, ELSET={section.elset}, COMPOSITE")
        for ply in section.plies:
            out.append(f"{number(length(ply.thickness_m))}, , {ply.material}, {orientation_name(ply.angle_deg)}")
    onto = {tie.reference_set: tie.node_set for tie in ties}  # what holds a tied grip's reference node holds the grip's nodes
    fixed = [b for b in model.boundaries if b.value == 0.0]
    moving = [b for b in model.boundaries if b.value != 0.0]
    if fixed:
        out.append("*BOUNDARY")
        out += [f"{onto.get(b.target, b.target)}, {b.dof_first}, {b.dof_last}" for b in fixed]
    out.append("*STEP")
    out.append("*STATIC")
    if moving:
        out.append("*BOUNDARY")
        out += [f"{b.target}, {b.dof_first}, {b.dof_last}, {number(length(b.value) if b.dof_last <= 3 else b.value)}" for b in moving]
    for tie in ties:
        out.append(f"** The coupon states a force of {number(from_si(tie.force, 'force', units))} on {tie.node_set}, which moves as one. CalculiX holds a shell node "
                   "through every ply and ties one by its faces alone, so the grip is moved here by the travel our kernel finds for that force on "
                   "the same model, and CalculiX's reaction says what it carries there (ADR-0030 amendment 7).")
        out.append("*BOUNDARY")
        out.append(f"{tie.node_set}, {tie.dof}, {tie.dof}, {number(length(tie.travel))}")
    loads = [load for load in model.loads if load.target not in onto]
    if loads:
        out.append("*CLOAD")
        out += [f"{load.target.rsplit('.', 1)[-1] if '.' in load.target else load.target}, {load.dof}, {number(from_si(load.value, 'force', units))}" for load in loads]
    if model.pressures:
        out.append("** A CalculiX shell pressure is positive along the element normal (fea/checks/calculix-conventions.toml). The spec's pressure is positive against it, pressing on the top face, so it is written here with the opposite sign.")
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
