"""Reads the subset of the Abaqus input format that the team's coupon decks use (ADR-0029).

A deck is keyword lines (`*Keyword, param=value, flag`), comment lines (`**`) and data lines. The
reader tokenizes the file into keyword blocks, then interprets each block with a handler that accepts
only the parameters and data forms listed in `fea/README.md`. Anything else is refused with the line
number (ADR-0003). Output requests cannot change the solution, so they are skipped and recorded in
`Deck.ignored_keywords`. Numbers are kept exactly as written; `read_deck` converts to SI once the
caller has stated the unit system.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .model import (
    GLOBAL_AXES,
    SUPPORTED_ELEMENT_TYPES,
    Boundary,
    ConcentratedLoad,
    Deck,
    DeckError,
    Elastic,
    ElementKey,
    Elements,
    ElementSurface,
    FailStress,
    Instance,
    KinematicCoupling,
    Layer,
    Material,
    NodeKey,
    Nodes,
    NodeSurface,
    Orientation,
    Part,
    ShellSection,
    Step,
    to_si,
    validate_deck,
)

# Output requests and job controls: they cannot change the solution, so they are skipped and recorded.
IGNORED_KEYWORDS = frozenset({
    "preprint", "restart", "output", "node output", "element output", "contact output",
    "node print", "el print", "energy output", "node file", "el file",
})

# Named boundary types and the dofs they hold (Abaqus definitions).
NAMED_BOUNDARIES = {
    "ENCASTRE": (1, 2, 3, 4, 5, 6), "PINNED": (1, 2, 3),
    "XSYMM": (1, 5, 6), "YSYMM": (2, 4, 6), "ZSYMM": (3, 4, 5),
}
REFUSED_NAMED_BOUNDARIES = ("XASYMM", "YASYMM", "ZASYMM")
AXES_TOLERANCE = 1e-9


@dataclass(frozen=True)
class KeywordBlock:
    name: str  # lower case, single spaces, without the leading "*"
    params: dict[str, str | None]  # lower-case keys; None for a flag such as `composite`
    data: tuple[tuple[str, ...], ...]
    line: int
    data_lines: tuple[int, ...]


def tokenize(text: str) -> list[KeywordBlock]:
    """Keyword blocks in file order. Comment lines are dropped; a trailing comma leaves no empty token."""
    blocks: list[KeywordBlock] = []
    current: list | None = None
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("**"):
            continue
        if line.lstrip().startswith("*"):
            if current is not None:
                blocks.append(_finish(current))
            name, params = _keyword(line.lstrip(), number)
            current = [name, params, [], number, []]
            continue
        if current is None:
            raise DeckError(f"line {number}: data before any keyword")
        tokens = [token.strip() for token in line.split(",")]
        if tokens and tokens[-1] == "":
            tokens.pop()
        current[2].append(tuple(tokens))
        current[4].append(number)
    if current is not None:
        blocks.append(_finish(current))
    return blocks


def _finish(current: list) -> KeywordBlock:
    name, params, data, line, data_lines = current
    return KeywordBlock(name=name, params=params, data=tuple(data), line=line, data_lines=tuple(data_lines))


def _keyword(line: str, number: int) -> tuple[str, dict[str, str | None]]:
    pieces = [piece.strip() for piece in line[1:].split(",")]
    name = re.sub(r"\s+", " ", pieces[0]).strip().lower()
    if not name:
        raise DeckError(f"line {number}: empty keyword")
    params: dict[str, str | None] = {}
    for piece in pieces[1:]:
        if not piece:
            continue
        key, _, value = piece.partition("=")
        key = re.sub(r"\s+", " ", key).strip().lower()
        if key in params:
            raise DeckError(f"line {number}: *{pieces[0]} repeats the parameter {key!r}")
        params[key] = value.strip() if "=" in piece else None
    return name, params


# --- interpretation -----------------------------------------------------------------------------


@dataclass
class _PartBuilder:
    name: str
    line: int
    labels: list[int] = field(default_factory=list)
    xyz: list[tuple[float, float, float]] = field(default_factory=list)
    element_labels: list[int] = field(default_factory=list)
    connectivity: list[tuple[int, int, int, int]] = field(default_factory=list)
    element_type: str | None = None
    nsets: dict[str, list[int]] = field(default_factory=dict)
    elsets: dict[str, list[int]] = field(default_factory=dict)
    orientations: dict[str, Orientation] = field(default_factory=dict)
    sections: list[ShellSection] = field(default_factory=list)

    def build(self) -> Part:
        labels = np.asarray(self.labels, dtype=int)
        if np.unique(labels).size != labels.size:
            raise DeckError(f"part {self.name!r}: node labels repeat")
        elements = None
        if self.element_labels:
            element_labels = np.asarray(self.element_labels, dtype=int)
            if np.unique(element_labels).size != element_labels.size:
                raise DeckError(f"part {self.name!r}: element labels repeat")
            elements = Elements(labels=element_labels, connectivity=np.asarray(self.connectivity, dtype=int).reshape(-1, 4),
                                element_type=self.element_type or "")
        return Part(
            name=self.name,
            nodes=Nodes(labels=labels, xyz=np.asarray(self.xyz, dtype=float).reshape(-1, 3)),
            elements=elements,
            nsets={name: np.asarray(values, dtype=int) for name, values in self.nsets.items()},
            elsets={name: np.asarray(values, dtype=int) for name, values in self.elsets.items()},
            orientations=dict(self.orientations),
            sections=tuple(self.sections),
        )


@dataclass
class _StepBuilder:
    name: str
    nlgeom: bool
    line: int
    procedure: str | None = None
    boundaries: list[Boundary] = field(default_factory=list)
    cloads: list[ConcentratedLoad] = field(default_factory=list)


class _Parser:
    def __init__(self, blocks: list[KeywordBlock], source_sha256: str, source_path: str | None) -> None:
        self.blocks = blocks
        self.source_sha256 = source_sha256
        self.source_path = source_path
        self.heading = ""
        self.parts: dict[str, Part] = {}
        self.part: _PartBuilder | None = None
        self.in_assembly = False
        self.assembly_seen = False
        self.instance_open: str | None = None
        self.instances: dict[str, Instance] = {}
        self.assembly_labels: list[int] = []
        self.assembly_xyz: list[tuple[float, float, float]] = []
        self.nsets: dict[str, list[NodeKey]] = {}
        self.elsets: dict[str, list[ElementKey]] = {}
        self.surfaces: dict[str, NodeSurface | ElementSurface] = {}
        self.couplings: list[KinematicCoupling] = []
        self.pending_coupling: KeywordBlock | None = None
        self.materials: dict[str, Material] = {}
        self.material: str | None = None
        self.model_boundaries: list[Boundary] = []
        self.steps: list[Step] = []
        self.step: _StepBuilder | None = None
        self.ignored: list[str] = []

    def run(self) -> Deck:
        for block in self.blocks:
            if self.pending_coupling is not None and block.name != "kinematic":
                self._refuse_coupling_type(block)
            handler = HANDLERS.get(block.name)
            if handler is None:
                if block.name in IGNORED_KEYWORDS:
                    self.ignored.append(f"line {block.line}: *{block.name}")
                    continue
                raise DeckError(f"line {block.line}: *{block.name} is not supported by anisotropy_fea 0.1; "
                                "see fea/README.md for the supported subset")
            handler(self, block)
        if self.part is not None:
            raise DeckError(f"line {self.part.line}: *Part {self.part.name!r} has no *End Part")
        if self.in_assembly:
            raise DeckError("the *Assembly has no *End Assembly")
        if self.step is not None:
            raise DeckError(f"line {self.step.line}: *Step {self.step.name!r} has no *End Step")
        return Deck(
            heading=self.heading,
            parts=self.parts,
            instances=self.instances,
            assembly_nodes=Nodes(labels=np.asarray(self.assembly_labels, dtype=int),
                                 xyz=np.asarray(self.assembly_xyz, dtype=float).reshape(-1, 3)),
            nsets={name: tuple(keys) for name, keys in self.nsets.items()},
            elsets={name: tuple(keys) for name, keys in self.elsets.items()},
            surfaces=dict(self.surfaces),
            couplings=tuple(self.couplings),
            materials=dict(self.materials),
            model_boundaries=tuple(self.model_boundaries),
            steps=tuple(self.steps),
            ignored_keywords=tuple(self.ignored),
            source_sha256=self.source_sha256,
            source_path=self.source_path,
        )

    # -- helpers --

    @staticmethod
    def _params(block: KeywordBlock, allowed: tuple[str, ...], required: tuple[str, ...] = ()) -> None:
        for key in block.params:
            if key not in allowed:
                raise DeckError(f"line {block.line}: *{block.name} parameter {key!r} is not supported")
        for key in required:
            if block.params.get(key) is None:
                raise DeckError(f"line {block.line}: *{block.name} needs the parameter {key!r}")

    @staticmethod
    def _flag(block: KeywordBlock, key: str) -> bool:
        return key in block.params

    @staticmethod
    def _int(token: str, line: int, what: str) -> int:
        try:
            return int(token)
        except ValueError:
            raise DeckError(f"line {line}: {what} must be an integer; got {token!r}") from None

    @staticmethod
    def _float(token: str, line: int, what: str) -> float:
        try:
            value = float(token)
        except ValueError:
            raise DeckError(f"line {line}: {what} must be a number; got {token!r}") from None
        if value != value or value in (float("inf"), float("-inf")):
            raise DeckError(f"line {line}: {what} must be finite; got {token!r}")
        return value

    def _target(self, token: str, line: int) -> str | NodeKey:
        """A boundary or load target: a set name, `Instance.label`, or a bare assembly node label."""
        if token.isdigit():
            return (None, int(token))
        instance, dot, label = token.rpartition(".")
        if dot and label.isdigit():
            if instance not in self.instances:
                raise DeckError(f"line {line}: {token!r} names instance {instance!r}, which is not defined")
            return (instance, int(label))
        return token

    def _labels(self, block: KeywordBlock) -> list[int]:
        labels: list[int] = []
        if self._flag(block, "generate"):
            for tokens, line in zip(block.data, block.data_lines):
                if len(tokens) not in (2, 3):
                    raise DeckError(f"line {line}: a generate line is `first, last[, step]`")
                first, last = (self._int(tokens[0], line, "first label"), self._int(tokens[1], line, "last label"))
                step = self._int(tokens[2], line, "step") if len(tokens) == 3 else 1
                if step <= 0:
                    raise DeckError(f"line {line}: generate step must be positive")
                labels.extend(range(first, last + 1, step))
            return labels
        for tokens, line in zip(block.data, block.data_lines):
            for token in tokens:
                labels.append(self._int(token, line, "a set member"))
        return labels

    def _outside_blocks(self, block: KeywordBlock, what: str) -> None:
        if self.part is not None:
            raise DeckError(f"line {block.line}: {what} inside a *Part is not supported")
        if self.in_assembly:
            raise DeckError(f"line {block.line}: {what} inside the *Assembly is not supported")

    def _refuse_coupling_type(self, block: KeywordBlock) -> None:
        pending = self.pending_coupling
        assert pending is not None
        if block.name in ("distributing", "structural"):
            raise DeckError(f"line {block.line}: *{block.name} coupling is not supported; only *Kinematic couplings are")
        raise DeckError(f"line {pending.line}: *Coupling must be followed by *Kinematic; found *{block.name} at line {block.line}")

    # -- handlers --

    def heading_(self, block: KeywordBlock) -> None:
        self._params(block, ())
        self.heading = " ".join(" ".join(tokens) for tokens in block.data).strip()

    def part_(self, block: KeywordBlock) -> None:
        self._params(block, ("name",), required=("name",))
        if self.part is not None:
            raise DeckError(f"line {block.line}: *Part inside *Part {self.part.name!r}")
        name = block.params["name"] or ""
        if name in self.parts:
            raise DeckError(f"line {block.line}: part {name!r} is defined twice")
        self.part = _PartBuilder(name=name, line=block.line)

    def end_part_(self, block: KeywordBlock) -> None:
        if self.part is None:
            raise DeckError(f"line {block.line}: *End Part without *Part")
        self.parts[self.part.name] = self.part.build()
        self.part = None

    def node_(self, block: KeywordBlock) -> None:
        self._params(block, ("system",))
        if (block.params.get("system") or "R").upper() != "R":
            raise DeckError(f"line {block.line}: *Node system {block.params['system']!r} is not supported; only rectangular coordinates are")
        if self.instance_open is not None:
            raise DeckError(f"line {block.line}: nodes inside *Instance are not supported")
        if self.part is None and not self.in_assembly:
            raise DeckError(f"line {block.line}: *Node outside a *Part or the *Assembly")
        for tokens, line in zip(block.data, block.data_lines):
            if len(tokens) not in (3, 4):
                raise DeckError(f"line {line}: a node line is `label, x, y[, z]`")
            label = self._int(tokens[0], line, "node label")
            coords = [self._float(token, line, "a coordinate") for token in tokens[1:]]
            if len(coords) == 2:
                coords.append(0.0)
            if self.part is not None:
                self.part.labels.append(label)
                self.part.xyz.append((coords[0], coords[1], coords[2]))
            else:
                self.assembly_labels.append(label)
                self.assembly_xyz.append((coords[0], coords[1], coords[2]))

    def element_(self, block: KeywordBlock) -> None:
        self._params(block, ("type", "elset"), required=("type",))
        if self.part is None:
            raise DeckError(f"line {block.line}: *Element outside a *Part is not supported")
        element_type = (block.params["type"] or "").upper()
        if element_type not in SUPPORTED_ELEMENT_TYPES:
            raise DeckError(f"line {block.line}: element type {element_type!r} is not supported; anisotropy_fea 0.1 reads "
                            f"{', '.join(SUPPORTED_ELEMENT_TYPES)} (four-node shells)")
        if self.part.element_type not in (None, element_type):
            raise DeckError(f"line {block.line}: part {self.part.name!r} mixes element types {self.part.element_type} and {element_type}")
        self.part.element_type = element_type
        labels = []
        for tokens, line in zip(block.data, block.data_lines):
            if len(tokens) != 5:
                raise DeckError(f"line {line}: a {element_type} element line is `label, n1, n2, n3, n4`")
            values = [self._int(token, line, "an element line entry") for token in tokens]
            self.part.element_labels.append(values[0])
            self.part.connectivity.append((values[1], values[2], values[3], values[4]))
            labels.append(values[0])
        if block.params.get("elset"):
            self.part.elsets.setdefault(block.params["elset"] or "", []).extend(labels)

    def nset_(self, block: KeywordBlock) -> None:
        self._set(block, "nset")

    def elset_(self, block: KeywordBlock) -> None:
        self._set(block, "elset")

    def _set(self, block: KeywordBlock, kind: str) -> None:
        if "unsorted" in block.params:
            raise DeckError(f"line {block.line}: *{block.name} unsorted is not supported")
        self._params(block, (kind, "instance", "internal", "generate"), required=(kind,))
        name = block.params[kind] or ""
        labels = self._labels(block)
        if self.part is not None:
            if "instance" in block.params:
                raise DeckError(f"line {block.line}: *{block.name} inside a *Part cannot name an instance")
            target = self.part.nsets if kind == "nset" else self.part.elsets
            target.setdefault(name, []).extend(labels)
            return
        if not self.in_assembly:
            raise DeckError(f"line {block.line}: *{block.name} outside a *Part or the *Assembly is not supported")
        instance = block.params.get("instance")
        if instance is not None and instance not in self.instances:
            raise DeckError(f"line {block.line}: *{block.name} names instance {instance!r}, which is not defined")
        if kind == "nset":
            self.nsets.setdefault(name, []).extend((instance, label) for label in labels)
        else:
            if instance is None:
                raise DeckError(f"line {block.line}: an assembly *Elset needs instance=; the assembly has no elements of its own")
            self.elsets.setdefault(name, []).extend((instance, label) for label in labels)

    def orientation_(self, block: KeywordBlock) -> None:
        self._params(block, ("name", "system", "definition"), required=("name",))
        if (block.params.get("system") or "RECTANGULAR").upper() != "RECTANGULAR":
            raise DeckError(f"line {block.line}: *Orientation system {block.params['system']!r} is not supported")
        if "definition" in block.params:
            raise DeckError(f"line {block.line}: *Orientation definition= is not supported")
        if self.part is None:
            raise DeckError(f"line {block.line}: *Orientation outside a *Part is not supported")
        if not 1 <= len(block.data) <= 2:
            raise DeckError(f"line {block.line}: *Orientation takes one data line of axes and an optional rotation line")
        first, first_line = block.data[0], block.data_lines[0]
        if len(first) < 6:
            raise DeckError(f"line {first_line}: *Orientation axes line needs the six components of a and b")
        values = [self._float(token, first_line, "an axis component") for token in first[:6]]
        axis, angle = 3, 0.0
        if len(block.data) == 2:
            second, second_line = block.data[1], block.data_lines[1]
            if len(second) != 2:
                raise DeckError(f"line {second_line}: *Orientation rotation line is `axis, angle`")
            axis = self._int(second[0], second_line, "rotation axis")
            angle = self._float(second[1], second_line, "rotation angle")
        a, b = tuple(values[:3]), tuple(values[3:6])
        if (max(abs(a[i] - GLOBAL_AXES[0][i]) for i in range(3)) > AXES_TOLERANCE
                or max(abs(b[i] - GLOBAL_AXES[1][i]) for i in range(3)) > AXES_TOLERANCE or angle != 0.0):
            raise DeckError(f"line {block.line}: *Orientation {block.params['name']!r} is not the global axes with zero rotation; "
                            "anisotropy_fea 0.1 reads laminate axes aligned with x and y only (a rotated layup is a planned extension)")
        name = block.params["name"] or ""
        self.part.orientations[name] = Orientation(name=name, a=a, b=b, rotation_axis=axis, rotation_deg=angle, line=block.line)  # type: ignore[arg-type]

    def shell_section_(self, block: KeywordBlock) -> None:
        if "nodal thickness" in block.params:
            raise DeckError(f"line {block.line}: *Shell Section nodal thickness is not supported")
        self._params(block, ("elset", "composite", "orientation", "layup", "symmetric", "material", "offset", "section integration"),
                     required=("elset",))
        if self.part is None:
            raise DeckError(f"line {block.line}: *Shell Section outside a *Part is not supported")
        offset = block.params.get("offset")
        if offset is not None:
            try:
                offset_value = float(offset)
            except ValueError:
                offset_value = None
            if offset_value != 0.0:
                raise DeckError(f"line {block.line}: *Shell Section offset={offset} is not supported; the membrane reference surface is the midplane")
        composite = self._flag(block, "composite")
        material = block.params.get("material")
        if composite and material is not None:
            raise DeckError(f"line {block.line}: a composite *Shell Section does not take material=; materials are on the layer lines")
        if not composite and material is None:
            raise DeckError(f"line {block.line}: *Shell Section needs either composite with layer lines or material=")
        if not composite and self._flag(block, "symmetric"):
            raise DeckError(f"line {block.line}: symmetric applies to a composite *Shell Section only")
        layers: list[Layer] = []
        if composite:
            if not block.data:
                raise DeckError(f"line {block.line}: a composite *Shell Section needs at least one layer line")
            for tokens, line in zip(block.data, block.data_lines):
                if len(tokens) not in (4, 5):
                    raise DeckError(f"line {line}: a layer line is `thickness, integration points, material, angle[, ply name]`")
                layers.append(Layer(
                    thickness=self._float(tokens[0], line, "layer thickness"),
                    integration_points=self._int(tokens[1], line, "layer integration points"),
                    material=tokens[2],
                    angle_deg=self._float(tokens[3], line, "layer angle"),
                    ply_name=tokens[4] if len(tokens) == 5 else None,
                ))
        else:
            if len(block.data) != 1 or len(block.data[0]) not in (1, 2):
                raise DeckError(f"line {block.line}: a homogeneous *Shell Section takes one line `thickness[, integration points]`")
            tokens, line = block.data[0], block.data_lines[0]
            layers.append(Layer(
                thickness=self._float(tokens[0], line, "shell thickness"),
                integration_points=self._int(tokens[1], line, "integration points") if len(tokens) == 2 else 5,
                material=material or "", angle_deg=0.0, ply_name=None,
            ))
        for layer in layers:
            if layer.thickness <= 0:
                raise DeckError(f"line {block.line}: a layer thickness must be positive")
        self.part.sections.append(ShellSection(
            elset=block.params["elset"] or "",
            orientation=block.params.get("orientation"),
            layup_name=block.params.get("layup"),
            symmetric=self._flag(block, "symmetric"),
            layers=tuple(layers),
            section_integration=block.params.get("section integration"),
            line=block.line,
        ))

    def assembly_(self, block: KeywordBlock) -> None:
        self._params(block, ("name",))
        if self.part is not None:
            raise DeckError(f"line {block.line}: *Assembly inside a *Part")
        if self.assembly_seen:
            raise DeckError(f"line {block.line}: a second *Assembly")
        self.in_assembly = True
        self.assembly_seen = True

    def end_assembly_(self, block: KeywordBlock) -> None:
        if not self.in_assembly:
            raise DeckError(f"line {block.line}: *End Assembly without *Assembly")
        if self.instance_open is not None:
            raise DeckError(f"line {block.line}: *End Assembly inside *Instance {self.instance_open!r}")
        self.in_assembly = False

    def instance_(self, block: KeywordBlock) -> None:
        self._params(block, ("name", "part"), required=("name", "part"))
        if not self.in_assembly:
            raise DeckError(f"line {block.line}: *Instance outside the *Assembly")
        if block.data:
            raise DeckError(f"line {block.line}: a translated or rotated instance is not supported yet; "
                            "anisotropy_fea 0.1 reads instances placed at the origin without rotation")
        name, part = block.params["name"] or "", block.params["part"] or ""
        if part not in self.parts:
            raise DeckError(f"line {block.line}: *Instance names part {part!r}, which is not defined")
        if name in self.instances:
            raise DeckError(f"line {block.line}: instance {name!r} is defined twice")
        self.instances[name] = Instance(name=name, part=part)
        self.instance_open = name

    def end_instance_(self, block: KeywordBlock) -> None:
        if self.instance_open is None:
            raise DeckError(f"line {block.line}: *End Instance without *Instance")
        self.instance_open = None

    def surface_(self, block: KeywordBlock) -> None:
        self._params(block, ("type", "name", "internal"), required=("name",))
        if not self.in_assembly:
            raise DeckError(f"line {block.line}: *Surface outside the *Assembly is not supported")
        kind = (block.params.get("type") or "ELEMENT").upper()
        name = block.params["name"] or ""
        if kind == "NODE":
            if len(block.data) != 1 or len(block.data[0]) not in (1, 2):
                raise DeckError(f"line {block.line}: a node-based *Surface takes one line `node set[, weight]`")
            tokens, line = block.data[0], block.data_lines[0]
            if len(tokens) == 2 and self._float(tokens[1], line, "surface weight") != 1.0:
                raise DeckError(f"line {line}: node surface weights other than 1 are not supported")
            self.surfaces[name] = NodeSurface(name=name, nset=tokens[0], internal=self._flag(block, "internal"))
        elif kind == "ELEMENT":
            if len(block.data) != 1 or len(block.data[0]) != 2:
                raise DeckError(f"line {block.line}: an element-based *Surface takes one line `element set, side`")
            tokens = block.data[0]
            self.surfaces[name] = ElementSurface(name=name, elset=tokens[0], side=tokens[1].upper())
        else:
            raise DeckError(f"line {block.line}: *Surface type {kind!r} is not supported")

    def coupling_(self, block: KeywordBlock) -> None:
        if "influence radius" in block.params:
            raise DeckError(f"line {block.line}: *Coupling influence radius is not supported")
        self._params(block, ("constraint name", "ref node", "surface"), required=("constraint name", "ref node", "surface"))
        if not self.in_assembly:
            raise DeckError(f"line {block.line}: *Coupling outside the *Assembly is not supported")
        if block.data:
            raise DeckError(f"line {block.line}: *Coupling takes no data lines")
        self.pending_coupling = block

    def kinematic_(self, block: KeywordBlock) -> None:
        self._params(block, ())
        pending = self.pending_coupling
        if pending is None:
            raise DeckError(f"line {block.line}: *Kinematic without a preceding *Coupling")
        dofs: set[int] = set()
        if not block.data:
            dofs = set(range(1, 7))
        for tokens, line in zip(block.data, block.data_lines):
            if len(tokens) not in (1, 2):
                raise DeckError(f"line {line}: a *Kinematic line is `first dof[, last dof]`")
            first = self._int(tokens[0], line, "a dof")
            last = self._int(tokens[1], line, "a dof") if len(tokens) == 2 else first
            if not 1 <= first <= last <= 6:
                raise DeckError(f"line {line}: *Kinematic dofs {first}..{last} are outside 1..6")
            dofs.update(range(first, last + 1))
        self.couplings.append(KinematicCoupling(
            name=pending.params["constraint name"] or "", ref_node_set=pending.params["ref node"] or "",
            surface=pending.params["surface"] or "", dofs=frozenset(dofs), line=pending.line,
        ))
        self.pending_coupling = None

    def material_(self, block: KeywordBlock) -> None:
        self._params(block, ("name",), required=("name",))
        self._outside_blocks(block, "*Material")
        if self.step is not None:
            raise DeckError(f"line {block.line}: *Material inside a *Step is not supported")
        name = block.params["name"] or ""
        if name in self.materials:
            raise DeckError(f"line {block.line}: material {name!r} is defined twice")
        self.materials[name] = Material(name=name, elastic=None, fail_stress=None, line=block.line)
        self.material = name

    def _open_material(self, block: KeywordBlock) -> Material:
        if self.material is None:
            raise DeckError(f"line {block.line}: *{block.name} outside a *Material")
        return self.materials[self.material]

    def elastic_(self, block: KeywordBlock) -> None:
        if "dependencies" in block.params:
            raise DeckError(f"line {block.line}: *Elastic dependencies= (field-variable dependence) is not supported")
        self._params(block, ("type",))
        material = self._open_material(block)
        if material.elastic is not None:
            raise DeckError(f"line {block.line}: material {material.name!r} has two *Elastic definitions")
        if len(block.data) != 1:
            raise DeckError(f"line {block.line}: *Elastic with {len(block.data)} data lines; temperature-dependent elasticity is not supported")
        tokens, line = block.data[0], block.data_lines[0]
        kind = (block.params.get("type") or "ISOTROPIC").upper()
        if kind == "LAMINA":
            if len(tokens) != 6:
                raise DeckError(f"line {line}: *Elastic, type=LAMINA takes exactly `E1, E2, nu12, G12, G13, G23` "
                                f"(a seventh value would be a temperature, which is not supported)")
            values = [self._float(token, line, "an elastic constant") for token in tokens]
            elastic = Elastic(kind="LAMINA", E1=values[0], E2=values[1], nu12=values[2], G12=values[3], G13=values[4], G23=values[5])
        elif kind == "ISOTROPIC":
            if len(tokens) != 2:
                raise DeckError(f"line {line}: isotropic *Elastic takes exactly `E, nu` (a third value would be a temperature)")
            E, nu = (self._float(token, line, "an elastic constant") for token in tokens)
            elastic = Elastic(kind="ISOTROPIC", E1=E, E2=E, nu12=nu, G12=E / (2.0 * (1.0 + nu)))
        else:
            raise DeckError(f"line {block.line}: *Elastic type {kind!r} is not supported; LAMINA and isotropic are")
        self.materials[material.name] = material.model_copy(update={"elastic": elastic})

    def fail_stress_(self, block: KeywordBlock) -> None:
        self._params(block, ())
        material = self._open_material(block)
        if material.fail_stress is not None:
            raise DeckError(f"line {block.line}: material {material.name!r} has two *Fail Stress definitions")
        if len(block.data) != 1 or not 5 <= len(block.data[0]) <= 7:
            raise DeckError(f"line {block.line}: *Fail Stress takes one line `Xt, Xc, Yt, Yc, S[, f*[, sigma_biax]]`")
        tokens, line = block.data[0], block.data_lines[0]
        values = [self._float(token, line, "a strength") for token in tokens]
        self.materials[material.name] = material.model_copy(update={"fail_stress": FailStress(
            Xt=values[0], Xc=values[1], Yt=values[2], Yc=values[3], S=values[4],
            f_star=values[5] if len(values) > 5 else None, sigma_biax=values[6] if len(values) > 6 else None,
        )})

    def step_(self, block: KeywordBlock) -> None:
        if "perturbation" in block.params:
            raise DeckError(f"line {block.line}: *Step perturbation is not supported")
        self._params(block, ("name", "nlgeom", "inc"))
        self._outside_blocks(block, "*Step")
        if self.step is not None:
            raise DeckError(f"line {block.line}: *Step inside *Step {self.step.name!r}")
        if self.steps:
            raise DeckError(f"line {block.line}: a second *Step is not supported; anisotropy_fea 0.1 solves one linear static step")
        nlgeom = (block.params.get("nlgeom") or "NO").upper()
        if nlgeom == "YES":
            raise DeckError(f"line {block.line}: nlgeom=YES (geometric nonlinearity) is not supported; the kernel is linear")
        self.material = None
        self.step = _StepBuilder(name=block.params.get("name") or f"step at line {block.line}", nlgeom=False, line=block.line)

    def static_(self, block: KeywordBlock) -> None:
        if block.params:
            raise DeckError(f"line {block.line}: *Static parameters {sorted(block.params)} are not supported (a plain linear static step is)")
        if self.step is None:
            raise DeckError(f"line {block.line}: *Static outside a *Step")
        if self.step.procedure is not None:
            raise DeckError(f"line {block.line}: a second procedure in *Step {self.step.name!r}")
        if len(block.data) > 1:
            raise DeckError(f"line {block.line}: *Static takes at most one data line")
        self.step.procedure = "static"

    def end_step_(self, block: KeywordBlock) -> None:
        if self.step is None:
            raise DeckError(f"line {block.line}: *End Step without *Step")
        if self.step.procedure is None:
            raise DeckError(f"line {self.step.line}: *Step {self.step.name!r} has no *Static procedure")
        self.steps.append(Step(name=self.step.name, nlgeom=self.step.nlgeom, boundaries=tuple(self.step.boundaries),
                               cloads=tuple(self.step.cloads), line=self.step.line))
        self.step = None

    def boundary_(self, block: KeywordBlock) -> None:
        self._params(block, ("type",))
        if (block.params.get("type") or "DISPLACEMENT").upper() != "DISPLACEMENT":
            raise DeckError(f"line {block.line}: *Boundary type {block.params['type']!r} is not supported")
        if self.part is not None or self.instance_open is not None:
            raise DeckError(f"line {block.line}: *Boundary inside a *Part or *Instance is not supported")
        for tokens, line in zip(block.data, block.data_lines):
            if len(tokens) < 2:
                raise DeckError(f"line {line}: a boundary line is `node or set, first dof[, last dof[, value]]` or `node or set, TYPE`")
            target = self._target(tokens[0], line)
            if not tokens[1].lstrip("-").isdigit():
                kind = tokens[1].upper()
                if kind in REFUSED_NAMED_BOUNDARIES:
                    raise DeckError(f"line {line}: boundary type {kind} is not supported")
                if kind not in NAMED_BOUNDARIES:
                    raise DeckError(f"line {line}: boundary type {kind!r} is not known")
                if len(tokens) != 2:
                    raise DeckError(f"line {line}: a named boundary type takes no further values")
                for dof in NAMED_BOUNDARIES[kind]:
                    self._add_boundary(Boundary(target=target, dof_first=dof, dof_last=dof, value=0.0, line=line))
                continue
            if len(tokens) > 4:
                raise DeckError(f"line {line}: a boundary line has at most four entries")
            first = self._int(tokens[1], line, "first dof")
            last = self._int(tokens[2], line, "last dof") if len(tokens) >= 3 and tokens[2] else first
            value = self._float(tokens[3], line, "prescribed value") if len(tokens) == 4 else 0.0
            self._add_boundary(Boundary(target=target, dof_first=first, dof_last=last, value=value, line=line))

    def _add_boundary(self, boundary: Boundary) -> None:
        if self.step is not None:
            self.step.boundaries.append(boundary)
        else:
            self.model_boundaries.append(boundary)

    def cload_(self, block: KeywordBlock) -> None:
        self._params(block, ())
        if self.step is None:
            raise DeckError(f"line {block.line}: *Cload outside a *Step is not supported")
        for tokens, line in zip(block.data, block.data_lines):
            if len(tokens) != 3:
                raise DeckError(f"line {line}: a concentrated load line is `node or set, dof, value`")
            self.step.cloads.append(ConcentratedLoad(target=self._target(tokens[0], line), dof=self._int(tokens[1], line, "load dof"),
                                                     value=self._float(tokens[2], line, "load value"), line=line))


HANDLERS = {
    "heading": _Parser.heading_,
    "part": _Parser.part_,
    "end part": _Parser.end_part_,
    "node": _Parser.node_,
    "element": _Parser.element_,
    "nset": _Parser.nset_,
    "elset": _Parser.elset_,
    "orientation": _Parser.orientation_,
    "shell section": _Parser.shell_section_,
    "assembly": _Parser.assembly_,
    "end assembly": _Parser.end_assembly_,
    "instance": _Parser.instance_,
    "end instance": _Parser.end_instance_,
    "surface": _Parser.surface_,
    "coupling": _Parser.coupling_,
    "kinematic": _Parser.kinematic_,
    "material": _Parser.material_,
    "elastic": _Parser.elastic_,
    "fail stress": _Parser.fail_stress_,
    "step": _Parser.step_,
    "static": _Parser.static_,
    "end step": _Parser.end_step_,
    "boundary": _Parser.boundary_,
    "cload": _Parser.cload_,
}

SUPPORTED_KEYWORDS = tuple(sorted(HANDLERS))


def parse_deck(text: str, source_path: str | None = None) -> Deck:
    """The deck as written: unitless, unvalidated. Refuses anything outside the supported subset."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return _Parser(tokenize(text), digest, source_path).run()


def read_deck(path: Path | str, units: str) -> Deck:
    """Parse, validate and convert a deck file to SI. `units` must name the system the file is written in."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    deck = parse_deck(text, source_path=str(path))
    notes = validate_deck(deck)
    converted = to_si(deck, units)
    return dataclasses.replace(converted, notes=notes)
