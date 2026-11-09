"""ASTM D4018: tensile properties of a resin-impregnated carbon or graphite fibre tow, as a profile (ADR-0073).

Read from the D4018-23 copy licensed to UC San Diego. Each value below carries its clause; the wording is ours. The standard is in SI only
(§1.5). It judges a test record, not a model: the fibre, its mass per unit length and density, the impregnated strand, the tensile set-up
and the specimens tested. The record is a `TowSubject`, in SI; the numbers (strength, chord modulus, statistics) are the engine's
(`anisotropy_engine.tow`), and the fea package's `tow_test` reads the studio's rows into both.

Our readings, recorded as readings in ADR-0073:
- §8.3 lets a tow of 3000 filaments or fewer be tested as several bundles combined into one specimen; the specimen's fibre mass per unit
  length is then the bundles' sum, so the strength and modulus divide by that sum.
- §11.5 asks for the load introduction to be re-examined when a significant fraction of failures lie within one specimen width of a tab or
  grip, without a number for "significant"; we count the failures whose code places them there (area I, A, W or P of Fig. 1) and show the
  count as a note, never as a deviation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .profile import RELATIVE, Finding, Profile, Requirement

ID = "astm-d4018"
DESIGNATION = "ASTM D4018-23"
KIND = "fibre_tow"  # not a spec kind: a tow has no finite element model (ADR-0073)

GAUGE_LENGTH = 0.150  # m, §8.3, §10.3.2.3 and §11.3.1: between the tabs, or between the grips of an untabbed specimen
GAUGE_BAND = 0.005  # m, the same clauses: plus or minus
SPECIMENS = 4  # §8.3 and §11.3: at least four for strength and four for modulus, the same four or two sets
BUNDLE_FILAMENTS = 3000  # §8.3: several bundles in one specimen only for a tow of this many filaments or fewer
RESIN_STRAIN_RATIO = 2.0  # §4.5: the consolidated resin's strain capability at least twice the fibre's
MUL_LENGTH = 1.0  # m, §8.1 and §11.1.1: the least length of the mass-per-unit-length specimen
SPEED = 250e-3 / 60.0  # m/s, §11.3.2: 250 mm/min, the largest speed allowed
RESIN_CONTENT = (35.0, 60.0)  # percent by weight, §6.1.1 and §10.3.2: the usual range of a uniform impregnation

FIBRE_TYPES = ("carbon", "graphite", "other")  # §1.1 and §3.2.2: continuous-filament carbon or graphite yarn, roving or tow
DENSITY_SAMPLES = ("desized", "unsized", "sized")  # §4.3, §10.2: desized or unsized fibre is the preferred density sample
TAB_WORDS = ("none", "paper or card", "cast resin", "metal", "other")  # §6.1.3, §10.3.2.3: tabs are optional

# Fig. 1, the three-part failure code: the failure's type, its area and its location, each one letter; the words are ours.
FAILURE_TYPES = {"G": "grip or tab", "L": "lateral", "S": "long splitting (fibre pull-out)", "X": "explosive", "O": "other"}
FAILURE_AREAS = {"I": "inside the grip or tab", "A": "at the grip or tab", "W": "within one width of the grip or tab", "G": "gauge",
                 "P": "tab pull-out", "V": "various", "U": "unknown"}
FAILURE_LOCATIONS = {"B": "bottom", "T": "top", "M": "middle", "V": "various", "U": "unknown"}
NEAR_GRIP_AREAS = ("I", "A", "W", "P")  # §11.5: at, in, or within one specimen width of a tab or grip


def failure_words(code: str) -> str | None:
    """A Fig. 1 code in words, "LGM": "lateral, gauge, middle"; None when the code is not three letters of the figure."""
    code = code.strip().upper()
    if len(code) != 3 or code[0] not in FAILURE_TYPES or code[1] not in FAILURE_AREAS or code[2] not in FAILURE_LOCATIONS:
        return None
    return f"{FAILURE_TYPES[code[0]]}, {FAILURE_AREAS[code[1]]}, {FAILURE_LOCATIONS[code[2]]}"


@dataclass(frozen=True)
class TowSubject:
    """The test record a D4018 profile judges, in SI (lengths in metres, speeds in m/s, strains absolute)."""

    fibre_type: str
    gauge_length: float
    tabs: str
    strength_specimens: int  # valid specimens with a maximum force
    modulus_specimens: int  # valid specimens with the forces at both chord strains
    valid: int  # valid specimens
    coded: int  # valid specimens whose failure carries a Fig. 1 code
    near_grip: int  # valid specimens whose code places the failure within one width of a tab or grip
    bundles: int
    filaments: int | None
    failure_strain: float  # the product's typical strain at failure
    chord_used: tuple[float, float]  # the strains the chord forces were read at
    chord_table: tuple[float, float]  # Table 2's for the failure strain
    density_sample: str
    resin_strain: float | None = None
    mul_length: float | None = None  # the mass-per-unit-length specimen's length, when its mass and length are given
    speed: float | None = None
    resin_content: float | None = None  # percent by weight, given or from Eq 3
    units: str = "SI"


def _four(value: float) -> str:
    """A value to four significant figures without an exponent: 50000, not 5e+04."""
    return f"{float(f'{value:.4g}'):.10g}"


def _mm(value_m: float) -> str:
    return f"{_four(value_m * 1e3)} mm"


def _microstrain(strain: float) -> str:
    return f"{_four(strain * 1e6)} microstrain"


def _fibre(s: TowSubject) -> Finding:
    asked = "a continuous-filament carbon or graphite yarn, roving or tow"
    return Finding(s.fibre_type in ("carbon", "graphite"), f"a {s.fibre_type} fibre" if s.fibre_type != "other" else "another fibre", asked)


def _gauge(s: TowSubject) -> Finding:
    where = "between the grips" if s.tabs == "none" else "between the tabs"
    ok = abs(s.gauge_length - GAUGE_LENGTH) <= GAUGE_BAND * (1 + RELATIVE)
    return Finding(ok, f"{_mm(s.gauge_length)} {where}", f"{_mm(GAUGE_LENGTH)} ± {_mm(GAUGE_BAND)} {where}")


def _count(n: int, what: str) -> Finding:
    return Finding(n >= SPECIMENS, f"{n} valid specimen{'s' if n != 1 else ''} with {what}", f"at least {SPECIMENS}")


def _strength_count(s: TowSubject) -> Finding:
    return _count(s.strength_specimens, "a maximum force")


def _modulus_count(s: TowSubject) -> Finding:
    return _count(s.modulus_specimens, "both chord forces")


def _bundles(s: TowSubject) -> Finding:
    asked = f"one bundle, or several combined only for a tow of {BUNDLE_FILAMENTS} filaments or fewer"
    if s.bundles == 1:
        return Finding(None, "one bundle per specimen", asked)
    if s.filaments is None:
        return Finding(None, f"{s.bundles} bundles; the filament count is not given, so this cannot be judged", asked)
    return Finding(s.filaments <= BUNDLE_FILAMENTS, f"{s.bundles} bundles of {s.filaments} filaments", asked)


def _resin_strain(s: TowSubject) -> Finding:
    asked = f"at least {RESIN_STRAIN_RATIO:g} times the fibre's, {_microstrain(RESIN_STRAIN_RATIO * s.failure_strain)}"
    if s.resin_strain is None:
        return Finding(None, "the resin's strain to failure is not given", asked)
    return Finding(s.resin_strain >= RESIN_STRAIN_RATIO * s.failure_strain * (1 - RELATIVE), _microstrain(s.resin_strain), asked)


def _chord(s: TowSubject) -> Finding:
    lo, hi = s.chord_table
    asked = f"{_microstrain(lo)} to {_microstrain(hi)} (Table 2, typical failure strain {_microstrain(s.failure_strain)})"
    if s.modulus_specimens == 0:
        return Finding(None, "no specimen gives chord forces", asked)
    ok = all(math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12) for a, b in zip(s.chord_used, s.chord_table))
    return Finding(ok, f"{_microstrain(s.chord_used[0])} to {_microstrain(s.chord_used[1])}", asked)


def _mul_length(s: TowSubject) -> Finding:
    asked = f"at least {MUL_LENGTH:g} m"
    if s.mul_length is None:
        return Finding(None, "the mass per unit length is given, not the specimen it was weighed on", asked)
    return Finding(s.mul_length >= MUL_LENGTH * (1 - RELATIVE), f"{_four(s.mul_length)} m", asked)


def _speed(s: TowSubject) -> Finding:
    asked = f"at most {SPEED * 6e4:g} mm/min"
    if s.speed is None:
        return Finding(None, "the speed is not given", asked)
    return Finding(s.speed <= SPEED * (1 + RELATIVE), f"{_four(s.speed * 6e4)} mm/min", asked)


def _resin_content(s: TowSubject) -> Finding:
    lo, hi = RESIN_CONTENT
    asked = f"{lo:g} % to {hi:g} % by weight"
    if s.resin_content is None:
        return Finding(None, "the resin content is not given", asked)
    return Finding(lo * (1 - RELATIVE) <= s.resin_content <= hi * (1 + RELATIVE), f"{_four(s.resin_content)} %", asked)


def _density_sample(s: TowSubject) -> Finding:
    return Finding(s.density_sample in ("desized", "unsized"), f"{s.density_sample} fibre", "desized or unsized fibre")


def _density_correction(s: TowSubject) -> Finding:
    asked = "k_c from ten paired tests of sized and desized or unsized fibre; none needed when they differ by less than 1.0 %"
    if s.density_sample != "sized":
        return Finding(True, f"{s.density_sample} fibre: no correction", asked)
    return Finding(False, "a sized fibre's density, corrected by the k_c given (zero when none is given)", asked)


def _failure_codes(s: TowSubject) -> Finding:
    asked = "every specimen's failure coded by type, area and location (Fig. 1)"
    if s.valid == 0:
        return Finding(None, "no valid specimen", asked)
    return Finding(s.coded == s.valid, f"{s.coded} of {s.valid} valid specimens coded", asked)


def _grip_failures(s: TowSubject) -> Finding:
    asked = "re-examine the tabs, the grips and their alignment when a significant fraction fails within one width of them"
    if s.coded == 0:
        return Finding(None, "no failure coded", asked)
    return Finding(s.near_grip == 0, f"{s.near_grip} of {s.coded} coded failures at, in or within one width of a tab or grip", asked)


REQUIREMENTS: tuple[Requirement, ...] = (
    Requirement("scope-fibre", "§1.1", "scope", "A continuous-filament carbon or graphite yarn, roving or tow, impregnated with resin and "
                "consolidated before it is pulled.", _fibre, ("fibre_type",)),
    Requirement("gauge", "§8.3, §11.3.1", "mandatory", "A gauge length of 150 mm ± 5 mm between the tabs, or between the grips of an untabbed "
                "specimen.", _gauge, ("tow_gauge_length", "tow_tabs")),
    Requirement("strength-count", "§8.3, §11.3", "mandatory", "At least four valid specimens tested for strength.", _strength_count, ("specimens",)),
    Requirement("modulus-count", "§8.3, §11.3", "mandatory", "At least four valid specimens tested for modulus, the same four as for strength "
                "or another four.", _modulus_count, ("specimens",)),
    Requirement("bundles", "§8.3", "mandatory", "Several fibre bundles combined into one specimen only for a tow of 3000 filaments or fewer, "
                "the bundles combined before impregnation.", _bundles, ("bundles", "filaments")),
    Requirement("resin-strain", "§4.5", "mandatory", "A consolidated resin able to strain at least twice as far as the fibre.", _resin_strain,
                ("resin_strain", "failure_strain")),
    Requirement("chord", "Table 2, §11.3.11", "mandatory", "The forces for the chord modulus read at the strains Table 2 gives for the "
                "product's typical strain at failure.", _chord, ("chord_lower", "chord_upper", "failure_strain")),
    Requirement("mul-length", "§8.1, §11.1.1", "mandatory", "A mass-per-unit-length specimen of sized fibre at least 1 m long.", _mul_length,
                ("mul_length",)),
    Requirement("speed", "§11.3.2", "mandatory", "A testing machine speed of at most 250 mm/min.", _speed, ("speed",)),
    Requirement("resin-content", "§6.1.1, §10.3.2", "recommended", "A uniform impregnation, typically 35 % to 60 % resin by weight.",
                _resin_content, ("mul_impregnated", "resin_content")),
    Requirement("density-sample", "§4.3, §10.2", "recommended", "The density measured on desized or unsized fibre.", _density_sample,
                ("density_sample",)),
    Requirement("density-correction", "§12.2.2", "note", "A sized fibre's density is corrected for its sizing by k_c, found from ten paired "
                "tests; no correction is needed when sized and desized results differ by less than 1.0 %.", _density_correction,
                ("density_sample", "density_correction")),
    Requirement("failure-codes", "§11.4, Fig. 1", "recommended", "Each specimen's failure recorded by its type, area and location.",
                _failure_codes, ("specimens",)),
    Requirement("grip-failures", "§11.5", "note", "When a significant fraction of the failures lies within one specimen width of a tab or grip, "
                "re-examine the tabs, their adhesive, the grips, their pressure and their alignment.", _grip_failures, ("specimens",)),
    Requirement("machine", "§6.1.4", "lab", "A testing machine verified to ASTM E4 at the largest expected force, its force recorded together "
                "with the extensometer's elongation."),
    Requirement("extensometer", "§6.1.4.3", "lab", "An extensometer and recorder of ASTM E83 Class B-2."),
    Requirement("measuring", "§6.1.4.4, §6.1.4.6", "lab", "Masses on an analytical balance to ±0.0002 g; lengths to ±2 mm."),
    Requirement("density-method", "§11.2", "lab", "The density by ASTM D3800 Method A (Archimedes) or by D70 or D5550 (pycnometer)."),
    Requirement("conditioning", "§9", "lab", "Conditioning and the test atmosphere by the fibre's moisture adsorption: no conditioning below "
                "0.5 % by weight at 23 °C and 90 % relative humidity, 24 h at 23 °C and 50 % relative humidity above it."),
    Requirement("consolidation", "§6.1.2, §6.1.4.8, §10.3.2.1", "lab", "The impregnated strand held under tension while it consolidates, "
                "and cured in an oven held within ±10 °C."),
    Requirement("preload", "§11.3.6, Table 1", "lab", "A preload no larger than Table 1 gives, found from the expected modulus and the "
                "fibre's area (the planning loads below)."),
    Requirement("alignment", "§11.3.5", "lab", "The specimen centred in the jaws and aligned with the load."),
    Requirement("specimen-quality", "§8.3", "lab", "Fuzzy, curved, uneven or otherwise flawed specimens rejected unless they represent the "
                "material."),
    Requirement("retests", "§11.3.12", "lab", "A flawed or suspect specimen replaced or retested, slippage and breaks in the tabs or at the "
                "extensometer counted as such, every value recorded."),
)

# §13.1.3: what the tensile test report holds, each with the rows that give it (the record shows it when they are filled in).
REPORT_ITEMS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("§13.1.3.1", "Identification of the samples tested", ("fibre", "lot")),
    ("§13.1.3.2", "Date of test", ("date",)),
    ("§13.1.3.3", "Test facility", ("facility",)),
    ("§13.1.3.4", "Who tested", ("filled_by",)),
    ("§13.1.3.5", "Impregnation apparatus, resin and consolidation or cure cycle", ("impregnation", "resin", "cure")),
    ("§13.1.3.6", "Tensile testing apparatus", ("machine",)),
    ("§13.1.3.7", "Each specimen's and the average strength and chord modulus", ("specimens",)),
    ("§13.1.3.8", "Reasons for rejecting specimens and the failure modes", ("specimens",)),
    ("§13.1.3.9", "Deviations from the method", ()),
)

PROFILE = Profile(
    id=ID, designation=DESIGNATION, title="Tensile properties of continuous-filament carbon and graphite fibre tows", kinds=(KIND,),
    catalog_url="https://store.astm.org/d4018-23.html",
    edition_note="read from the D4018-23 copy licensed to UC San Diego",
    systems="SI only (§1.5)",
    requirements=REQUIREMENTS, aliases=("d4018",),
)
