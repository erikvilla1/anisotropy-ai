"""The fibre tow test of ASTM D4018 (ADR-0074): the studio's tow rows and specimen list read, refused by row, judged against the standard,
and reduced by the engine to the strength, the chord modulus and their statistics.

"fibre tow tension" is a test on the coupon form's Test list, but no coupon: it has no spec, no mesh and no finite element model. The studio
sends its rows as one values file, like a coupon's (ADR-0046 amendment 2), with the specimens tested as a list; the Excel form has no rows
for it and refuses the word. Its rows are in the standard's own units, which are SI only (§1.5): N, g, m and mm, g/m, g/cm³, microstrain,
mm/min, MPa and GPa. They become SI where they are read, the engine (`anisotropy_engine.tow`) computes in SI, and the result is written
back in the units the standard reports (ADR-0002).

`read_tow` reads a values file; `check_tow` types every row and names every problem at once (ADR-0003); `tow_subject` gives the record the
D4018 profile judges; `tow_answer` returns the checklist the studio shows and, when nothing blocks, the result. Nothing here is a number of
its own: every quantity is the engine's, every judgement the profile's.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from anisotropy_engine import tow as engine

from . import forms
from .checks import CheckItem, Checklist
from .intake import FORM_VERSION, IntakeError
from .spec import TOW_TEST, test_name
from .standards import NONE, profile_of_word
from .standards.astm_d4018 import (DENSITY_SAMPLES, FIBRE_TYPES, KIND, NEAR_GRIP_AREAS, PROFILE, REPORT_ITEMS, TAB_WORDS, TowSubject,
                                   failure_words)
from .standards.conformance import Conformance, judge

# The standard's units into SI, where the rows are read; and back, where the result is written.
G, G_PER_M, G_PER_CM3, MM, MICRO, MPA, GPA, MM_PER_MIN = 1e-3, 1e-3, 1e3, 1e-3, 1e-6, 1e6, 1e9, 1e-3 / 60.0
REPORT_UNITS = {"force": "N", "strength": "MPa", "modulus": "GPa", "mul": "g/m", "density": "g/cm³", "area": "mm²", "strain": "microstrain",
                "length": "mm", "resin_content": "% by weight"}
SHARED = ("test", "standard", "filled_by", "date", "notes")  # the coupon form's rows the tow test reads too
STATUS_WORDS = ("valid", "rejected")


@dataclass(frozen=True)
class TowField:
    """A row of the tow test, shaped like a row of the coupon form for the studio; its label carries its unit, the standard's, which no
    Units row changes."""

    key: str
    label: str
    kind: str  # "text", "number", "whole", "list"
    help: str = ""
    required: bool = False
    default: Any = None
    words: tuple[str, ...] = ()
    at_least: float | None = None
    above: float | None = None
    unit: None = None  # no unit kind: the tow's rows are in the standard's units only

    def label_in(self, _units: str) -> str:
        return self.label


TOW_BLOCKS: tuple[tuple[str, tuple[TowField, ...]], ...] = (
    ("The fibre tow", (
        TowField("fibre", "Fibre", "text", "the fibre as its maker names it, with its filament count and sizing, e.g. T700SC-12000-50C; it "
                 "identifies the samples tested (§13.1.3.1)", required=True),
        TowField("fibre_type", "Fibre type", "list", "carbon or graphite, the fibres D4018 covers (§1.1); other for any other fibre, which lies "
                 "outside it", required=True, words=FIBRE_TYPES),
        TowField("lot", "Lot or spool", "text", "the lot, spool or batch the samples came from, for traceability (§13.1.3.1)"),
        TowField("filaments", "Filaments per bundle", "whole", "the filament count of one bundle, e.g. 12000 for a 12K tow", above=0),
        TowField("bundles", "Bundles per specimen", "whole", "how many bundles were combined into one specimen: 1, or more only for a tow of "
                 "3000 filaments or fewer (§8.3)", required=True, default=1, at_least=1),
    )),
    ("Mass per unit length and density (§8.1, §8.2, §12.1, §12.2)", (
        TowField("mul", "Mass per unit length (g/m)", "number", "the sized fibre's mass per unit length, e.g. 0.800, or blank to compute it from the "
                 "MUL specimen's mass and length (Eq 1)", above=0),
        TowField("mul_mass", "MUL specimen mass (g)", "number", "the mass of the length of sized fibre weighed, e.g. 0.8012", above=0),
        TowField("mul_length", "MUL specimen length (m)", "number", "the length weighed, at least 1 m (§8.1), e.g. 1.000", above=0),
        TowField("density_sample", "Density measured on", "list", "the fibre the density was measured on: desized or unsized fibre is preferred "
                 "(§4.3), and a sized fibre's density is corrected by k_c (§12.2.2)", required=True, words=DENSITY_SAMPLES),
        TowField("fibre_density", "Measured density (g/cm³)", "number", "the density measured on that fibre, e.g. 1.80", required=True, above=0),
        TowField("density_correction", "Sizing correction k_c (g/cm³)", "number", "for a sized fibre only: the correction found from ten paired "
                 "tests of sized and desized fibre (§12.2.2), or blank for none"),
    )),
    ("The impregnated strand (§10.3, §12.3.1)", (
        TowField("resin", "Resin", "text", "the resin and its hardener, e.g. a bisphenol A epoxy with diethyltoluene diamine (§13.1.3.5)"),
        TowField("resin_strain", "Resin strain to failure (microstrain)", "number", "the consolidated resin's strain to failure, at least twice "
                 "the fibre's (§4.5), e.g. 50000", above=0),
        TowField("impregnation", "Impregnation apparatus", "text", "how the fibre was impregnated, e.g. a dip bath and a die (§13.1.3.5)"),
        TowField("cure", "Consolidation and cure", "text", "the cure cycle, held under tension, e.g. 2 h at 120 °C (§13.1.3.5)"),
        TowField("mul_impregnated", "Impregnated mass per unit length (g/m)", "number", "MUL_i, the impregnated and consolidated strand's mass "
                 "per unit length, for the resin content (Eq 3), or give the resin content instead", above=0),
        TowField("resin_content", "Resin content (% by weight)", "number", "the resin content when it was measured another way, or blank "
                 "when MUL_i is given", above=0),
    )),
    ("The tensile test (§8.3, §11.3)", (
        TowField("tow_gauge_length", "Gauge length (mm)", "number", "the free length between the tabs, or between the grips of an untabbed "
                 "specimen: 150 mm ± 5 mm (§8.3)", required=True, above=0),
        TowField("tow_tabs", "Tabs", "list", "the tabs on the ends, or none for a specimen gripped directly (§6.1.3)", required=True, words=TAB_WORDS),
        TowField("speed", "Machine speed (mm/min)", "number", "the crosshead speed, at most 250 mm/min (§11.3.2)", above=0),
        TowField("machine", "Testing machine and extensometer", "text", "the tensile testing apparatus (§13.1.3.6)"),
        TowField("facility", "Test facility", "text", "where the tests were run (§13.1.3.3)"),
        TowField("failure_strain", "Typical strain at failure (microstrain)", "number", "the product's typical strain at failure, e.g. 21000 for "
                 "2.1 %: it sets the chord strains (Table 2) and the largest preload (Table 1)", required=True, above=0),
        TowField("chord_lower", "Chord lower strain (microstrain)", "number", "the strain the force P_l was read at, or blank for Table 2's",
                 at_least=0),
        TowField("chord_upper", "Chord upper strain (microstrain)", "number", "the strain the force P_u was read at, or blank for Table 2's",
                 above=0),
    )),
    ("Datasheet values, for the planning loads", (
        TowField("datasheet_strength", "Datasheet strength (MPa)", "number", "the fibre's tensile strength on its datasheet, e.g. 4900: the "
                 "force to expect at failure", above=0),
        TowField("datasheet_modulus", "Datasheet modulus (GPa)", "number", "the fibre's tensile modulus on its datasheet, e.g. 230: the preload "
                 "and the chord forces to expect", above=0),
    )),
)
SPECIMEN_FIELDS: tuple[TowField, ...] = (
    TowField("id", "Specimen", "text", "its name or number, e.g. 1", required=True),
    TowField("max_force", "Maximum force (N)", "number", "P, the largest force before failure; blank for a specimen tested for modulus only",
             above=0),
    TowField("force_lower", "Force at lower strain (N)", "number", "P_l, read at the chord's lower strain; blank for strength only", at_least=0),
    TowField("force_upper", "Force at upper strain (N)", "number", "P_u, read at the chord's upper strain; blank for strength only", above=0),
    TowField("failure_code", "Failure code", "text", "the three letters of Fig. 1, the failure's type, area and location, e.g. LGM"),
    TowField("status", "Status", "list", "valid, or rejected with the reason in the note (§11.3.12): a rejected specimen is listed, not counted",
             required=True, default="valid", words=STATUS_WORDS),
    TowField("note", "Note", "text", "why it was rejected, or what was atypical about its failure (§13.1.3.8)"),
)
TOW_FIELDS: dict[str, TowField] = {f.key: f for _, fields in TOW_BLOCKS for f in fields}
SPECIMEN_FIELD: dict[str, TowField] = {f.key: f for f in SPECIMEN_FIELDS}
SPECIMENS = "Specimens"  # the label a problem with the list names

TOW_ITEMS = (  # the tow's checklist, in the order the studio lists it: id, label
    ("identity", "Who and which fibre"),
    ("fibre", "Mass, density and resin"),
    ("test", "Tensile set-up"),
    ("specimens", "Specimens tested"),
    ("standard", "Test standard"),
    ("results", "Results"),
)
ITEM_OF_ROW = {
    **{key: "identity" for key in ("test", "standard", "filled_by", "date", "notes", "fibre", "fibre_type", "lot", "filaments", "bundles")},
    **{key: "fibre" for key in ("mul", "mul_mass", "mul_length", "density_sample", "fibre_density", "density_correction", "resin", "resin_strain",
                                "impregnation", "cure", "mul_impregnated", "resin_content")},
    **{key: "test" for key in ("tow_gauge_length", "tow_tabs", "speed", "machine", "facility", "failure_strain", "chord_lower", "chord_upper",
                               "datasheet_strength", "datasheet_modulus")},
    "specimens": "specimens",
}
SHARED_LABELS = {"test": "Test", "standard": "Standard", "filled_by": "Filled in by", "date": "Date", "notes": "Notes to us"}
assert set(ITEM_OF_ROW) == set(TOW_FIELDS) | set(SHARED) | {"specimens"}


def label_of(key: str) -> str:
    """The label a problem names: a tow row's, a shared row's as the coupon form labels it, or the specimen list's."""
    if key == "specimens":
        return SPECIMENS
    return TOW_FIELDS[key].label if key in TOW_FIELDS else SHARED_LABELS[key]


# --------------------------------------------------------------------------------------------- reading


@dataclass(frozen=True)
class TowInput:
    """A tow values file as read: the cells by row key, as typed, and the specimens, each a dict of its cells."""

    path: Path
    cells: dict[str, Any]
    specimens: tuple[dict[str, Any], ...]


def is_tow(data: dict) -> bool:
    """Whether a values object states the fibre tow test."""
    return isinstance(data, dict) and str(data.get("test", "")).strip().lower() == TOW_TEST


def read_tow(path: Path | str) -> TowInput:
    """A tow values file: one JSON object of the tow's rows by key, the shared rows (test, standard, who, date, notes), `form_version`, which
    must be the current form's, and `specimens`, a list of objects by the specimen rows' keys. An unknown key is refused by name (ADR-0003)."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntakeError(f"{path.name}: not a values file ({exc})") from None
    if not isinstance(data, dict):
        raise IntakeError(f"{path.name}: a values file is one JSON object of the rows by key")
    data = dict(data)
    version = data.pop("form_version", None)
    if str(version) != FORM_VERSION:
        raise IntakeError(f"{path.name}: form_version {version!r} is not the current form's, {FORM_VERSION}; the tow's rows follow its definition")
    if not is_tow(data):
        raise IntakeError(f"{path.name}: Test: {data.get('test')!r} is not {TOW_TEST}; a coupon's values are checked by the setup check")
    specimens = data.pop("specimens", [])
    if not isinstance(specimens, list) or not all(isinstance(s, dict) for s in specimens):
        raise IntakeError(f"{path.name}: specimens must be a list of objects, one per specimen, by the specimen rows' keys")
    unknown = sorted(key for key in data if key not in TOW_FIELDS and key not in SHARED)
    if unknown:
        raise IntakeError(f"{path.name}: unknown keys {', '.join(unknown)}; the keys are the tow's rows ({', '.join(TOW_FIELDS)}) and "
                          f"{', '.join(SHARED)}")
    for n, specimen in enumerate(specimens, start=1):
        extra = sorted(key for key in specimen if key not in SPECIMEN_FIELD)
        if extra:
            raise IntakeError(f"{path.name}: specimen {n}: unknown keys {', '.join(extra)}; the keys are {', '.join(SPECIMEN_FIELD)}")
    blank = lambda v: v is None or (isinstance(v, str) and not v.strip())  # noqa: E731
    cells = {key: None if blank(data.get(key)) else data.get(key) for key in (*SHARED, *TOW_FIELDS)}
    rows = tuple({key: None if blank(s.get(key)) else s.get(key) for key in SPECIMEN_FIELD} for s in specimens)
    return TowInput(path, cells, rows)


# --------------------------------------------------------------------------------------------- checking


@dataclass(frozen=True)
class TowSpecimen:
    id: str
    max_force: float | None  # N
    force_lower: float | None  # N
    force_upper: float | None  # N
    failure_code: str | None  # three capital letters of Fig. 1
    status: str
    note: str

    @property
    def valid(self) -> bool:
        return self.status == "valid"

    @property
    def has_chord(self) -> bool:
        return self.force_lower is not None and self.force_upper is not None


@dataclass(frozen=True)
class TowValues:
    """The tow's rows typed, in SI."""

    standard: str  # a designation, or "none"
    filled_by: str
    day: str
    notes: str
    fibre: str
    fibre_type: str
    lot: str
    filaments: int | None
    bundles: int
    mul: float | None  # kg/m, as given
    mul_mass: float | None  # kg
    mul_length: float | None  # m
    density_sample: str
    fibre_density: float  # kg/m^3, as measured
    density_correction: float | None  # kg/m^3
    resin: str
    resin_strain: float | None  # absolute
    impregnation: str
    cure: str
    mul_impregnated: float | None  # kg/m
    resin_content: float | None  # percent by weight, as given
    gauge_length: float  # m
    tabs: str
    speed: float | None  # m/s
    machine: str
    facility: str
    failure_strain: float  # absolute
    chord_lower: float | None  # absolute, as given
    chord_upper: float | None
    datasheet_strength: float | None  # Pa
    datasheet_modulus: float | None  # Pa
    specimens: tuple[TowSpecimen, ...]


@dataclass(frozen=True)
class Problem:
    row: str  # a row key, or "specimens"
    message: str  # names the row by its label

    @property
    def missing(self) -> bool:
        return ": required" in self.message


class TowRefused(IntakeError):
    """A tow record that cannot be read: every problem, each with its row."""

    def __init__(self, problems: list[Problem]):
        super().__init__("; ".join(p.message for p in problems))
        self.problems = tuple(problems)


def check_tow(form: TowInput) -> TowValues:
    """The typed rows of a tow record, in SI; refused with every problem named, each by its row."""
    cells, problems = form.cells, []

    def problem(key: str, message: str) -> None:
        problems.append(Problem(key, f"{label_of(key)}: {message}"))

    def text(key: str, required: bool = False) -> str:
        value = forms.text_of(cells.get(key))
        if not value and (required or (key in TOW_FIELDS and TOW_FIELDS[key].required)):
            problem(key, "required")
        return value

    def number_of(value: Any, f: TowField, say) -> float | int | None:
        if value is None:
            if f.required:
                say("required")
            return None
        try:
            found = float(str(value).replace(",", ".")) if isinstance(value, str) else float(value)
        except (TypeError, ValueError):
            say(f"a number is needed, not {forms.text_of(value)!r}")
            return None
        if not math.isfinite(found):
            say(f"a finite number is needed, not {forms.text_of(value)!r}")
            return None
        if f.kind == "whole" and found != int(found):
            say(f"a whole number is needed, not {found:g}")
            return None
        if f.above is not None and not found > f.above:
            say(f"must be greater than {f.above:g}, not {found:g}")
            return None
        if f.at_least is not None and not found >= f.at_least:
            say(f"must be at least {f.at_least:g}, not {found:g}")
            return None
        return int(found) if f.kind == "whole" else found

    def number(key: str) -> float | int | None:
        return number_of(cells.get(key), TOW_FIELDS[key], lambda m: problem(key, m))

    def word_of(value: Any, f: TowField, say) -> str:
        typed = forms.text_of(value).lower()
        if not typed:
            if f.required:
                say(f"required; one of {', '.join(f.words)}")
            return ""
        known = next((w for w in f.words if w == typed), None)
        if known is None:
            say(f"{forms.text_of(value)!r} is not one of {', '.join(f.words)}")
        return known or ""

    def word(key: str) -> str:
        return word_of(cells.get(key), TOW_FIELDS[key], lambda m: problem(key, m))

    # the shared rows
    filled_by, notes = text("filled_by", required=True), text("notes")
    day = text("date", required=True)
    if day:
        try:
            day = date.fromisoformat(day).isoformat()
        except ValueError:
            problem("date", f"{day!r} is not a date (write YYYY-MM-DD)")
    standard = forms.text_of(cells.get("standard")) or NONE
    profile = profile_of_word(standard)
    if profile is None and standard.lower() != NONE:
        problem("standard", f"{standard!r} is not {NONE} or {PROFILE.designation}")
    elif profile is not None and KIND not in profile.kinds:
        problem("standard", f"{profile.designation} covers {', '.join(test_name(k) for k in profile.kinds)}, not {TOW_TEST}; pick {NONE} or "
                f"{PROFILE.designation}")
    standard = profile.designation if profile is not None else NONE

    # the fibre
    fibre, fibre_type, lot = text("fibre"), word("fibre_type"), text("lot")
    filaments, bundles = number("filaments"), number("bundles")
    mul, mul_mass, mul_length = number("mul"), number("mul_mass"), number("mul_length")
    given = [cells.get(k) is not None for k in ("mul", "mul_mass", "mul_length")]
    if given[0] and (given[1] or given[2]):
        problem("mul", "give the mass per unit length or the MUL specimen's mass and length, not both")
    elif not given[0] and not (given[1] and given[2]):
        if given[1] or given[2]:
            problem("mul_mass" if not given[1] else "mul_length", "required with the other; give the MUL specimen's mass and its length")
        else:
            problem("mul", "required, or the MUL specimen's mass and length (Eq 1)")
    density_sample, density = word("density_sample"), number("fibre_density")
    correction = number("density_correction")
    if correction is not None and density_sample and density_sample != "sized":
        problem("density_correction", f"belongs to a density measured on sized fibre, not {density_sample} fibre; leave it blank")
    if density is not None and correction is not None and density - correction <= 0:
        problem("density_correction", f"{correction:g} g/cm³ leaves no positive density from {density:g} g/cm³")
    resin, impregnation, cure = text("resin"), text("impregnation"), text("cure")
    resin_strain = number("resin_strain")
    mul_i, resin_content = number("mul_impregnated"), number("resin_content")
    if mul_i is not None and resin_content is not None:
        problem("resin_content", "give the impregnated mass per unit length or the resin content, not both")
    fibre_mul = mul if mul is not None else (mul_mass / mul_length if mul_mass is not None and mul_length is not None else None)
    if mul_i is not None and fibre_mul is not None and bundles and mul_i <= fibre_mul * bundles:
        problem("mul_impregnated", f"{mul_i:g} g/m is not more than the fibre's {fibre_mul * bundles:.4g} g/m; the strand carries the resin")
    if resin_content is not None and resin_content >= 100:
        problem("resin_content", f"must be below 100 %, not {resin_content:g}")

    # the tensile test
    gauge, tabs, speed = number("tow_gauge_length"), word("tow_tabs"), number("speed")
    machine, facility = text("machine"), text("facility")
    failure_strain = number("failure_strain")
    chord_lower, chord_upper = number("chord_lower"), number("chord_upper")
    if (cells.get("chord_lower") is None) != (cells.get("chord_upper") is None):
        problem("chord_upper" if cells.get("chord_upper") is None else "chord_lower", "give both chord strains, or neither for Table 2's")
    if chord_lower is not None and chord_upper is not None and not chord_upper > chord_lower:
        problem("chord_upper", f"must be greater than the lower strain, {chord_lower:g}, not {chord_upper:g}")
    strength, modulus = number("datasheet_strength"), number("datasheet_modulus")

    # the specimens
    specimens: list[TowSpecimen] = []
    seen: set[str] = set()
    if not form.specimens:
        problem("specimens", "required; at least one specimen with its forces")
    for n, row in enumerate(form.specimens, start=1):
        name = forms.text_of(row.get("id")) or str(n)
        say = lambda field_label: (lambda m: problem("specimens", f"specimen {name}, {field_label}: {m}"))  # noqa: E731
        if not forms.text_of(row.get("id")):
            say(SPECIMEN_FIELD["id"].label)("required")
        elif name in seen:
            say(SPECIMEN_FIELD["id"].label)(f"{name!r} names two specimens; give each its own")
        seen.add(name)
        values = {key: number_of(row.get(key), SPECIMEN_FIELD[key], say(SPECIMEN_FIELD[key].label)) for key in ("max_force", "force_lower", "force_upper")}
        status = word_of(row.get("status"), SPECIMEN_FIELD["status"], say(SPECIMEN_FIELD["status"].label)) or "valid"
        code = forms.text_of(row.get("failure_code")).upper() or None
        if code is not None and failure_words(code) is None:
            say(SPECIMEN_FIELD["failure_code"].label)(f"{code!r} is not a code of Fig. 1 (type G, L, S, X or O; area I, A, W, G, P, V or U; "
                                                     "location B, T, M, V or U)")
            code = None
        lower, upper = values["force_lower"], values["force_upper"]
        if (row.get("force_lower") is None) != (row.get("force_upper") is None):
            say(SPECIMEN_FIELD["force_upper"].label if row.get("force_upper") is None else SPECIMEN_FIELD["force_lower"].label)(
                "give both chord forces, or neither for a specimen tested for strength only")
        elif lower is not None and upper is not None and not upper > lower:
            say(SPECIMEN_FIELD["force_upper"].label)(f"must be greater than the force at the lower strain, {lower:g} N, not {upper:g} N")
        if status == "valid" and row.get("max_force") is None and row.get("force_lower") is None and row.get("force_upper") is None:
            say(SPECIMEN_FIELD["max_force"].label)("required for a valid specimen, or its two chord forces")
        if status == "rejected" and not forms.text_of(row.get("note")):
            say(SPECIMEN_FIELD["note"].label)("required for a rejected specimen: why it was rejected (§11.3.12, §13.1.3.8)")
        specimens.append(TowSpecimen(name, values["max_force"], lower, upper, code, status, forms.text_of(row.get("note"))))

    if problems:
        raise TowRefused(problems)
    return TowValues(
        standard=standard, filled_by=filled_by, day=day, notes=notes, fibre=fibre, fibre_type=fibre_type, lot=lot, filaments=filaments,
        bundles=bundles, mul=None if mul is None else mul * G_PER_M, mul_mass=None if mul_mass is None else mul_mass * G, mul_length=mul_length,
        density_sample=density_sample, fibre_density=density * G_PER_CM3,
        density_correction=None if correction is None else correction * G_PER_CM3, resin=resin,
        resin_strain=None if resin_strain is None else resin_strain * MICRO, impregnation=impregnation, cure=cure,
        mul_impregnated=None if mul_i is None else mul_i * G_PER_M, resin_content=resin_content, gauge_length=gauge * MM, tabs=tabs,
        speed=None if speed is None else speed * MM_PER_MIN, machine=machine, facility=facility, failure_strain=failure_strain * MICRO,
        chord_lower=None if chord_lower is None else chord_lower * MICRO, chord_upper=None if chord_upper is None else chord_upper * MICRO,
        datasheet_strength=None if strength is None else strength * MPA, datasheet_modulus=None if modulus is None else modulus * GPA,
        specimens=tuple(specimens))


# --------------------------------------------------------------------------------------------- the numbers, by the engine


@dataclass(frozen=True)
class TowNumbers:
    """What the engine computes from the record, in SI."""

    mul: float  # kg/m of one bundle: given, or Eq 1
    specimen_mul: float  # kg/m of a specimen: the bundles' sum (our reading of §8.3)
    density: float  # kg/m^3: as measured, or Eq 2 for a sized sample
    area: float  # m^2 of a specimen's fibre
    resin_content: float | None  # percent: Eq 3, or as given
    chord_table: tuple[float, float]
    chord_used: tuple[float, float]
    preload: float
    strengths: dict[str, float]  # Pa, by valid specimen
    moduli: dict[str, float]  # Pa, by valid specimen
    rejected_strengths: dict[str, float]  # computed and listed, never counted (§11.3.12: every value recorded)
    rejected_moduli: dict[str, float]
    strength_stats: engine.SampleStatistics | None
    modulus_stats: engine.SampleStatistics | None
    planning: engine.PlanningLoads


def tow_numbers(v: TowValues) -> TowNumbers:
    mul = v.mul if v.mul is not None else engine.mass_per_unit_length(v.mul_mass, v.mul_length)
    density = engine.fibre_density(v.fibre_density, v.density_correction or 0.0) if v.density_sample == "sized" else v.fibre_density
    specimen_mul = mul * v.bundles
    rc = engine.resin_content(specimen_mul, v.mul_impregnated) if v.mul_impregnated is not None else v.resin_content
    table = engine.chord_strains(v.failure_strain)
    used = (v.chord_lower, v.chord_upper) if v.chord_lower is not None else table
    strengths, moduli, rejected_s, rejected_m = {}, {}, {}, {}
    for s in v.specimens:
        if s.max_force is not None:
            (strengths if s.valid else rejected_s)[s.id] = engine.tow_strength(s.max_force, density, specimen_mul)
        if s.has_chord:
            (moduli if s.valid else rejected_m)[s.id] = engine.tow_chord_modulus(s.force_lower, s.force_upper, used[0], used[1], density, specimen_mul)
    stats = lambda values: engine.sample_statistics(list(values)) if len(values) >= 2 else None  # noqa: E731
    return TowNumbers(mul=mul, specimen_mul=specimen_mul, density=density, area=engine.fibre_area(specimen_mul, density), resin_content=rc,
                      chord_table=table, chord_used=used, preload=engine.preload_strain(v.failure_strain), strengths=strengths, moduli=moduli,
                      rejected_strengths=rejected_s, rejected_moduli=rejected_m, strength_stats=stats(strengths.values()),
                      modulus_stats=stats(moduli.values()),
                      planning=engine.planning_loads(specimen_mul, density, v.failure_strain, v.datasheet_modulus, v.datasheet_strength))


# --------------------------------------------------------------------------------------------- the judgement, by the profile


def tow_subject(v: TowValues, numbers: TowNumbers) -> TowSubject:
    valid = [s for s in v.specimens if s.valid]
    coded = [s for s in valid if s.failure_code]
    return TowSubject(fibre_type=v.fibre_type, gauge_length=v.gauge_length, tabs=v.tabs,
                      strength_specimens=sum(1 for s in valid if s.max_force is not None), modulus_specimens=sum(1 for s in valid if s.has_chord),
                      valid=len(valid), coded=len(coded), near_grip=sum(1 for s in coded if s.failure_code[1] in NEAR_GRIP_AREAS),
                      bundles=v.bundles, filaments=v.filaments, failure_strain=v.failure_strain, chord_used=numbers.chord_used,
                      chord_table=numbers.chord_table, density_sample=v.density_sample, resin_strain=v.resin_strain,
                      mul_length=v.mul_length if v.mul is None else None, speed=v.speed, resin_content=numbers.resin_content)


def tow_conformance(subject: TowSubject) -> Conformance:
    """The record judged against D4018: every requirement met, a deviation, an advisory, a note, the laboratory's, or not applicable."""
    return Conformance(PROFILE, subject, None, tuple(judge(r, subject) for r in PROFILE.requirements), checked="test record",
                       judged_by="the record shows")


# --------------------------------------------------------------------------------------------- the answer


def _stats(found: engine.SampleStatistics | None, scale: float) -> dict | None:
    if found is None:
        return None
    return {"n": found.n, "mean": found.mean / scale, "sd": found.standard_deviation / scale, "cv": found.cv_percent}


def tow_result(v: TowValues, numbers: TowNumbers, conformance: Conformance | None) -> dict:
    """The result in the standard's report units: the fibre, each specimen, the statistics, the planning loads and, under a standard, the
    judgement and the report items the record gives."""
    p = numbers.planning
    specimens = []
    for s in v.specimens:
        strength = numbers.strengths.get(s.id, numbers.rejected_strengths.get(s.id))
        modulus = numbers.moduli.get(s.id, numbers.rejected_moduli.get(s.id))
        specimens.append({"id": s.id, "status": s.status, "note": s.note, "max_force": s.max_force, "force_lower": s.force_lower,
                          "force_upper": s.force_upper, "strength": None if strength is None else strength / MPA,
                          "modulus": None if modulus is None else modulus / GPA, "failure_code": s.failure_code,
                          "failure_words": None if s.failure_code is None else failure_words(s.failure_code)})
    filled = {"fibre": v.fibre, "lot": v.lot, "date": v.day, "facility": v.facility, "filled_by": v.filled_by, "impregnation": v.impregnation,
              "resin": v.resin, "cure": v.cure, "machine": v.machine}
    report = []
    for clause, item, rows in REPORT_ITEMS:
        if rows == ("specimens",):
            shown = bool(numbers.strengths or numbers.moduli)
        elif not rows:
            shown = conformance is not None
        else:
            shown = all(filled.get(row) for row in rows)
        report.append({"clause": clause, "item": item, "rows": list(rows), "shown": shown})
    return {
        "test": TOW_TEST, "designation": None if conformance is None else PROFILE.designation, "fibre": v.fibre, "lot": v.lot or None,
        "units": dict(REPORT_UNITS),
        "fibre_properties": {
            "mul": numbers.mul / G_PER_M, "mul_from": "given" if v.mul is not None else "Eq 1",
            "bundles": v.bundles, "specimen_mul": numbers.specimen_mul / G_PER_M,
            "density": numbers.density / G_PER_CM3, "density_from": "Eq 2" if v.density_sample == "sized" else f"measured on {v.density_sample} fibre",
            "area": numbers.area / MM**2,
            "resin_content": numbers.resin_content,
            "resin_content_from": None if numbers.resin_content is None else ("Eq 3" if v.mul_impregnated is not None else "given"),
        },
        "strains": {"failure": v.failure_strain / MICRO, "preload": numbers.preload / MICRO,
                    "chord": [numbers.chord_used[0] / MICRO, numbers.chord_used[1] / MICRO],
                    "chord_table": [numbers.chord_table[0] / MICRO, numbers.chord_table[1] / MICRO],
                    "chord_from": "Table 2" if v.chord_lower is None else "given"},
        "specimens": specimens,
        "strength": _stats(numbers.strength_stats, MPA), "modulus": _stats(numbers.modulus_stats, GPA),
        "counts": {"specimens": len(v.specimens), "valid": sum(1 for s in v.specimens if s.valid), "strength": len(numbers.strengths),
                   "modulus": len(numbers.moduli)},
        "planning": {"preload_force": p.preload_force, "force_lower": p.force_lower, "force_upper": p.force_upper, "failure_force": p.failure_force,
                     "from": [w for w, given in (("datasheet modulus", v.datasheet_modulus), ("datasheet strength", v.datasheet_strength)) if given]},
        "conformance": None if conformance is None else conformance.as_dict(),
        "report": report,
        "note": "Strength and chord modulus divide by the fibre's area, MUL / density (Eqs 4 and 5); the chord strains are absolute in the "
                "engine (ADR-0074: the standard's factor B gives GPa only with absolute strains). Nothing here is a model of the tow.",
    }


def tow_answer(path: Path | str) -> dict:
    """The checklist the studio shows for a tow values file and, when nothing blocks, the result: `{"checklist": ..., "result": ...}`."""
    states = {item_id: "pending" for item_id, _ in TOW_ITEMS}
    messages: dict[str, list[str]] = {item_id: [] for item_id, _ in TOW_ITEMS}
    rows: dict[str, list[str]] = {item_id: [] for item_id, _ in TOW_ITEMS}
    requirements: tuple[dict, ...] = ()
    severity = {"pending": -1, "pass": 0, "warn": 1, "fail": 2, "missing": 2}

    def note(item_id: str, state: str, message: str = "", label: str = "") -> None:
        if severity[state] > severity[states[item_id]]:
            states[item_id] = state
        if message:
            messages[item_id].append(message)
        if label and label not in rows[item_id]:
            rows[item_id].append(label)

    problems: tuple[str, ...] = ()
    result = None
    try:
        values = check_tow(read_tow(path))
    except TowRefused as refused:
        for p in refused.problems:
            note(ITEM_OF_ROW[p.row], "missing" if p.missing else "fail", p.message, label_of(p.row))
        problems = tuple(p.message for p in refused.problems)
        for item_id in ("identity", "fibre", "test", "specimens"):
            note(item_id, "pass")  # every problem is named at once, so a part with none passed
        values = None
    except IntakeError as exc:
        note("identity", "fail", str(exc))
        problems = (str(exc),)
        values = None
    if values is not None:
        for item_id in ("identity", "fibre", "test", "specimens"):
            note(item_id, "pass")
        try:
            numbers = tow_numbers(values)
        except ValueError as exc:  # the engine's refusal of a value the rows let through
            note("results", "fail", f"the engine refused the record: {exc}")
            problems = (str(exc),)
        else:
            conformance = tow_conformance(tow_subject(values, numbers)) if values.standard != NONE else None
            if conformance is None:
                note("standard", "pass", "no standard named: the record is reduced by D4018's equations and judged against no clause")
            else:
                requirements = tuple(j.as_dict() for j in conformance.judged)
                note("standard", "warn" if conformance.deviations or conformance.advisories else "pass", conformance.words(),
                     *(label_of(r) for r in conformance.deviation_rows()[:1]))
            note("results", "pass", f"{len(numbers.strengths)} strength{'s' if len(numbers.strengths) != 1 else ''} and {len(numbers.moduli)} "
                 f"modul{'i' if len(numbers.moduli) != 1 else 'us'} from the valid specimens")
            result = tow_result(values, numbers, conformance)
    items = tuple(CheckItem(item_id, label, states[item_id], "; ".join(messages[item_id]), tuple(rows[item_id]),
                            requirements if item_id == "standard" else ()) for item_id, label in TOW_ITEMS)
    blocked = any(item.state in ("fail", "missing") for item in items)
    checklist = Checklist(items, None, False, 0, "blocked" if blocked else "ready", problems)
    return {"checklist": checklist.as_dict(), "result": None if blocked else result}
