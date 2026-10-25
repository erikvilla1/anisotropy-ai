"""The coupon audit (ADR-0043): one rubric that every audit of a coupon package is scored against.

The rubric (`paths.RUBRIC`) lists each check once: what is checked, what passes, who judges it (our tools or the auditor),
the tolerance, whether a Pass verdict needs it, the tests it applies to and what the team must send for it. This module reads
it and refuses one that is incomplete or inconsistent (ADR-0003): a missing field, an item numbered out of order or under an
unknown section, a test code `spec.TEST_CODES` does not know, or a function in `source` that does not exist.

`score` gives each item of a package its result from what our tools found (`Evidence`): a result for the items our tools
judge, and the evidence the auditor reads for the rest. `write_form` writes the audit form, the Excel workbook the auditor
fills in: the computed results locked, the auditor's cells open, the words of each answer offered as a list, the verdict the
rule gives as a formula that follows the auditor's entries, and, from `form_tables`, the numbers behind our rows as values
on a Results sheet and every compared value on a Compared values sheet (ADR-0044).

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


class Condition(Record):
    """What a coupon must satisfy for an item to apply to it; otherwise the item is N/A, with the reason stated."""

    min_free_length_widths: PositiveFloat  # the free length between the grips, in widths of the coupon


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
    condition: Condition | None = None  # when set, a coupon that does not meet it gets N/A on this item
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


def laminate_distance(check: LaminateCheck) -> tuple[float, float]:
    """How far the kernel's centre element is from free-edge laminate theory: the largest strain difference as a share of the largest
    laminate-theory strain, and the same for the ply stresses in material axes."""
    strain = float(np.max(np.abs(check.kernel_strain - check.strain)) / np.max(np.abs(check.strain)))
    stress = float(np.max(np.abs(check.kernel_ply_stress_12 - check.ply_stress_12)) / np.max(np.abs(check.ply_stress_12)))
    return strain, stress


def end_effect(check: LaminateCheck) -> tuple[float, float, float]:
    """Three measures of the grips' hold on the width: the free length in widths; the lateral section force at the centre as a share
    of the longitudinal one, zero with free lateral edges and more where the hold still reaches the centre; and the reaction's excess
    over free-edge laminate theory, the stiffening of the held ends, which under displacement control shifts strain from the ends to
    the free length even where N_x at the centre has faded."""
    n_x, n_y = check.kernel_section_force[0], check.kernel_section_force[1]
    restraint = abs(n_x / n_y) if n_y != 0.0 else float("nan")
    excess = check.kernel_reaction_N / check.reaction_N - 1.0 if check.reaction_N != 0.0 else float("nan")
    return check.free_length_m / check.width_m, restraint, excess


def _laminate(item: Item, ev: Evidence, facts: _Facts) -> tuple[str, str]:
    check = facts.laminate
    if check is None:
        return "Not checked", "no laminate-theory check for this model: " + facts.laminate_reason
    strain, stress = laminate_distance(check)
    widths, restraint, excess = end_effect(check)
    distance = (f"centre element {check.centre_element}: strain within {_pct(strain)} of the largest laminate-theory strain, ply stresses within "
                f"{_pct(stress)} of the largest ply stress; the free length is {widths:.2g} widths, N_x at the centre is {_pct(restraint)} of N_y, and "
                f"the reaction is {_pct(abs(excess))} {'above' if excess >= 0 else 'below'} free-edge theory (the held ends stiffen the coupon)")
    if item.condition is not None and widths < item.condition.min_free_length_widths:
        return "N/A", (f"the free length is {widths:.2g} widths, under the {item.condition.min_free_length_widths:g} the hand check needs: the grips' "
                       f"hold on the width reaches the gauge centre. For the record, {distance}")
    return ("Pass" if max(strain, stress) <= item.tolerance.relative else "Fail"), distance


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

COVER, RUBRIC_SHEET, FINDINGS = "Cover", "Rubric", "Findings"  # read back from a returned form: the first three sheets, in this order
RESULTS_SHEET, VALUES_SHEET = "Results", "Compared values"  # the numbers behind our rows, for the reader; not read back
AUDITOR_FIELDS = ("Auditor", "Audit date", "Verdict")  # the cover's cells the auditor fills in
RULE_FIELD = "Verdict by the rule"  # the cover's formula: the verdict the rule gives for the results and findings as they stand
DIGEST = "Our results digest"  # the cover row that lets a returned form show our tools' results were not changed
RUBRIC_COLUMNS = ("ID", "Section", "Check", "Acceptance", "Judged by", "Required", "Tolerance", "Result", "Evidence", "Observation", "Findings")
FINDING_COLUMNS = ("ID", "Item", "Severity", "Cause", "What was found", "Owner", "Status")
FINDING_ROWS = 30  # numbered rows offered on the form; a row without "What was found" is not a finding
RUBRIC_ROWS = 200  # how far down the rubric sheet the cover's formulas look: more rows than any rubric has
FONT = "Arial"
GLANCE = "At a glance"  # the cover's block of headline numbers
BY_SECTION = "Rows by section, as filled in"  # the cover's counts per section, formulas that follow the auditor's entries
TO_SEND = "For the next delivery, the team's export should also include"  # the cover's list of what the Not checked rows need


@dataclass(frozen=True)
class Table:
    """One table of our numbers on the Results sheet: a title, a header row, rows of values and a note under them."""

    title: str
    columns: tuple[str, ...]
    rows: tuple[tuple, ...]
    note: str = ""


@dataclass(frozen=True)
class FormTables:
    """The numbers behind the results, computed by our tools and written to the form as values (ADR-0001): the cover's lines at a
    glance, the tables of the Results sheet, every compared value for the Compared values sheet, and what the team's next export
    should include for the rows left Not checked."""

    glance: tuple[tuple[str, str], ...]
    tables: tuple[Table, ...]
    values: Table | None
    to_send: tuple[str, ...]


def form_tables(rubric: Rubric, evidence: Evidence, scored: tuple[Scored, ...]) -> FormTables:
    """The form's numbers, from the evidence the rows were scored from: the band agreement per quantity and layer, the gauge centre
    against laminate theory, the reaction, and every compared value."""
    ev = evidence
    length_unit, stress_unit = {"mm-MPa": ("mm", "MPa"), "m-Pa": ("m", "Pa")}[ev.units]
    items = {item.id: item for item in rubric.items}
    glance: list[tuple[str, str]] = []
    tables: list[Table] = []
    values: Table | None = None

    if ev.paired and ev.inner_band is not None:
        lo, hi = ev.inner_band
        quantities = list(dict.fromkeys(p.quantity for p in ev.paired))
        in_band = {q: [p for p in ev.paired if p.quantity == q and lo <= p.y <= hi] for q in quantities}
        largest_of = {q: max((abs(p.reference) for p in in_band[q]), default=0.0) for q in quantities}
        rows: list[tuple] = []
        for q in quantities:
            tolerance = items["C3" if q == "Mises" else "C2"].tolerance.relative
            largest = largest_of[q]
            for layer in [*sorted({p.layer for p in in_band[q]}), None]:
                group = in_band[q] if layer is None else [p for p in in_band[q] if p.layer == layer]
                if not group:
                    continue
                worst = max(group, key=lambda p: abs(p.difference))
                within = sum(abs(p.difference) <= tolerance * largest for p in group)
                share = abs(worst.difference) / largest if largest else None
                rows.append((q, "all" if layer is None else layer, len(group), within, 100 * tolerance, largest, abs(worst.difference),
                             None if share is None else 100 * share, worst.reference_element, worst.x, worst.y))
                if layer is None:
                    glance.append((f"{q} in the graded band", f"{within} of {len(group)} within {_pct(tolerance)} of {largest:.6g} {stress_unit}; worst "
                                   f"{_pct(share) if share is not None else 'n/a'} at team element {worst.reference_element}, layer {worst.layer}"))
        tables.append(Table(f"Stresses in the graded band, y {lo:g} to {hi:g} {length_unit}: the team's solver against ours",
                            ("Quantity", "Layer (1 = bottom)", "Values compared", "Within tolerance", "Tolerance (% of the largest team value)",
                             f"Largest team value ({stress_unit})", f"Worst difference ({stress_unit})", "Worst difference (% of the largest)",
                             "Team element of the worst", f"x ({length_unit})", f"y ({length_unit})"), tuple(rows),
                            "A value is within tolerance when |ours - team| is at most the tolerance times the largest team value of that quantity in the "
                            "band (rubric rows C2 and C3). The same numbers are in 4-results/team-vs-ours.csv."))
        values = Table("Every compared value: the team's reported value beside ours at the same element and layer",
                       ("Team element", "Our element", f"x ({length_unit})", f"y ({length_unit})", "Layer (1 = bottom)", "Quantity", f"Team ({stress_unit})",
                        f"Ours ({stress_unit})", f"Ours - team ({stress_unit})", "Share of the largest team value in the graded band", "In the graded band"),
                       tuple((p.reference_element, p.our_element, p.x, p.y, p.layer, p.quantity, p.reference, p.ours, p.difference,
                              abs(p.difference) / largest_of[p.quantity] if largest_of[p.quantity] else None, "yes" if lo <= p.y <= hi else "no")
                             for p in ev.paired))

    try:
        check: LaminateCheck | None = laminate_check(ev.our_deck, ev.solution)
    except KernelError:
        check = None
    hand_check = any(s.item.id == "D1" for s in scored)  # the gauge centre of an open-hole coupon is at the hole: no laminate theory there
    if check is not None and not hand_check:
        tables.append(Table("Reaction at the loaded grip (N)", ("Ours (kernel)", "Team"),
                            ((check.kernel_reaction_N, ev.team_reaction if ev.team_reaction is not None else "not exported"),),
                            "Rubric rows C1 and D2. The laminate-theory hand check (row D1) does not apply to this test."))
        glance.append(("Reaction at the loaded grip", f"ours {check.kernel_reaction_N:.6g} N; " + (
            f"team {ev.team_reaction:.6g} N, {_pct(abs(check.kernel_reaction_N - ev.team_reaction) / abs(ev.team_reaction))} apart"
            if ev.team_reaction is not None else "not in the team's export")))
    if check is not None and hand_check:
        widths, restraint, excess = end_effect(check)
        strain, stress = laminate_distance(check)
        per_length = 1.0 / from_si(1.0, "length", ev.units)  # N/m to N per stated length unit
        strain_scale = float(np.max(np.abs(check.strain)))
        force_scale = float(np.max(np.abs(check.section_force)))
        rows = [(name, float(theory), float(ours), 100 * abs(float(ours) - float(theory)) / strain_scale)
                for name, theory, ours in zip(("eps_x", "eps_y", "gamma_xy"), check.strain, check.kernel_strain)]
        rows += [(f"{name} (N/{length_unit})", float(theory) * per_length, float(ours) * per_length, 100 * abs(float(ours) - float(theory)) / force_scale)
                 for name, theory, ours in zip(("N_x", "N_y", "N_xy"), check.section_force, check.kernel_section_force)]
        condition = items["D1"].condition if "D1" in items else None
        if condition is None:
            applies_note = applies_short = ""
        elif widths >= condition.min_free_length_widths:
            applies_note, applies_short = f" Rubric row D1 applies from {condition.min_free_length_widths:g} widths.", ""
        else:
            applies_note = f" Rubric row D1 applies from {condition.min_free_length_widths:g} widths, so for this coupon it is N/A."
            applies_short = f"; row D1 is N/A under {condition.min_free_length_widths:g} widths"
        tables.append(Table(f"Gauge centre, element {check.centre_element}: laminate theory with free lateral edges against our kernel",
                            ("Quantity", "Laminate theory", "Ours (kernel)", "Difference (% of the largest theory value of its kind)"), tuple(rows),
                            f"Strains are dimensionless; section forces are per unit width. The free length between the grips is "
                            f"{from_si(check.free_length_m, 'length', ev.units):.4g} {length_unit}, {widths:.2g} widths. N_x at the centre is "
                            f"{_pct(restraint)} of N_y: the hold the grips keep on the width there, zero with free edges. The reaction is "
                            f"{_pct(abs(excess))} {'above' if excess >= 0 else 'below'} free-edge theory: the held ends stiffen the coupon, and under "
                            f"displacement control the free length then carries a little more strain than the pull over the free length.{applies_note}"))
        ply_rows = []
        for k, ply in enumerate(check.plies):
            theory = [float(v) for v in from_si(check.ply_stress_12[k], "stress", ev.units)]
            ours = [float(v) for v in from_si(check.kernel_ply_stress_12[k], "stress", ev.units)]
            ply_rows.append((k + 1, ply.angle_deg, theory[0], ours[0], theory[1], ours[1], theory[2], ours[2]))
        tables.append(Table(f"Ply stresses at the gauge centre in material axes ({stress_unit}): laminate theory against our kernel",
                            ("Ply (1 = bottom)", "Angle (deg)", "S11 theory", "S11 ours", "S22 theory", "S22 ours", "S12 theory", "S12 ours"), tuple(ply_rows),
                            f"The largest difference is {_pct(stress)} of the largest theory value, and the strains above differ by {_pct(strain)} "
                            "(rubric row D1)."))
        if ev.team_reaction is not None:
            team = f"team {ev.team_reaction:.6g} N, {_pct(abs(check.kernel_reaction_N - ev.team_reaction) / abs(ev.team_reaction))} apart"
        else:
            team = "not in the team's export"
        tables.append(Table("Reaction at the loaded grip (N)", ("Laminate theory", "Ours (kernel)", "Team"),
                            ((check.reaction_N, check.kernel_reaction_N, ev.team_reaction if ev.team_reaction is not None else "not exported"),),
                            "Laminate theory is the free-edge laminate under the same pull or load (rubric rows C1 and D2)."))
        glance.append(("Reaction at the loaded grip", f"ours {check.kernel_reaction_N:.6g} N; {team}"))
        glance.append(("Hand check at the gauge centre", f"strain within {_pct(strain)} and ply stresses within {_pct(stress)} of laminate theory with "
                       f"free edges; the free length is {widths:.2g} widths{applies_short}"))

    to_send = tuple(f"{s.item.id} ({s.item.check}): {s.item.needs}" for s in scored if s.result == "Not checked" and s.item.needs)
    return FormTables(tuple(glance), tuple(tables), values, to_send)


def write_form(path: Path | str, rubric: Rubric, scored: tuple[Scored, ...], cover: list[tuple[str, str]], units: str,
               tables: FormTables | None = None) -> Path:
    """The audit form. The cover: the package's identity, the auditor's fields, the verdict the rule gives (a formula that follows the
    auditor's entries), the headline numbers, a count per section and what the next export should include. The rubric, with our
    results locked and the auditor's cells open, and a findings table. With `tables`, a Results sheet of the numbers behind our rows
    and a Compared values sheet of every value compared. Lists offer the fixed words, results are coloured, and every sheet prints on
    letter paper. The sheets are protected without a password, so a cell is not changed by accident (this is not a security measure)."""
    from openpyxl import Workbook
    from openpyxl.formatting.rule import CellIsRule, FormulaRule
    from openpyxl.styles import Alignment, Font, PatternFill, Protection
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.page import PageMargins
    from openpyxl.worksheet.properties import PageSetupProperties

    path = Path(path)
    bold, title = Font(name=FONT, bold=True, size=10), Font(name=FONT, bold=True, size=14)
    wrap = Alignment(wrap_text=True, vertical="top")
    open_cell = PatternFill("solid", fgColor="FFF4CC")  # the auditor's cells
    header_fill = PatternFill("solid", fgColor="DDE6F0")
    unlocked = Protection(locked=False)
    shades = {"Pass": ("C6EFCE", "006100"), "Pass with observations": ("FFEB9C", "9C5700"), "Fail": ("FFC7CE", "9C0006"),
              "N/A": ("EDEDED", "595959"), "Not checked": ("EDEDED", "595959"), "Blocker": ("FFC7CE", "9C0006"), "Major": ("FFC7CE", "9C0006"),
              "Minor": ("FFEB9C", "9C5700"), "Open": ("FFEB9C", "9C5700")}
    length_unit, stress_unit = {"mm-MPa": ("mm", "MPa"), "m-Pa": ("m", "Pa")}[units]
    letter = {name: get_column_letter(i + 1) for i, name in enumerate(RUBRIC_COLUMNS)}
    fletter = {name: get_column_letter(i + 1) for i, name in enumerate(FINDING_COLUMNS)}

    def listing(sheet, words, cells: list[str]) -> None:
        validation = DataValidation(type="list", formula1='"' + ",".join(words) + '"', allow_blank=True)
        sheet.add_data_validation(validation)
        for cell in cells:
            validation.add(cell)

    def protect(sheet) -> None:
        sheet.protection.sheet = True
        sheet.protection.formatColumns = False  # widths and heights may still be changed
        sheet.protection.formatRows = False

    def shade(sheet, cells: str, words) -> None:
        """A result or a severity shows its colour wherever it is written, by the auditor too."""
        for word in words:
            fill, ink = shades[word]
            sheet.conditional_formatting.add(cells, CellIsRule(operator="equal", formula=[f'"{word}"'], fill=PatternFill("solid", fgColor=fill),
                                                               font=Font(name=FONT, color=ink)))

    def printable(sheet, landscape: bool, title_rows: str | None = None) -> None:
        sheet.page_setup.orientation = "landscape" if landscape else "portrait"
        sheet.page_setup.paperSize = sheet.PAPERSIZE_LETTER
        sheet.page_setup.fitToWidth, sheet.page_setup.fitToHeight = 1, 0  # one page wide, as many pages long as it takes
        sheet.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
        sheet.page_margins = PageMargins(left=0.4, right=0.4, top=0.6, bottom=0.6)
        sheet.oddFooter.center.text = "&A, page &P of &N"
        if title_rows:
            sheet.print_title_rows = title_rows

    def fit_rows(sheet, widths: dict[int, float], first: int, last: int) -> None:
        """Row heights from the longest wrapped text in each row: Excel does not fit them itself for a file it did not write."""
        for r in range(first, last + 1):
            lines = 1
            for col, width in widths.items():
                text = sheet.cell(r, col).value
                if isinstance(text, str) and text and not text.startswith("="):
                    per_line = max(1, int(width * 1.15))
                    lines = max(lines, sum(max(1, -(-len(part) // per_line)) for part in text.split("\n")))
            if lines > 1:
                sheet.row_dimensions[r].height = min(409, 13.0 * lines + 4)

    def rubric_range(name: str) -> str:
        return f"{RUBRIC_SHEET}!${letter[name]}$2:${letter[name]}${RUBRIC_ROWS}"

    def finding_range(name: str) -> str:
        return f"{FINDINGS}!${fletter[name]}$2:${fletter[name]}${FINDING_ROWS + 1}"

    def rule_formula() -> str:
        """verdict_of, as a formula: Fail if a required row fails or a Blocker or Major finding is open; Pass with observations if anything
        else failed or any finding is open; Pass otherwise; no verdict while a required row has no result other than Not checked."""
        required, result = rubric_range("Required"), rubric_range("Result")
        what, severity, status = finding_range("What was found"), finding_range("Severity"), finding_range("Status")
        missing = f'COUNTIFS({required},"yes",{result},"Not checked")+COUNTIFS({required},"yes",{result},"")'
        required_fail = f'COUNTIFS({required},"yes",{result},"Fail")'
        open_major = f'COUNTIFS({what},"<>",{status},"Open",{severity},"Blocker")+COUNTIFS({what},"<>",{status},"Open",{severity},"Major")'
        any_fail, any_open = f'COUNTIF({result},"Fail")', f'COUNTIFS({what},"<>",{status},"Open")'
        return (f'=IF({missing}>0,"no verdict yet: "&({missing})&" required row(s) have no result other than Not checked",'
                f'IF(OR({required_fail}>0,{open_major}>0),"Fail",IF(OR({any_fail}>0,{any_open}>0),"Pass with observations","Pass")))')

    def section_formula(section_id: str) -> str:
        ids, result = rubric_range("ID"), rubric_range("Result")
        prefix = f'"{section_id}*"'
        count = lambda word: f'COUNTIFS({ids},{prefix},{result},"{word}")'  # noqa: E731
        return ("=" + count("Pass") + '&" pass, "&' + count("Fail") + '&" fail, "&' + count("N/A") + '&" not applicable, "&' + count("Not checked")
                + '&" not checked, "&' + count("") + f'&" without a result, of "&COUNTIF({ids},{prefix})')

    def findings_formula() -> str:
        what, status = finding_range("What was found"), finding_range("Status")
        return f'=COUNTIFS({what},"<>",{status},"Open")&" open, "&COUNTIFS({what},"<>",{status},"Closed")&" closed"'

    book = Workbook()
    book.properties.creator = "Anisotropy AI"
    book.properties.title = f"Coupon audit: {dict(cover).get('Package', path.stem)}"
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
            shade(sheet, cell.coordinate, VERDICTS)
        row += 1
    sheet.cell(row, 1, RULE_FIELD).font = bold
    rule = sheet.cell(row, 2, rule_formula())
    rule.alignment = wrap
    shade(sheet, rule.coordinate, VERDICTS)
    sheet.conditional_formatting.add(rule.coordinate, FormulaRule(formula=[f'LEFT({rule.coordinate},2)="no"'], fill=PatternFill("solid", fgColor="EDEDED")))
    row += 1
    note = sheet.cell(row, 1, "The rule's verdict is computed on this sheet from the Rubric and Findings sheets as you fill them in. Your verdict above "
                              "must equal it; a form that differs is refused.")
    note.alignment = wrap
    sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    sheet.row_dimensions[row].height = 30
    row += 2

    if tables is not None and tables.glance:
        sheet.cell(row, 1, GLANCE).font = bold
        row += 1
        for label, value in tables.glance:
            sheet.cell(row, 1, label)
            sheet.cell(row, 2, value).alignment = wrap
            row += 1
        row += 1
    sheet.cell(row, 1, BY_SECTION).font = bold
    row += 1
    for section in rubric.sections:
        if any(s.item.section == section.id for s in scored):
            sheet.cell(row, 1, f"{section.id}. {section.title}")
            sheet.cell(row, 2, section_formula(section.id)).alignment = wrap
            row += 1
    sheet.cell(row, 1, "Findings")
    sheet.cell(row, 2, findings_formula())
    row += 2

    legend = [
        "How to fill it in: on the Rubric sheet, give a Result for every row judged by the auditor, and add an Observation where you have one. "
        "Rows judged by our tools are filled in and locked. Record each problem on the Findings sheet and put its ID in the Findings column of "
        "the rubric row it is about. Then give your name, the date and the verdict above. The yellow cells are yours; the rest is locked, without "
        "a password, so that nothing changes by accident.",
        "The verdict: Fail if a required row fails or a Blocker or Major finding is open; Pass with observations if anything else failed or any "
        "finding is open; Pass otherwise. A verdict needs every required row to have a result other than Not checked. The row 'Verdict by the "
        "rule' computes it as you go.",
        "Example finding, on the Findings sheet: F1 | C6 | Minor | their model | S22 peaks one element nearer the tab line in the team's model than "
        "in ours | J. Doe | Open. Then write F1 in the Findings column of rubric row C6.",
        *(["The Results sheet holds the numbers behind our tools' rows" + (", and Compared values every value compared, with a filter. Both are also in "
           "the package's 4-results folder." if tables.values is not None else ". Our ply stresses are also in the package's 4-results folder.")]
          if tables is not None and tables.tables else []),
        "Put the filled-in form back in the folder you received the package in.",
    ]
    for line in legend:
        cell = sheet.cell(row, 1, line)
        cell.alignment = wrap
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        sheet.row_dimensions[row].height = 14.0 * max(1, -(-len(line) // 125)) + 4
        row += 1
    if tables is not None and tables.to_send:
        row += 1
        sheet.cell(row, 1, TO_SEND).font = bold
        row += 1
        for line in tables.to_send:
            cell = sheet.cell(row, 1, line)
            cell.alignment = wrap
            sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
            sheet.row_dimensions[row].height = 14.0 * max(1, -(-len(line) // 125)) + 4
            row += 1
    sheet.column_dimensions["A"].width = 26
    sheet.column_dimensions["B"].width = 90
    fit_rows(sheet, {2: 90}, 3, row)
    protect(sheet)
    printable(sheet, landscape=False)

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
    if auditor_rows:
        listing(sheet, RESULTS, [f"{letter['Result']}{r}" for r in auditor_rows])
    shade(sheet, f"{letter['Result']}2:{letter['Result']}{last}", RESULTS)
    widths = (6, 18, 26, 40, 10, 9, 10, 12, 60, 36, 12)
    for name, width in zip(RUBRIC_COLUMNS, widths):
        sheet.column_dimensions[letter[name]].width = width
    fit_rows(sheet, {i + 1: w for i, w in enumerate(widths)}, 2, last)
    sheet.freeze_panes = "C2"
    protect(sheet)
    printable(sheet, landscape=True, title_rows="1:1")

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
        listing(sheet, words, [f"{fletter[name]}{first}:{fletter[name]}{end}"])
    shade(sheet, f"{fletter['Severity']}{first}:{fletter['Severity']}{end}", ("Blocker", "Major", "Minor"))
    shade(sheet, f"{fletter['Status']}{first}:{fletter['Status']}{end}", ("Open",))
    for name, width in zip(FINDING_COLUMNS, (6, 8, 13, 15, 70, 16, 10)):
        sheet.column_dimensions[fletter[name]].width = width
    sheet.freeze_panes = "B2"
    protect(sheet)
    printable(sheet, landscape=True, title_rows="1:1")

    if tables is not None and tables.tables:
        sheet = book.create_sheet(RESULTS_SHEET)
        sheet["A1"] = "The numbers behind our tools' rows"
        sheet["A1"].font = title
        sheet["A2"] = (f"Computed by our tools while the package was built, from the same evidence as the rubric's rows. Lengths in {length_unit}, "
                       f"stresses in {stress_unit}, forces in N. These are values, not formulas: the engine computes every number (ADR-0001).")
        sheet["A2"].alignment = wrap
        sheet.merge_cells("A2:H2")
        sheet.row_dimensions[2].height = 30
        row, columns = 4, 1
        for t in tables.tables:
            sheet.cell(row, 1, t.title).font = Font(name=FONT, bold=True, size=11)
            row += 1
            for j, name in enumerate(t.columns, start=1):
                cell = sheet.cell(row, j, name)
                cell.font, cell.fill, cell.alignment = bold, header_fill, wrap
            sheet.row_dimensions[row].height = 44
            row += 1
            for values_row in t.rows:
                for j, value in enumerate(values_row, start=1):
                    sheet.cell(row, j, value)
                row += 1
            if t.note:
                cell = sheet.cell(row, 1, t.note)
                cell.alignment = wrap
                sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=max(4, len(t.columns)))
                sheet.row_dimensions[row].height = 14.0 * max(1, -(-len(t.note) // 120)) + 4
                row += 1
            row += 1
            columns = max(columns, len(t.columns))
        sheet.column_dimensions["A"].width = 30
        for j in range(2, columns + 1):
            sheet.column_dimensions[get_column_letter(j)].width = 16
        protect(sheet)
        printable(sheet, landscape=True)

    if tables is not None and tables.values is not None:
        sheet = book.create_sheet(VALUES_SHEET)
        sheet.append(list(tables.values.columns))
        for cell in sheet[1]:
            cell.font, cell.fill, cell.alignment = bold, header_fill, wrap
        sheet.row_dimensions[1].height = 44
        for values_row in tables.values.rows:
            sheet.append(list(values_row))
        for j in range(1, len(tables.values.columns) + 1):
            sheet.column_dimensions[get_column_letter(j)].width = 14
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = f"A1:{get_column_letter(len(tables.values.columns))}{len(tables.values.rows) + 1}"
        printable(sheet, landscape=True, title_rows="1:1")  # left open, so the filter and sorting work; the digest covers the results, not this sheet

    for sheet in book.worksheets:
        for cells in sheet.iter_rows():
            for cell in cells:
                if cell.value is not None:
                    font = cell.font
                    cell.font = Font(name=FONT, size=font.sz or 10, bold=font.b, italic=font.i, color=font.color)

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
    if book.sheetnames[:3] != [COVER, RUBRIC_SHEET, FINDINGS]:  # the sheets of our numbers, or any the auditor adds, may follow
        raise AuditError(f"{path.name}: the sheets are {book.sheetnames}, not {[COVER, RUBRIC_SHEET, FINDINGS]} first")

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
