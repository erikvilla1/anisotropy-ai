"""A plate followed as its shape changes, solved by CalculiX (ADR-0142; fea/docs/theory.md, Section 14).

Our own kernel is linear: it writes equilibrium on the shape the plate had before the load. A plate that deflects by its own thickness
or more carries part of the load by stretching, and only a solve that follows the shape sees that. This module asks CalculiX for it:
the spec's eight-node twin is written with a large-displacement step (`*STEP, NLGEOM`), CalculiX raises the load in increments it sizes
itself, and the answer is read back as a history, one level per fraction of the load. No number here is computed by our kernel, so no
second solver of ours checks it; what stands behind it are the cases of `fea/checks/large_displacement_cases/`, problems with exact or
published answers that CalculiX is run on by `tests/test_large_displacement.py`.

A case is a TOML file:

    title = "..."
    source = "where the expected numbers come from"

    [follow]                              # how the load is raised
    first = 0.02                          # the first increment, a fraction of the load
    at = [0.1, 0.2, 0.5, 1.0]             # the fractions of the load the answer is read at

    [small_load]                          # optional: the same model under `factor` times its load, where following the shape changes nothing
    factor = 0.001
    tolerance = 1e-4                      # the large-displacement answer against CalculiX's own linear one, on every reading below
    kernel_tolerance = 0.01               # and against our kernel's linear answer, on the displacement readings (a different element)

    [[expected]]                          # one reading; its values are in the plate's own units, one per fraction of `at`
    name = "centre deflection over the thickness"
    what = "displacement"                 # of a node probe; "reaction": the total force on a support region; "strain": of an element probe
    of = "centre"                         # the probe, or the region
    component = 3                         # displacement and reaction: 1 x, 2 y, 3 z; strain: 1 xx, 2 yy, 3 zz, 4 xy, 5 xz, 6 yz
    height = -0.2887                      # strain only: the height above the middle of the plate of the points read (their mean is compared)
    scale = 0.5                           # the reading times this is what `values` holds (here 1 / thickness); 1 when absent
    values = [0.237, 0.471]
    tolerance = 0.025                     # relative

    [plate]                               # the plate, as a spec of kind "plate" (`spec.py`), its tables one level down: [plate.geometry], ...

The strain CalculiX prints in such a step is the Lagrangian strain in the axes the plate had before the load; the stress it prints is the
true stress in the fixed global axes, which a section that has turned no longer shares (Section 14). A ply's stresses in its own axes
therefore come from the strains, through the ply's stiffness, and not from the printed stress components.
"""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .calculix import CalculixResult, DatResults, parse_dat, run_calculix
from .femodel import FEModel, build_model
from .spec import CouponSpec, SpecError, spec_from_table, to_si
from .units import deck_units_of, unit_factors
from .write_calculix import LargeDisplacement, write_calculix

READINGS = ("displacement", "reaction", "strain")


class LargeDisplacementError(ValueError):
    """A case that cannot be read, or a history that lacks what was asked of it."""


@dataclass(frozen=True)
class Level:
    """The model at one fraction of its load, in SI: the total force on each support region (N), the displacement of each node probe
    (m), and at each element probe's integration points the place before the load (m), the Lagrangian strain and the true stress (Pa),
    components xx, yy, zz, xy, xz, yz in the fixed global axes (or the ply's own, when the spec does not ask for global ones)."""

    fraction: float
    reaction: dict[str, np.ndarray]
    displacement: dict[str, np.ndarray]
    points: dict[str, np.ndarray]
    strain: dict[str, np.ndarray]
    stress: dict[str, np.ndarray]


@dataclass(frozen=True)
class History:
    """What a followed solve gave: the levels in the order the load rose, and the run they were read from."""

    levels: tuple[Level, ...]
    run: CalculixResult | None = None

    def at(self, fraction: float) -> Level:
        for level in self.levels:
            if abs(level.fraction - fraction) <= 1e-6:  # CalculiX prints the fraction to seven digits
                return level
        raise LargeDisplacementError(f"no level at {fraction:g} of the load; levels at " + ", ".join(f"{lv.fraction:g}" for lv in self.levels))


@dataclass(frozen=True)
class Reading:
    name: str
    what: str
    of: str
    component: int
    values: tuple[float, ...]
    tolerance: float
    scale: float = 1.0
    height: float | None = None


@dataclass(frozen=True)
class Case:
    name: str
    title: str
    source: str
    spec: CouponSpec  # in SI
    units: str  # the system the plate is stated in, and the readings' values
    follow: LargeDisplacement
    readings: tuple[Reading, ...]
    small_load: dict | None


def eight_node_twin(spec: CouponSpec) -> CouponSpec:
    """The same plate on eight-node elements, the only shell CalculiX takes a layup on."""
    return spec if spec.mesh.element_order == 2 else spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"element_order": 2})})


def under(spec: CouponSpec, factor: float) -> CouponSpec:
    """The same plate under `factor` times everything that loads it: its forces, its pressures and the values its supports are moved by."""
    loads = [ld.model_copy(update={key: getattr(ld, key) * factor for key in ("total", "pressure") if getattr(ld, key) is not None}) for ld in spec.loads]
    supports = [s.model_copy(update={"value": s.value * factor}) for s in spec.supports]
    return spec.model_copy(update={"loads": loads, "supports": supports})


def read_history(model: FEModel, dat: DatResults) -> tuple[Level, ...]:
    """The levels a `.dat` holds, by the fraction of the load each block was printed at, in SI. A run that stopped before the whole
    load leaves the levels it reached."""
    f = unit_factors(deck_units_of(model.spec.units))  # the .dat is in the deck's system
    fractions = sorted({block.time for block in dat.blocks})
    levels = []
    for fraction in fractions:
        reaction, displacement, points, strain, stress = {}, {}, {}, {}, {}
        for block in dat.blocks:
            if block.time != fraction:
                continue
            probe = block.set_name[len("Probe-"):] if block.set_name.upper().startswith("PROBE-") else None
            if block.quantity == "total force":
                reaction[block.set_name] = block.values[0] * f["force"]
            elif block.quantity == "displacements" and probe is not None:
                displacement[probe] = block.values[0] * f["length"]
            elif block.quantity == "global coordinates" and probe is not None:
                points[probe] = block.values * f["length"]
            elif block.quantity == "strains" and probe is not None:
                strain[probe] = block.values
            elif block.quantity == "stresses" and probe is not None:
                stress[probe] = block.values * f["stress"]
        levels.append(Level(float(fraction), _by_name(reaction, model.support_sets), _by_name(displacement, model.probe_nodes),
                            _by_name(points, model.probe_elements), _by_name(strain, model.probe_elements), _by_name(stress, model.probe_elements)))
    return tuple(levels)


def _by_name(found: dict[str, np.ndarray], names) -> dict[str, np.ndarray]:
    """CalculiX prints a set's name in capitals; the model's own spelling is given back."""
    upper = {name.upper(): name for name in names}
    return {upper.get(key.upper(), key): values for key, values in found.items()}


def follow(spec: CouponSpec, large: LargeDisplacement, workdir: Path | str, ccx: str | Path | None = None, timeout_s: float = 600.0,
           job: str = "followed") -> History:
    """Solve the plate in CalculiX with its shape followed and read the history. `spec` is in SI (`load_spec`, or a case's)."""
    model = build_model(eight_node_twin(spec))
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    deck = workdir / f"{job}.inp"
    deck.write_text(write_calculix(model, large=large), encoding="utf-8", newline="\n")
    run = run_calculix(deck, ccx=ccx, timeout_s=timeout_s)
    return History(read_history(model, parse_dat(run.dat_text)), run)


def reading_of(level: Level, reading: Reading, spec: CouponSpec, units: str) -> float:
    """One reading of a level, in the units its case states the plate in, times the reading's scale."""
    f = unit_factors(units)
    try:
        if reading.what == "displacement":
            value = level.displacement[reading.of][reading.component - 1] / f["length"]
        elif reading.what == "reaction":
            value = level.reaction[reading.of][reading.component - 1] / f["force"]
        else:
            z = level.points[reading.of][:, 2] / f["length"]
            rows = np.flatnonzero(np.abs(z - reading.height) <= 1e-4 * max(abs(reading.height), np.abs(z).max()))
            if rows.size == 0:
                raise LargeDisplacementError(f"{reading.name}: no integration point of {reading.of} at height {reading.height:g}; heights printed: "
                                             + ", ".join(f"{v:.6g}" for v in sorted(set(np.round(z, 9)))))
            value = float(level.strain[reading.of][rows, reading.component - 1].mean())
    except KeyError:
        raise LargeDisplacementError(f"{reading.name}: the run printed no {reading.what} of {reading.of!r} at {level.fraction:g} of the load") from None
    return float(value) * reading.scale


def load_case(path: Path | str) -> Case:
    """Read a case file (the format is at the top of this module); the plate is validated as any spec is and converted to SI."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    missing = [key for key in ("title", "source", "follow", "expected", "plate") if key not in data]
    if missing:
        raise LargeDisplacementError(f"{path.name}: missing {', '.join(missing)}")
    try:
        written = spec_from_table(dict(data["plate"]), hashlib.sha256(text.encode("utf-8")).hexdigest(), str(path))
    except SpecError as exc:
        raise LargeDisplacementError(f"{path.name}: [plate] {exc}") from None
    if written.kind != "plate":
        raise LargeDisplacementError(f"{path.name}: [plate] is of kind {written.kind!r}; a large-displacement case is a plate")
    at = tuple(float(v) for v in data["follow"].get("at", ()))
    if not at:
        raise LargeDisplacementError(f"{path.name}: [follow] names no fraction of the load to read the answer at")
    large = LargeDisplacement(first=float(data["follow"]["first"]), at=at)
    readings = []
    for entry in data["expected"]:
        unknown = set(entry) - {"name", "what", "of", "component", "height", "scale", "values", "tolerance"}
        if unknown:
            raise LargeDisplacementError(f"{path.name}: a reading has {', '.join(sorted(unknown))}, which no reading takes")
        reading = Reading(name=entry["name"], what=entry["what"], of=entry["of"], component=int(entry["component"]),
                          values=tuple(float(v) for v in entry["values"]), tolerance=float(entry["tolerance"]), scale=float(entry.get("scale", 1.0)),
                          height=float(entry["height"]) if "height" in entry else None)
        if reading.what not in READINGS:
            raise LargeDisplacementError(f"{path.name}: {reading.name}: a reading is one of {', '.join(READINGS)}; got {reading.what!r}")
        if len(reading.values) != len(at):
            raise LargeDisplacementError(f"{path.name}: {reading.name}: {len(reading.values)} values for {len(at)} fractions of the load")
        if not 1 <= reading.component <= (6 if reading.what == "strain" else 3):
            raise LargeDisplacementError(f"{path.name}: {reading.name}: component {reading.component} is not one of a {reading.what}")
        if (reading.what == "strain") != (reading.height is not None):
            raise LargeDisplacementError(f"{path.name}: {reading.name}: a strain reading states the height of its points, and no other reading does")
        readings.append(reading)
    return Case(name=path.stem, title=data["title"], source=data["source"], spec=to_si(written), units=written.units, follow=large,
                readings=tuple(readings), small_load=data.get("small_load"))
