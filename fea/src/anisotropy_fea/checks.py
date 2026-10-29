"""The setup check the studio shows before a coupon is solved (ADR-0051): one list of named items, each passed, warned, failed,
missing an input, or still pending, with the form rows it concerns.

Every judgement is the one the tools already make: the form's checks (`intake.check_form`), the coupon's name
(`intake.designation_for`), the spec's rules (`spec.parse_spec`), the mesh (`femodel.build_model`), the engine's criterion
rules (`anisotropy_engine.failure.check_criterion`), the mesh quality measures (`quality.py`), and what is installed (CalculiX,
Tectonic, Gmsh). This module only sorts what they say under the items an engineer reads, and never passes a setup those
tools refuse. A failed or missing item blocks the run; a warning does not.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from anisotropy_engine.failure import check_criterion

from . import paths
from .calculix import ccx_version, find_ccx
from .case_pages import read_case
from .femodel import FEModel, build_model
from .intake import FIELDS, FormInput, IntakeError, Values, check_form, designation_for, form_rows_of, spec_from_values
from .mesher import MeshError, gmsh_available
from .model import PLAUSIBLE_MODULUS_PA, is_symmetric_layup
from .quality import QualityField, element_quality, quality_summary, quality_words
from .spec import TEST_CODES, SpecError, full_angles, layup_text, spec_plies
from .units import UNIT_LABEL, from_si

STATES = ("pass", "warn", "fail", "missing", "pending")
SEVERITY = {"pass": 0, "warn": 1, "fail": 2, "missing": 2}
ITEMS = (  # in the order the studio lists them: id, label
    ("identity", "Who and which coupon"),
    ("units", "Units consistent"),
    ("geometry", "Geometry defined"),
    ("material", "Material defined"),
    ("laminate", "Laminate assigned"),
    ("constraints", "Constraints defined"),
    ("load", "Load applied"),
    ("mesh", "Mesh quality acceptable"),
    ("criterion", "Failure criterion"),
    ("probes", "Result points inside the coupon"),
    ("solver", "Reference solver installed"),
    ("document", "Document builder installed"),
)
ITEM_OF_KEY = {  # which item a form row belongs to
    **{key: "identity" for key in ("filled_by", "date", "notes", "test", "material_code", "layup_code", "standard", "size_from", "team_model", "test_data",
                                   "name_part", "name_instance", "name_material", "name_layup", "name_section")},
    **{key: "geometry" for key in ("length", "width", "tab_length", "hole_diameter", "span", "overhang", "load_span")},
    **{key: "mesh" for key in ("hole_circumferential", "hole_radial", "hole_ring", "hole_growth", "element_size", "mesh_nx", "mesh_partitions", "mesh_seeds")},
    **{key: "laminate" for key in ("symmetric", "ply_thickness", *(f"ply_{i}" for i in range(1, 17)))},
    **{key: "material" for key in ("library", "own_name", "own_E1", "own_E2", "own_G12", "own_nu12", "own_F1t", "own_F1c", "own_F2t", "own_F2c",
                                   "own_F6", "own_source", "G13", "G23")},
    **{key: "criterion" for key in ("criteria", "f12_star")},
    **{key: "load" for key in ("control", "value")},
    **{key: "constraints" for key in ("grips", "region")},
}
ITEM_OF_LABEL = {f.label: ITEM_OF_KEY[key] for key, f in FIELDS.items()}


@dataclass(frozen=True)
class CheckItem:
    id: str
    label: str
    state: str
    message: str
    rows: tuple[str, ...] = ()  # the form rows concerned, by label


@dataclass(frozen=True)
class Checklist:
    items: tuple[CheckItem, ...]
    designation: str | None
    coupon_exists: bool
    attempts: int
    state: str  # "ready" when nothing failed or is missing, else "blocked"
    problems: tuple[str, ...]  # every refusal, as the tools word it

    def as_dict(self) -> dict[str, Any]:
        return {"items": [{**asdict(item), "rows": list(item.rows)} for item in self.items], "designation": self.designation, "coupon_exists": self.coupon_exists,
                "attempts": self.attempts, "state": self.state, "problems": list(self.problems)}


def find_tectonic() -> str | None:
    """Tectonic on PATH, or where its Windows installer puts it (as docs/manual/build.py looks for it)."""
    found = shutil.which("tectonic")
    fallback = Path.home() / "AppData/Local/Programs/tectonic/tectonic.exe"
    return found or (str(fallback) if fallback.exists() else None)


def split_problems(message: str) -> list[tuple[str, str]]:
    """A refusal's message, '<file>: <row>: <problem>; <row>: <problem>', as (row label, problem) pairs; a problem naming no row is
    paired with ''."""
    body = message.split(": ", 1)[1] if ": " in message and not message.startswith(tuple(ITEM_OF_LABEL)) else message
    pairs = []
    for problem in body.split("; "):
        label = next((lab for lab in ITEM_OF_LABEL if problem.startswith(lab + ":")), "")
        if not label:  # a problem naming two rows, "Library material and Own material: ...": the first row it names
            label = next((lab for lab in ITEM_OF_LABEL if problem.startswith(lab + " ")), "")
        pairs.append((label, problem))
    return pairs


def coupon_attempts(root: Path, designation: str | None) -> tuple[bool, int]:
    """Whether the coupon already has its specs under root, and how many rows its case page's attempt log holds."""
    if designation is None or not (root / designation / paths.OURS / f"{designation}.toml").is_file():
        return False, 0
    try:
        return True, read_case(root / designation).attempts
    except Exception:  # a page that does not read: the coupon exists; the run tool names the page's problem
        return True, 0


class _Notes:
    """The items' states, messages and rows as the checks fill them in."""

    def __init__(self) -> None:
        self.state = {item_id: "pending" for item_id, _ in ITEMS}
        self.messages: dict[str, list[str]] = {item_id: [] for item_id, _ in ITEMS}
        self.rows: dict[str, list[str]] = {item_id: [] for item_id, _ in ITEMS}

    def note(self, item_id: str, state: str, message: str, rows: tuple[str, ...] = ()) -> None:
        if self.state[item_id] == "pending" or SEVERITY[state] > SEVERITY[self.state[item_id]]:
            self.state[item_id] = state
        if message:
            self.messages[item_id].append(message)
        for label in rows:
            if label and label not in self.rows[item_id]:
                self.rows[item_id].append(label)

    def refused(self, message: str, fallback: str = "identity", rows: tuple[str, ...] = ()) -> None:
        for label, problem in split_problems(message):
            item_id = ITEM_OF_LABEL.get(label, fallback)
            self.note(item_id, "missing" if ": required" in problem else "fail", problem, (label, *rows))

    def items(self) -> tuple[CheckItem, ...]:
        labels = dict(ITEMS)
        return tuple(CheckItem(item_id, labels[item_id], self.state[item_id], "; ".join(self.messages[item_id]), tuple(self.rows[item_id]))
                     for item_id, _ in ITEMS)


def setup_checklist(form: FormInput, root: Path | str | None = None, *, ccx: Callable[[], Path | None] = find_ccx,
                    tectonic: Callable[[], str | None] = find_tectonic, gmsh: Callable[[], str | None] = gmsh_available,
                    ) -> tuple[Checklist, FEModel | None, QualityField | None]:
    """Every item judged as far as the inputs allow. Returns the checklist, and the model and its mesh quality when the inputs build one."""
    root = Path(root) if root is not None else paths.LOCAL
    notes = _Notes()
    problems: list[str] = []
    values: Values | None = None
    named = None
    spec = None
    model: FEModel | None = None
    quality: QualityField | None = None
    try:
        values = check_form(form)
    except IntakeError as exc:
        problems.append(str(exc))
        notes.refused(str(exc))
    if values is not None:
        try:
            named = designation_for(values, root)
        except IntakeError as exc:
            problems.append(str(exc))
            notes.refused(str(exc), rows=("Material code", "Layup code"))
    if named is not None:
        try:
            spec = spec_from_values(values, named, form.path.name)
        except IntakeError as exc:
            problems.append(str(exc))
            concerned = tuple(form_rows_of(str(exc)))
            item_id = ITEM_OF_LABEL.get(concerned[0], "geometry") if concerned else "geometry"
            notes.note(item_id, "fail", str(exc).split(": the spec refuses the inputs: ", 1)[-1], concerned)
    plies = None
    if spec is not None:
        try:
            model = build_model(spec)
            plies = spec_plies(spec)  # the engine's plies: it refuses a lamina whose compliance is not positive
        except (SpecError, MeshError) as exc:
            problems.append(str(exc))
            notes.note("mesh", "fail", str(exc), ("Element size (mm)",))
        except ValueError as exc:
            model = None
            reason = str(exc).split("Value error, ", 1)[-1].split(" [type=", 1)[0]
            problems.append(reason)
            notes.note("material", "fail", f"our engine refuses these constants: {reason}",
                       ("Own material: E1 (MPa)", "Own material: E2 (MPa)", "Own material: G12 (MPa)", "Own material: nu12"))
    designation = named.name if named is not None else None
    exists, attempts = coupon_attempts(root, designation)

    if model is not None:
        units = spec.units
        lab = UNIT_LABEL[units]
        g, material, mesh, loading = spec.geometry, model.material, model.mesh, spec.loading
        length = lambda v: from_si(v, "length", units)  # noqa: E731
        notes.note("identity", "pass", f"{designation}, {TEST_CODES[spec.kind][1]}; " + (
            f"the coupon has {attempts} row{'s' if attempts != 1 else ''} in its attempt log, so this run is attempt {attempts + 1}" if exists
            else "a new coupon: its folder and case page are written when it runs"))
        # units: the form fixes mm, MPa and N; a modulus outside the engine's plausible range after conversion means the wrong unit
        moduli = (("E1", material.E1), ("E2", material.E2), ("G12", material.G12), ("G13", material.G13), ("G23", material.G23))
        suspicious = [name for name, value in moduli if not PLAUSIBLE_MODULUS_PA[0] <= value <= PLAUSIBLE_MODULUS_PA[1]]
        if suspicious:
            shown = ", ".join(f"{name} = {from_si(dict(moduli)[name], 'stress', units):g} {lab['stress']}" for name in suspicious)
            notes.note("units", "warn", f"{shown}: outside the plausible range for a modulus in {lab['stress']} (GPa typed as MPa, or the reverse?)",
                       tuple(f"Own material: {name} (MPa)" if name in ("E1", "E2", "G12") else f"{name} (MPa)" for name in suspicious))
        else:
            notes.note("units", "pass", f"every row in mm, MPa and N; the model is written in {units} and forces come out in {lab['force']}")
        # geometry
        size = f"{length(g.length):g} by {length(g.width):g} {lab['length']}"
        if g.tab_length:
            size += f", {length(g.tab_length):g} {lab['length']} tabs with a node row on each tab line"
        if g.hole_diameter:
            size += f", central hole of {length(g.hole_diameter):g} {lab['length']}"
        if model.bending:
            size += (f", {length(g.span):g} {lab['length']} span with {length(g.overhang):g} {lab['length']} overhangs"
                     + (f", {length(g.load_span):g} {lab['length']} loading span" if g.load_span else "") + ", a node row on each support and nose line")
        notes.note("geometry", "pass", size)
        # material
        has_strengths = material.strengths is not None
        notes.note("material", "pass", f"{material.name}: {material.source}; rights class {material.rights}; "
                   + ("strengths given" if has_strengths else "no strengths, so no failure criterion can be reported"))
        # laminate
        angles = full_angles(spec)
        thickness = length(sum(p.thickness_m for p in plies))
        symmetric = is_symmetric_layup(plies)
        if model.bending:
            kernel_words = "the flat shell kernel solves the bending" + ("" if symmetric else "; the layup is not symmetric, so stretching and bending couple (B is kept)")
        else:
            kernel_words = ("symmetric, so B = 0 and the membrane model applies" if symmetric
                            else "not symmetric (B does not vanish), so the flat shell kernel solves it with stretching and bending coupled")
        notes.note("laminate", "pass", f"{len(angles)} plies {layup_text(spec)}, {thickness:g} {lab['length']} thick; {kernel_words}")
        sets = model.node_sets
        held = [b for b in model.boundaries if b.value == 0.0]
        if model.bending:
            # constraints: w held along both support lines, the in-plane motion pinned at the centre node of each
            supports = [sets.get(name) for name in ("Support-Left", "Support-Right")]
            if any(s is None or s.size == 0 for s in supports):
                notes.note("constraints", "fail", "a support line holds no node; the support lines must fall on node rows", ("Support span (mm)", "Overhang (mm)"))
            elif not ({"Pin-Left", "Pin-Right"} <= set(sets)):
                notes.note("constraints", "fail", "the in-plane pins are missing; the coupon could slide as a rigid body", ("Support span (mm)",))
            else:
                notes.note("constraints", "pass", f"both support lines held along z ({supports[0].size} and {supports[1].size} nodes); the centre node of each "
                           "pins the in-plane motion without restraining the coupon's stretch or contraction; no rigid-body motion is left")
            amount = from_si(loading.value, "length", units)
            noses = ", ".join(model.nose_sets)
            notes.note("load", "pass", f"the loading nose{'s' if len(model.nose_sets) > 1 else ''} ({noses}) moved {abs(amount):g} {lab['length']} "
                       f"{'down onto' if amount < 0 else 'up from'} the coupon along z; the supports carry the reaction")
        else:
            # constraints: both grips present, the held one removing every in-plane rigid-body motion
            bottom, top = sets.get("Grip-Bottom"), sets.get("Grip-Top")
            if bottom is None or top is None or bottom.size == 0 or top.size == 0:
                notes.note("constraints", "fail", "a grip set is empty: no node lies within the tab length of an end", ("Tab length (mm)", "Grip region"))
            elif not any(b.dof_first <= 1 and b.dof_last >= 2 for b in held):
                notes.note("constraints", "fail", "no grip holds both in-plane directions; the coupon could move as a rigid body", ("Grip kind",))
            else:
                how = "through a reference point at each end" if model.couplings else "node by node"
                notes.note("constraints", "pass", f"bottom grip held in every direction ({bottom.size} nodes), top grip held across the width "
                           f"({top.size} nodes), {how}; no rigid-body motion is left")
            # load
            amount = from_si(loading.value, "length" if loading.control == "displacement" else "force", units)
            unit = lab["length" if loading.control == "displacement" else "force"]
            notes.note("load", "pass", f"{loading.control} of {abs(amount):g} {unit} on the top grip along the coupon, {'a push' if amount < 0 else 'a pull'}")
        # mesh
        quality = element_quality(mesh.xy, mesh.corners)
        summary = quality_summary(quality)
        counts = f"{mesh.element_count} elements, {mesh.node_count} nodes ({mesh.mesher} mesh, order {mesh.order})"
        notes.note("mesh", "pass" if summary["acceptable"] else "warn", f"{counts}; {quality_words(summary)}"
                   + ("" if summary["acceptable"] else "; a mesh past a threshold still solves, but read the results near those elements with care"))
        if spec.mesh.mesher == "gmsh":
            version = gmsh()
            notes.note("mesh", "pass" if version else "fail", f"Gmsh {version} meshes the hole" if version else
                       "Gmsh is not installed: the open-hole mesh cannot be made (from fea/: uv sync --extra mesh)", ("Hole diameter (mm)",))
        # criterion
        criteria = list(spec.output.fpf_criteria)
        if not criteria:
            notes.note("criterion", "warn", "no failure criterion: first-ply failure will not be reported"
                       + ("" if has_strengths else " (the material has no strengths)"), ("Failure criterion",))
        else:
            bad = []
            for criterion in criteria:
                try:
                    check_criterion(plies, criterion, material.f12_star)
                except ValueError as exc:
                    bad.append(f"{criterion}: {exc}")
            if bad:
                notes.note("criterion", "fail", "; ".join(bad), ("Failure criterion", "Tsai-Wu interaction f12*"))
            else:
                notes.note("criterion", "pass", "first-ply failure by " + ", ".join(criteria)
                           + (f" with f12* = {material.f12_star:g}" if "tsai_wu" in criteria else ""))
        # probes
        names = [f"node {name} at ({length(mesh.xy[i, 0]):g}, {length(mesh.xy[i, 1]):g})" for name, i in model.probe_nodes.items()]
        names += [f"element {name}" for name in model.probe_elements]
        notes.note("probes", "pass", "results are read at " + ", ".join(names) + f" ({lab['length']})")
    # what is installed
    found = ccx()
    version = ccx_version(found) if found is not None else None
    if version:
        notes.note("solver", "pass", f"CalculiX {version} at {found}: the reference solver that checks our engine's result")
    else:
        notes.note("solver", "fail", "CalculiX not found: set ANISOTROPY_CCX or put ccx on PATH (docs/installation-fea-tools.md); the run tool refuses "
                   "to start without it")
    tectonic_path = tectonic()
    if tectonic_path:
        notes.note("document", "pass", f"Tectonic at {tectonic_path}: the package gets its PDF")
    else:
        notes.note("document", "warn", "Tectonic not found: the package is written without its PDF (run with pdf off)")

    items = notes.items()
    blocked = any(item.state in ("fail", "missing") for item in items)
    return Checklist(items, designation, exists, attempts, "blocked" if blocked else "ready", tuple(problems)), model, quality
