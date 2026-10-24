"""The coupon audit (ADR-0043): one rubric that every audit of a coupon package is scored against.

The rubric (`paths.RUBRIC`) lists each check once: what is checked, what passes, who judges it (our tools or the auditor),
the tolerance, whether a Pass verdict needs it, the tests it applies to and what the team must send for it. This module reads
it and refuses one that is incomplete or inconsistent (ADR-0003): a missing field, an item numbered out of order or under an
unknown section, a test code `spec.TEST_CODES` does not know, or a function in `source` that does not exist.

`score` gives each item of a package its result from what our tools found (`Evidence`): a result for the items our tools
judge, and the evidence the auditor reads for the rest. `write_form` writes the audit form, the Excel workbook the auditor
fills in: the computed results locked, the auditor's cells open, the words of each answer offered as a list.

The words an audit form uses are fixed here, so the form, the document and the reader of a returned form agree on them.
"""

from __future__ import annotations

import hashlib
import importlib
import re
import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, ValidationError, model_validator

from . import paths
from .equivalence import DeckEquivalence, EquivalenceItem
from .mesh import KernelError
from .model import Deck, expanded_layers, resolve_nodes
from .report import LaminateCheck, laminate_check
from .results import MembraneSolution
from .side_by_side import PairedValue, agreement
from .spec import TEST_CODES
from .units import from_si

RESULTS = ("Pass", "Fail", "N/A", "Not checked")  # an item's result on the form
VERDICTS = ("Pass", "Pass with observations", "Fail")  # the audit's verdict
SEVERITIES = ("Blocker", "Major", "Minor", "Observation")  # a finding's severity
CAUSES = ("engine", "our input", "their model", "documentation", "tolerance")  # what a finding traces to, and so who fixes it
STATUSES = ("Open", "Closed")  # a finding's status
ITEM_ID = re.compile(r"^(?P<section>[A-Z])(?P<number>[1-9][0-9]*)$")


class RubricError(ValueError):
    """The rubric is incomplete or inconsistent."""


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Tolerance(Record):
    """Exactly one of: a fraction (of the value or largest magnitude the acceptance names), or a length in metres."""

    relative: PositiveFloat | None = None
    length_m: PositiveFloat | None = None

    @model_validator(mode="after")
    def one_kind(self) -> Tolerance:
        if (self.relative is None) == (self.length_m is None):
            raise ValueError("give exactly one of relative or length_m")
        return self


class Section(Record):
    id: str
    title: str = Field(min_length=1)


class Item(Record):
    id: str
    section: str
    check: str = Field(min_length=1)
    acceptance: str = Field(min_length=1)
    method: Literal["auto", "auditor"]
    required: bool
    source: tuple[str, ...] = ()  # "module.function" or "module.Class.method" in anisotropy_fea
    tolerance: Tolerance | None = None
    applies_to: tuple[str, ...] = ()  # test codes; empty: every test
    needs: str | None = Field(default=None, min_length=1)


class Rubric(Record):
    version: str = Field(min_length=1)
    status: Literal["draft", "confirmed"]
    sections: tuple[Section, ...] = Field(alias="section", min_length=1)
    items: tuple[Item, ...] = Field(alias="item", min_length=1)


def parse_rubric(text: str, source_path: str | None = None) -> Rubric:
    """The rubric in `text`, checked; `source_path` only names it in errors."""
    where = source_path or "rubric"
    try:
        rubric = Rubric(**tomllib.loads(text))
    except (tomllib.TOMLDecodeError, ValidationError) as exc:
        raise RubricError(f"{where}: {exc}") from None
    validate_rubric(rubric, where)
    return rubric


def load_rubric(path: Path | str = paths.RUBRIC) -> Rubric:
    path = Path(path)
    return parse_rubric(path.read_text(encoding="utf-8"), str(path))


def validate_rubric(rubric: Rubric, where: str = "rubric") -> None:
    """Sections named once; items numbered 1, 2, ... within their section, in file order; known test codes and functions."""

    def need(condition: bool, message: str) -> None:
        if not condition:
            raise RubricError(f"{where}: {message}")

    section_ids = [s.id for s in rubric.sections]
    need(all(re.fullmatch(r"[A-Z]", s) for s in section_ids), f"section ids are single capital letters, not {section_ids}")
    need(len(set(section_ids)) == len(section_ids), f"a section id is used twice: {section_ids}")
    codes = {code for code, _ in TEST_CODES.values()}
    numbers: dict[str, int] = {}
    for item in rubric.items:
        match = ITEM_ID.match(item.id)
        need(match is not None, f"item id {item.id!r}: write the section letter and a number, such as A1")
        need(match.group("section") == item.section, f"item {item.id} sits under section {item.section!r}; its id names {match.group('section')}")
        need(item.section in section_ids, f"item {item.id}: section {item.section!r} is not one of {section_ids}")
        expected = numbers.get(item.section, 0) + 1
        need(int(match.group("number")) == expected, f"item {item.id}: section {item.section} is numbered from 1 in file order; expected {item.section}{expected}")
        numbers[item.section] = expected
        unknown = sorted(set(item.applies_to) - codes)
        need(not unknown, f"item {item.id}: test codes {unknown} are not in spec.TEST_CODES ({sorted(codes)})")
        need(len(set(item.applies_to)) == len(item.applies_to), f"item {item.id}: a test code is listed twice")
        for name in item.source:
            need(_resolves(name), f"item {item.id}: source {name!r} is not a function of anisotropy_fea (write module.function or module.Class.method)")
    empty = [s for s in section_ids if s not in numbers]
    need(not empty, f"sections {empty} have no items")


def _resolves(name: str) -> bool:
    """`module.function` or `module.Class.method` (a property counts), the module one of anisotropy_fea's."""
    module, *attributes = name.split(".")
    if not attributes:
        return False
    try:
        found = importlib.import_module(f"anisotropy_fea.{module}")
    except ImportError:
        return False
    for attribute in attributes:
        found = getattr(found, attribute, None)
    return callable(found) or isinstance(found, property)


def items_for(rubric: Rubric, test_code: str) -> tuple[Item, ...]:
    """The items an audit of a coupon with this test code scores, in rubric order."""
    if test_code not in {code for code, _ in TEST_CODES.values()}:
        raise RubricError(f"test code {test_code!r} is not in spec.TEST_CODES")
    return tuple(item for item in rubric.items if not item.applies_to or test_code in item.applies_to)


# --------------------------------------------------------------------------------------------- scoring

@dataclass(frozen=True)
class Evidence:
    """What our tools found for one coupon package. Lengths and stresses in the stated `units`, forces in N.

    The team's side is empty when the team has not built the coupon: the model and results match cannot then be checked.
    """

    test_code: str
    units: str  # "mm-MPa" or "m-Pa"
    card: tuple[tuple[str, str], ...]  # spec.coupon_card
    engine_commit: str | None  # as the documents print it; "+ local changes" when the tree was not clean
    attempt: str | None  # the attempt-log row the package delivers, as the case page writes it
    our_deck: Deck  # SI
    solution: MembraneSolution  # our kernel on our deck
    material: str | None = None  # the library record the spec names, in words
    team_deck: Deck | None = None  # SI
    team_deck_sha256: str | None = None  # compare.sha256_of
    equivalence: DeckEquivalence | None = None
    paired: tuple[PairedValue, ...] = ()  # the team's reported values beside ours
    inner_band: tuple[float, float] | None = None  # the graded band: element centroids with lo <= y <= hi
    free_band: tuple[float, float] | None = None  # the free length between the grips
    excluded: str | None = None  # how the regions left out of the grading were set, in words
    team_reaction: float | None = None  # N, at the loaded grip
    fpf: tuple[str, float, int] | None = None  # our first-ply failure: criterion, factor of the applied loading, ply (1 = bottom)
    rebuilt: DeckEquivalence | str | None = None  # a deck the auditor built from our guide against ours, or why the two could not be compared
    guide: tuple[int, int] | None = None  # the rebuild guide's open items and ASSUMED tags


@dataclass(frozen=True)
class Scored:
    item: Item
    result: str | None  # one of RESULTS for an item our tools judge; None for the auditor's
    evidence: str


@dataclass(frozen=True)
class _Facts:
    """Computed once per package for several items."""

    laminate: LaminateCheck | None
    laminate_reason: str  # why there is no laminate check, when there is none
    angles: tuple[float, ...]
    length_unit: str
    stress_unit: str


# Which of deck_equivalence's items (by the whole of their name) answer each B item.
EQUIVALENCE_GROUPS = {
    "B1": r"Nodes|Node positions",
    "B2": r"Elements|Element connectivity",
    "B3": r"Layup, bottom first",
    "B4": r"Section|Ply thickness|Integration points per ply|Shell orientation",
    "B5": r"Material (E1|E2|nu12|G12|G13|G23)( \(.+\))?",
    "B7": r"Couplings|Coupling(,| at) .+",
    "B8": r"Boundary conditions, node by node|Concentrated loads",
    "B9": r"Steps",
}
LISTED_ONLY = ("Part / instance names", "Material names", "Section set / layup names", "Strengths (*Fail Stress)")  # shown, not judged
NOT_BUILT_BY_TEAM = "the team has not built this coupon, so there is no model of theirs to compare"


def equivalence_group(equivalence: DeckEquivalence, item_id: str) -> list[EquivalenceItem]:
    return [i for i in equivalence.items if re.fullmatch(EQUIVALENCE_GROUPS[item_id], i.item)]


def _pct(fraction: float) -> str:
    return f"{100 * fraction:.3g} %"


def _layup_text(angles: tuple[float, ...]) -> str:
    symmetric = list(angles) == list(reversed(angles))
    off_axis = sorted({abs(a) for a in angles if a % 90 != 0})
    unbalanced = [a for a in off_axis if angles.count(a) != angles.count(-a)]
    balance = ("balanced" if not unbalanced else "unbalanced (" + "; ".join(f"{angles.count(a)} plies at +{a:g}, {angles.count(-a)} at -{a:g}"
                                                                             for a in unbalanced) + ")")
    return f"[{'/'.join(f'{a:g}' for a in angles)}], {len(angles)} plies, {balance}, {'symmetric' if symmetric else 'not symmetric'}"


def _model_match(item: Item, ev: Evidence, facts: _Facts) -> tuple[str, str]:
    if ev.equivalence is None:
        return "Not checked", NOT_BUILT_BY_TEAM
    group = equivalence_group(ev.equivalence, item.id)
    if not group:
        return "N/A", "neither deck has one" if item.id == "B7" else "deck_equivalence reports no such item"
    differ = [i for i in group if i.same is False]
    text = "; ".join(f"{i.item}: {'same' if i.same else 'differs'} (team {i.team}; ours {i.ours})" for i in group)
    result = "Fail" if differ else "Pass"
    if item.id == "B1":
        limit = item.tolerance.length_m
        offset = ev.equivalence.largest_node_offset
        result = "Fail" if differ or offset > limit else "Pass"
        text = (f"{text}; largest offset {from_si(offset, 'length', ev.units):.3g} {facts.length_unit} against the tolerance "
                f"{from_si(limit, 'length', ev.units):.3g} {facts.length_unit}")
    if item.id == "B3":
        text += f". Our layup: {_layup_text(facts.angles)}"
    if item.id == "B5" and differ:
        text += ". Largest relative difference: " + _largest_material_difference(ev.team_deck, ev.our_deck)
    return result, text


def _largest_material_difference(team: Deck, ours: Deck) -> str:
    """The constant whose ply values differ most, relative to ours: the size a six-digit table hides."""
    plies = lambda deck: expanded_layers(next(iter(deck.parts.values())).sections[0])  # noqa: E731
    worst = (0.0, "")
    for name in ("E1", "E2", "nu12", "G12", "G13", "G23"):
        for a, b in zip(plies(team), plies(ours)):
            x, y = getattr(team.materials[a.material].elastic, name), getattr(ours.materials[b.material].elastic, name)
            if x is not None and y is not None and y != 0:
                worst = max(worst, (abs(x - y) / abs(y), name))
    return f"{worst[0]:.2g} ({worst[1]})"


def _identity(item: Item, ev: Evidence, facts: _Facts) -> tuple[str, str]:
    if item.id == "A1":
        blank = [label for label, value in ev.card if not value.strip()]
        if not ev.card:
            return "Fail", "the spec has no [coupon] table"
        return ("Fail" if blank else "Pass"), ("blank: " + ", ".join(blank) if blank else "; ".join(f"{label}: {value}" for label, value in ev.card))
    if item.id == "A2":
        missing = []
        if ev.engine_commit in (None, "", "unknown"):
            missing.append("the engine's commit is unknown")
        elif "local changes" in ev.engine_commit:
            missing.append(f"the engine was built from uncommitted changes ({ev.engine_commit}), so the run cannot be traced to a commit")
        if not ev.attempt:
            missing.append("no attempt number (the case page names no accepted attempt)")
        if ev.team_deck is not None and not ev.team_deck_sha256:
            missing.append("the team's deck has no digest")
        named = [f"engine commit {ev.engine_commit}", f"attempt {ev.attempt or 'none'}",
                 f"team deck SHA-256 {ev.team_deck_sha256[:16]}... (in full on the cover)" if ev.team_deck_sha256 else "no team deck"]
        return ("Fail" if missing else "Pass"), "; ".join(named) + ("" if not missing else ". " + "; ".join(missing).capitalize())
    decks = [d for d in (ev.our_deck, ev.team_deck) if d is not None]
    read = [d.units for d in decks]
    ok = all(u == ev.units for u in read)
    return ("Pass" if ok else "Fail"), (f"{len(decks)} deck(s) read in {', '.join(str(u) for u in read)} and converted to SI; the audit states "
                                        f"{ev.units}")


def _stresses(quantities: tuple[str, ...]) -> Callable[[Item, Evidence, _Facts], tuple[str, str]]:
    def scorer(item: Item, ev: Evidence, facts: _Facts) -> tuple[str, str]:
        if ev.equivalence is None:
            return "Not checked", NOT_BUILT_BY_TEAM
        if ev.inner_band is None:
            return "Not checked", "no graded band is set for this coupon"
        reported = [q for q in quantities if any(p.quantity == q for p in ev.paired)]
        if not reported:
            return "Not checked", f"the team sent no field report of {', '.join(quantities)}"
        lo, hi = ev.inner_band
        parts, failed = [], False
        for q in reported:
            a = agreement(list(ev.paired), q, "inner", ev.inner_band, item.tolerance.relative)
            if a.count == 0:
                parts.append(f"{q}: no reported element in y {lo:g} to {hi:g} {facts.length_unit}")
                failed = True
                continue
            failed |= a.within != a.count
            w = a.worst
            parts.append(f"{q}: {a.within} of {a.count} within {_pct(a.fraction)} of {a.largest:.6g} {facts.stress_unit}; worst {_pct(a.worst_fraction)} "
                         f"at team element {w.reference_element}, layer {w.layer}")
        layers = sorted({p.layer for p in ev.paired if p.quantity in reported})
        missing = [q for q in quantities if q not in reported]
        text = (f"y {lo:g} to {hi:g} {facts.length_unit}, layers {', '.join(map(str, layers))}. " + "; ".join(parts)
                + (f". Not reported: {', '.join(missing)}" if missing else ""))
        return ("Fail" if failed else "Pass"), text
    return scorer


def _reaction(item: Item, ev: Evidence, facts: _Facts) -> tuple[str, str]:
    ours = f"ours {facts.laminate.kernel_reaction_N:.6g} N" if facts.laminate is not None else "ours not computed: " + facts.laminate_reason
    if ev.team_reaction is None:
        return "Not checked", f"the team's export has no reaction force; {ours}"
    if facts.laminate is None:
        return "Not checked", ours
    difference = abs(facts.laminate.kernel_reaction_N - ev.team_reaction) / abs(ev.team_reaction)
    return ("Pass" if difference <= item.tolerance.relative else "Fail"), f"team {ev.team_reaction:.6g} N, {ours}: {_pct(difference)} apart"


def _not_exported(what: str) -> Callable[[Item, Evidence, _Facts], tuple[str, str]]:
    return lambda item, ev, facts: ("Not checked", f"the team's export has no {what}")


def _fpf(item: Item, ev: Evidence, facts: _Facts) -> tuple[str, str]:
    ours = (f"ours: {ev.fpf[0].replace('_', ' ')} at {ev.fpf[1]:.4g} of the applied loading, ply {ev.fpf[2]}" if ev.fpf else "ours not computed")
    return "Not checked", f"the team's export has no failure index; {ours}"


def _laminate(item: Item, ev: Evidence, facts: _Facts) -> tuple[str, str]:
    check = facts.laminate
    if check is None:
        return "Not checked", "no laminate-theory check for this model: " + facts.laminate_reason
    strain = float(np.max(np.abs(check.kernel_strain - check.strain)) / np.max(np.abs(check.strain)))
    stress = float(np.max(np.abs(check.kernel_ply_stress_12 - check.ply_stress_12)) / np.max(np.abs(check.ply_stress_12)))
    worst = max(strain, stress)
    return (("Pass" if worst <= item.tolerance.relative else "Fail"),
            f"centre element {check.centre_element}: strain within {_pct(strain)} of the largest laminate-theory strain, ply stresses within "
            f"{_pct(stress)} of the largest ply stress")


def _equilibrium(item: Item, ev: Evidence, facts: _Facts) -> tuple[str, str]:
    deck = ev.our_deck
    applied = np.zeros(2)
    for step in deck.steps:
        for load in step.cloads:
            if load.dof in (1, 2):
                applied[load.dof - 1] += load.value * len(resolve_nodes(deck, load.target, load.line))
    residual = ev.solution.total_reaction + applied
    scale = abs(facts.laminate.kernel_reaction_N) if facts.laminate is not None else float(np.abs(ev.solution.reaction).sum(axis=0).max()) / 2
    if scale == 0.0:
        return "Not checked", "no reaction to compare the sum with"
    share = float(np.max(np.abs(residual))) / scale
    return (("Pass" if share <= item.tolerance.relative else "Fail"),
            f"reactions sum to ({ev.solution.total_reaction[0]:.3g}, {ev.solution.total_reaction[1]:.3g}) N against applied loads "
            f"({applied[0]:.3g}, {applied[1]:.3g}) N; the residual is {share:.2g} of the {scale:.6g} N reaction")


def _not_built(item: Item, ev: Evidence, facts: _Facts) -> tuple[str, str]:
    return "Not checked", "this check is not built yet"


def _rebuilt(item: Item, ev: Evidence, facts: _Facts) -> tuple[str, str]:
    if ev.rebuilt is None:
        return "Not checked", "no deck rebuilt from the guide has come back"
    if isinstance(ev.rebuilt, str):
        return "Fail", f"the rebuilt deck cannot be matched to ours: {ev.rebuilt}"
    differ = ev.rebuilt.differences
    return (("Pass" if not differ else "Fail"),
            "the rebuilt deck matches ours item by item" if not differ else "differs: " + "; ".join(i.item for i in differ))


AUTO: dict[str, Callable[[Item, Evidence, _Facts], tuple[str, str]]] = {
    "A1": _identity, "A2": _identity, "A3": _identity,
    **{item_id: _model_match for item_id in EQUIVALENCE_GROUPS},
    "C1": _reaction, "C2": _stresses(("S11", "S22", "S12")), "C3": _stresses(("Mises",)), "C4": _not_exported("displacement or strain (U, E)"),
    "C7": _fpf, "D1": _laminate, "D2": _equilibrium, "D3": _not_built, "D4": _not_built, "E2": _rebuilt,
}


def _auditor_evidence(item: Item, ev: Evidence, facts: _Facts) -> str:
    """What our tools can show the auditor for an item the auditor judges."""
    if item.id == "B6":
        strengths = next((i.ours for i in ev.equivalence.items if i.item.startswith("Strengths")), None) if ev.equivalence else None
        return "; ".join(t for t in (f"material: {ev.material}" if ev.material else "explicit constants in the spec",
                                     f"strengths in our deck: {strengths}" if strengths else None) if t)
    if item.id == "C5":
        return NOT_BUILT_BY_TEAM if ev.equivalence is None else (ev.excluded or "the comparison names no region left out")
    if item.id == "C6":
        if not ev.paired:
            return NOT_BUILT_BY_TEAM if ev.equivalence is None else "the team sent no field report"
        parts = []
        for q in dict.fromkeys(p.quantity for p in ev.paired):
            members = [p for p in ev.paired if p.quantity == q]
            team, ours = max(members, key=lambda p: abs(p.reference)), max(members, key=lambda p: abs(p.ours))
            parts.append(f"{q}: the team's largest at element {team.reference_element} ({team.x:g}, {team.y:g}), ours at element "
                         f"{ours.reference_element} ({ours.x:g}, {ours.y:g})")
        return "; ".join(parts) + f" (team element numbers, {facts.length_unit})"
    if item.id == "D5":
        text = f"layup {_layup_text(facts.angles)}"
        if facts.laminate is not None:
            eps = facts.laminate.kernel_strain
            text += f"; at the centre element gamma_xy = {eps[2]:.4g} and eps_y = {eps[1]:.4g}"
        return text + "; the kernel is a membrane model, so it shows no bending"
    if item.id == "E3":
        return "" if ev.guide is None else (f"the guide lists {ev.guide[0]} open item(s) at its end and tags {ev.guide[1]} value(s) ASSUMED")
    if item.id == "E4":
        card = dict(ev.card)
        return f"test data on the coupon card: {card.get('Test data', 'not stated')}"
    return ""


def score(rubric: Rubric, evidence: Evidence) -> tuple[Scored, ...]:
    """Every item that applies to the package's test, in rubric order: a result where our tools judge, evidence for the auditor."""
    deck = evidence.our_deck
    try:
        check, reason = laminate_check(deck, evidence.solution), ""
    except KernelError as exc:
        check, reason = None, str(exc)
    section = next(iter(deck.parts.values())).sections[0]
    length_unit, stress_unit = {"mm-MPa": ("mm", "MPa"), "m-Pa": ("m", "Pa")}[evidence.units]
    facts = _Facts(check, reason, tuple(layer.angle_deg for layer in expanded_layers(section)), length_unit, stress_unit)
    scored = []
    for item in items_for(rubric, evidence.test_code):
        if item.method == "auditor":
            scored.append(Scored(item, None, _auditor_evidence(item, evidence, facts)))
            continue
        scorer = AUTO.get(item.id)
        result, text = scorer(item, evidence, facts) if scorer else ("Not checked", "no scorer is built for this item yet")
        scored.append(Scored(item, result, text))
    return tuple(scored)


def tolerance_text(item: Item, units: str) -> str:
    if item.tolerance is None:
        return ""
    if item.tolerance.relative is not None:
        relative = item.tolerance.relative
        return f"{relative:g} relative" if relative < 1e-4 else f"{100 * relative:g} %"
    unit = {"mm-MPa": "mm", "m-Pa": "m"}[units]
    return f"{from_si(item.tolerance.length_m, 'length', units):g} {unit}"


# --------------------------------------------------------------------------------------------- the audit form

COVER, RUBRIC_SHEET, FINDINGS = "Cover", "Rubric", "Findings"
AUDITOR_FIELDS = ("Auditor", "Audit date", "Verdict")  # the cover's cells the auditor fills in
DIGEST = "Our results digest"  # the cover row that lets a returned form show our tools' results were not changed
RUBRIC_COLUMNS = ("ID", "Section", "Check", "Acceptance", "Judged by", "Required", "Tolerance", "Result", "Evidence", "Observation", "Findings")
FINDING_COLUMNS = ("ID", "Item", "Severity", "Cause", "What was found", "Owner", "Status")
FINDING_ROWS = 30  # numbered rows offered on the form; a row without "What was found" is not a finding


def write_form(path: Path | str, rubric: Rubric, scored: tuple[Scored, ...], cover: list[tuple[str, str]], units: str) -> Path:
    """The audit form: a cover with the package's identity and the auditor's fields, the rubric with our results locked and the
    auditor's cells open, and a findings table. Lists offer the fixed words; the sheets are protected without a password, so a
    cell is not changed by accident (this is not a security measure)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill, Protection
    from openpyxl.worksheet.datavalidation import DataValidation

    path = Path(path)
    bold, title = Font(bold=True), Font(bold=True, size=14)
    wrap = Alignment(wrap_text=True, vertical="top")
    open_cell = PatternFill("solid", fgColor="FFF4CC")  # the auditor's cells
    header_fill = PatternFill("solid", fgColor="DDE6F0")
    unlocked = Protection(locked=False)

    def listing(sheet, words, cells: list[str]) -> None:
        validation = DataValidation(type="list", formula1='"' + ",".join(words) + '"', allow_blank=True)
        sheet.add_data_validation(validation)
        for cell in cells:
            validation.add(cell)

    def protect(sheet) -> None:
        sheet.protection.sheet = True
        sheet.protection.formatColumns = False  # widths and heights may still be changed
        sheet.protection.formatRows = False

    book = Workbook()
    sheet = book.active
    sheet.title = COVER
    sheet["A1"] = "Anisotropy AI coupon audit"
    sheet["A1"].font = title
    row = 3
    digest = results_digest([(s.item.id, s.result) for s in scored if s.result is not None])
    for label, value in [*cover, ("Rubric", f"version {rubric.version} ({rubric.status})"), (DIGEST, digest)]:
        sheet.cell(row, 1, label).font = bold
        sheet.cell(row, 2, value).alignment = wrap
        row += 1
    row += 1
    sheet.cell(row, 1, "Filled in by the auditor").font = bold
    row += 1
    for label in AUDITOR_FIELDS:
        sheet.cell(row, 1, label).font = bold
        cell = sheet.cell(row, 2)
        cell.fill, cell.protection = open_cell, unlocked
        if label == "Verdict":
            listing(sheet, VERDICTS, [cell.coordinate])
        row += 1
    row += 1
    for line in (
        "How to fill it in: on the Rubric sheet, give a Result for every row judged by the auditor, and add an Observation where you have one. "
        "Rows judged by our tools are filled in and locked. Record each problem on the Findings sheet and put its ID in the Findings column of "
        "the rubric row it is about. Then give your name, the date and the verdict above.",
        "The verdict: Fail if a required row fails or a Blocker or Major finding is open; Pass with observations if anything else failed or any "
        "finding is open; Pass otherwise. A verdict needs every required row to have a result other than Not checked.",
        "Put the filled-in form back in the folder you received the package in.",
    ):
        cell = sheet.cell(row, 1, line)
        cell.alignment = wrap
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        sheet.row_dimensions[row].height = 48
        row += 1
    sheet.column_dimensions["A"].width = 22
    sheet.column_dimensions["B"].width = 90
    protect(sheet)

    sheet = book.create_sheet(RUBRIC_SHEET)
    sheet.append(list(RUBRIC_COLUMNS))
    titles = {s.id: s.title for s in rubric.sections}
    for s in scored:
        item = s.item
        sheet.append([item.id, titles[item.section], item.check, item.acceptance, "our tools" if item.method == "auto" else "auditor",
                      "yes" if item.required else "no", tolerance_text(item, units), s.result or "", s.evidence, "", ""])
    last = len(scored) + 1
    for cells in sheet.iter_rows(min_row=1, max_row=last):
        for cell in cells:
            cell.alignment = wrap
    for cell in sheet[1]:
        cell.font, cell.fill = bold, header_fill
    result_col, observation_col, findings_col = (RUBRIC_COLUMNS.index(name) + 1 for name in ("Result", "Observation", "Findings"))
    auditor_rows = [r for r, s in enumerate(scored, start=2) if s.result is None]
    for r in range(2, last + 1):
        for col in (observation_col, findings_col) + ((result_col,) if r in auditor_rows else ()):
            cell = sheet.cell(r, col)
            cell.fill, cell.protection = open_cell, unlocked
    letter = sheet.cell(1, result_col).column_letter
    if auditor_rows:
        listing(sheet, RESULTS, [f"{letter}{r}" for r in auditor_rows])
    for name, width in zip(RUBRIC_COLUMNS, (6, 18, 26, 40, 10, 9, 10, 12, 60, 36, 12)):
        sheet.column_dimensions[sheet.cell(1, RUBRIC_COLUMNS.index(name) + 1).column_letter].width = width
    sheet.freeze_panes = "C2"
    protect(sheet)

    sheet = book.create_sheet(FINDINGS)
    sheet.append(list(FINDING_COLUMNS))
    for n in range(1, FINDING_ROWS + 1):
        sheet.append([f"F{n}", "", "", "", "", "", ""])
        for col in range(2, len(FINDING_COLUMNS) + 1):
            cell = sheet.cell(n + 1, col)
            cell.fill, cell.protection, cell.alignment = open_cell, unlocked, wrap
    for cell in sheet[1]:
        cell.font, cell.fill = bold, header_fill
    first, end = 2, FINDING_ROWS + 1
    for name, words in (("Item", [s.item.id for s in scored]), ("Severity", SEVERITIES), ("Cause", CAUSES), ("Status", STATUSES)):
        col = sheet.cell(1, FINDING_COLUMNS.index(name) + 1).column_letter
        listing(sheet, words, [f"{col}{first}:{col}{end}"])
    for name, width in zip(FINDING_COLUMNS, (6, 8, 13, 15, 70, 16, 10)):
        sheet.column_dimensions[sheet.cell(1, FINDING_COLUMNS.index(name) + 1).column_letter].width = width
    sheet.freeze_panes = "B2"
    protect(sheet)

    path.parent.mkdir(parents=True, exist_ok=True)
    book.save(path)
    return path


def results_digest(results: list[tuple[str, str]]) -> str:
    """SHA-256 of our tools' results, item by item, so a returned form shows they were not changed (the sheet lock has no password)."""
    return hashlib.sha256(";".join(f"{item}={result}" for item, result in results).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------------------------- a returned form

class AuditError(ValueError):
    """A returned audit form that is incomplete, inconsistent, or not the package's."""


@dataclass(frozen=True)
class Row:
    id: str
    judged_by: str  # "our tools" or "auditor"
    required: bool
    result: str
    observation: str
    findings: tuple[str, ...]


@dataclass(frozen=True)
class Finding:
    id: str
    item: str
    severity: str
    cause: str
    what: str
    owner: str
    status: str


@dataclass(frozen=True)
class ReturnedForm:
    path: Path
    cover: dict[str, str]  # label -> value, as the form's cover states them
    rows: tuple[Row, ...]
    findings: tuple[Finding, ...]
    auditor: str
    date: str  # ISO
    verdict: str

    def counts(self) -> str:
        """The findings in words: open ones by severity, then closed ones."""
        open_ = [f for f in self.findings if f.status == "Open"]
        by = [f"{sum(f.severity == s for f in open_)} {s}" for s in SEVERITIES if any(f.severity == s for f in open_)]
        closed = len(self.findings) - len(open_)
        return (f"{len(open_)} open" + (f" ({', '.join(by)})" if by else "") if open_ else "none open") + (f", {closed} closed" if closed else "")


def verdict_of(rows: tuple[Row, ...], findings: tuple[Finding, ...]) -> str:
    """The rule's verdict: Fail if a required row fails or a Blocker or Major finding is open; Pass with observations if anything else
    failed or any finding is open; Pass otherwise. Refused while a required row has no result other than Not checked."""
    missing = [r.id for r in rows if r.required and r.result in ("", "Not checked")]
    if missing:
        raise AuditError(f"no verdict yet: the required rows {', '.join(missing)} have no result other than Not checked")
    open_ = [f for f in findings if f.status == "Open"]
    if any(r.required and r.result == "Fail" for r in rows) or any(f.severity in ("Blocker", "Major") for f in open_):
        return "Fail"
    if any(r.result == "Fail" for r in rows) or open_:
        return "Pass with observations"
    return "Pass"


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def read_form(path: Path | str) -> ReturnedForm:
    """A filled-in audit form, checked: every problem is named at once (ADR-0003)."""
    from openpyxl import load_workbook

    path = Path(path)
    try:
        book = load_workbook(path, data_only=True)
    except Exception as exc:  # openpyxl raises several kinds for a file that is not a workbook
        raise AuditError(f"{path.name}: not an audit form ({exc})") from None
    problems: list[str] = []
    if [COVER, RUBRIC_SHEET, FINDINGS] != book.sheetnames:
        raise AuditError(f"{path.name}: the sheets are {book.sheetnames}, not {[COVER, RUBRIC_SHEET, FINDINGS]}")

    sheet = book[COVER]
    cover = {_text(sheet.cell(r, 1).value): _text(sheet.cell(r, 2).value) for r in range(1, sheet.max_row + 1) if sheet.cell(r, 1).value}
    for label in AUDITOR_FIELDS:
        if not cover.get(label):
            problems.append(f"the cover's {label} is empty")
    if cover.get("Verdict") and cover["Verdict"] not in VERDICTS:
        problems.append(f"the verdict {cover['Verdict']!r} is not one of {list(VERDICTS)}")
    try:
        audit_date = date.fromisoformat(cover.get("Audit date", "")).isoformat()
    except ValueError:
        audit_date = cover.get("Audit date", "")
        if audit_date:
            problems.append(f"the audit date {audit_date!r} is not a date (write YYYY-MM-DD)")

    sheet = book[RUBRIC_SHEET]
    header = [_text(c.value) for c in sheet[1]]
    if header != list(RUBRIC_COLUMNS):
        raise AuditError(f"{path.name}: the rubric sheet's columns are {header}, not {list(RUBRIC_COLUMNS)}")
    col = {name: RUBRIC_COLUMNS.index(name) + 1 for name in RUBRIC_COLUMNS}
    rows = []
    for r in range(2, sheet.max_row + 1):
        item = _text(sheet.cell(r, col["ID"]).value)
        if not item:
            continue
        result = _text(sheet.cell(r, col["Result"]).value)
        if result not in RESULTS:
            problems.append(f"row {item}: the result {result!r} is not one of {list(RESULTS)}" if result else f"row {item} has no result")
        refs = tuple(x for x in re.split(r"[,\s;]+", _text(sheet.cell(r, col["Findings"]).value)) if x)
        rows.append(Row(item, _text(sheet.cell(r, col["Judged by"]).value), _text(sheet.cell(r, col["Required"]).value) == "yes", result,
                        _text(sheet.cell(r, col["Observation"]).value), refs))
    digest = results_digest([(row.id, row.result) for row in rows if row.judged_by == "our tools"])
    if cover.get(DIGEST) != digest:
        problems.append("a result our tools gave was changed: the rows judged by our tools no longer match the cover's digest")

    sheet = book[FINDINGS]
    fcol = {name: FINDING_COLUMNS.index(name) + 1 for name in FINDING_COLUMNS}
    findings = []
    items = {row.id for row in rows}
    for r in range(2, sheet.max_row + 1):
        what = _text(sheet.cell(r, fcol["What was found"]).value)
        if not what:
            continue
        f = Finding(*(_text(sheet.cell(r, fcol[name]).value) for name in ("ID", "Item", "Severity", "Cause")), what,
                    _text(sheet.cell(r, fcol["Owner"]).value), _text(sheet.cell(r, fcol["Status"]).value))
        for name, value, words in (("item", f.item, sorted(items)), ("severity", f.severity, SEVERITIES), ("cause", f.cause, CAUSES),
                                   ("status", f.status, STATUSES)):
            if value not in words:
                problems.append(f"finding {f.id}: the {name} {value!r} is not one of {list(words)}" if value else f"finding {f.id} has no {name}")
        findings.append(f)
    ids = {f.id for f in findings}
    for row in rows:
        for ref in row.findings:
            if ref not in ids:
                problems.append(f"row {row.id} names finding {ref}, which the findings sheet does not describe")

    if not problems:
        try:
            rule = verdict_of(tuple(rows), tuple(findings))
        except AuditError as exc:
            problems.append(str(exc))
        else:
            if cover["Verdict"] != rule:
                problems.append(f"the verdict on the form is {cover['Verdict']!r}; the rule gives {rule!r} for these results and findings")
    if problems:
        raise AuditError(f"{path.name}: " + "; ".join(problems))
    return ReturnedForm(path, cover, tuple(rows), tuple(findings), cover["Auditor"], audit_date, cover["Verdict"])


def our_results(path: Path | str) -> dict[str, str]:
    """The results our tools gave on a form, by item, filled in or not: what a later build of the same coupon is compared with."""
    from openpyxl import load_workbook

    sheet = load_workbook(path, data_only=True)[RUBRIC_SHEET]
    col = {name: RUBRIC_COLUMNS.index(name) + 1 for name in RUBRIC_COLUMNS}
    return {_text(sheet.cell(r, col["ID"]).value): _text(sheet.cell(r, col["Result"]).value) for r in range(2, sheet.max_row + 1)
            if _text(sheet.cell(r, col["Judged by"]).value) == "our tools"}


NOT_REGRESSIONS = ("A2",)  # how a package was built (a clean tree, an attempt number), not what the engine computes


def regressions(before: dict[str, str], now: dict[str, str]) -> list[str]:
    """The items our tools passed before and do not pass now; an item the rubric no longer has is not one, nor is A2."""
    return [item for item, result in before.items() if result == "Pass" and item in now and now[item] != "Pass" and item not in NOT_REGRESSIONS]
