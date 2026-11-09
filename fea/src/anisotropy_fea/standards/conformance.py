"""A coupon judged against the standard it names (ADR-0072): every requirement of the profile, met, a deviation, an advisory, a note, the
laboratory's, or not applicable, with this coupon's value and what the clause asks, in the coupon's units.

The judgement is of the specimen as the model states it, never of a test: the clauses of the procedure stay the laboratory's, and a model
that meets every requirement it can is still not said to conform. A deviation never stops a run; the document and the checklist state it.
"""

from __future__ import annotations

from dataclasses import dataclass

from anisotropy_engine.library import find_dataset

from ..spec import CouponSpec, full_angles, normalised_angle, spec_ply_thickness
from . import PROFILES
from .profile import Preset, Profile, Requirement, Subject

STATE_OF_MISS = {"scope": "deviation", "mandatory": "deviation", "recommended": "advisory", "note": "note"}
JUDGED_LEVELS = ("scope", "mandatory")  # the requirements a deviation is counted against


@dataclass(frozen=True)
class Judged:
    requirement: Requirement
    state: str
    value: str
    limit: str

    def as_dict(self) -> dict:
        r = self.requirement
        return {"id": r.id, "clause": r.clause, "level": r.level, "text": r.text, "state": self.state, "value": self.value, "limit": self.limit,
                "rows": list(r.rows)}


@dataclass(frozen=True)
class Conformance:
    profile: Profile
    subject: Subject
    preset: Preset | None  # the specimen (C1869 A or B) or the laminate's class (D3039 Table 2) the coupon is held to
    judged: tuple[Judged, ...]
    checked: str = "specimen"  # what was checked: a coupon's specimen, or a fibre tow's test record (ADR-0073)
    judged_by: str = "a model can meet"  # which requirements count: those a model can meet, or those the record shows

    def count(self, state: str) -> int:
        return sum(1 for j in self.judged if j.state == state)

    @property
    def deviations(self) -> tuple[Judged, ...]:
        return tuple(j for j in self.judged if j.state == "deviation")

    @property
    def advisories(self) -> tuple[Judged, ...]:
        return tuple(j for j in self.judged if j.state == "advisory")

    def held_to(self) -> str:
        """What the coupon is held to beyond the standard itself: its specimen or its laminate's class."""
        s = self.subject
        if self.profile.variants:
            return f"Specimen {s.variant}" if s.variant else "no specimen named"
        if self.profile.classes:
            return f"{self.preset.label} class ({self.preset.clause})" if self.preset is not None else "no class of Table 2"
        return ""

    def words(self) -> str:
        """One sentence for the checklist and the document's cover: what was checked and what came out, never "conforms"."""
        judged = [j for j in self.judged if j.requirement.level in JUDGED_LEVELS and j.state in ("met", "deviation")]
        met = sum(1 for j in judged if j.state == "met")
        held = self.held_to()
        parts = [f"{self.checked} checked against {self.profile.designation}" + (f", {held}" if held else "")
                 + f": {met} of {len(judged)} requirement{'s' if len(judged) != 1 else ''} {self.judged_by} {'is' if met == 1 else 'are'} met"]
        if self.deviations:
            parts.append(f"{len(self.deviations)} deviation{'s' if len(self.deviations) != 1 else ''} to report ("
                         + "; ".join(f"{j.requirement.clause}: {j.value}, against {j.limit}" for j in self.deviations) + ")")
        if self.advisories:
            parts.append(f"{len(self.advisories)} recommendation{'s' if len(self.advisories) != 1 else ''} not followed")
        lab = self.count("lab")
        parts.append(f"{lab} clauses of the procedure are the laboratory's")
        return "; ".join(parts)

    def deviation_rows(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(key for j in self.deviations for key in j.requirement.rows))

    def as_dict(self) -> dict:
        return {"id": self.profile.id, "designation": self.profile.designation, "held_to": self.held_to(), "words": self.words(),
                "deviations": len(self.deviations), "advisories": len(self.advisories), "requirements": [j.as_dict() for j in self.judged]}


def subject_of(spec: CouponSpec) -> Subject:
    """The coupon as the profiles read it: the spec's geometry, laminate, material family and measurement, in SI."""
    if not spec.si:
        raise ValueError("subject_of needs the spec in SI (load_spec or to_si)")
    g, mat = spec.geometry, spec.material
    family = architecture = None
    if mat.library is not None:
        record = find_dataset(mat.library, mat.dataset)
        family, architecture = record.get("family"), record.get("architecture")
    method, strain, tabs = spec.test_method, spec.strain, spec.tabs
    return Subject(kind=spec.kind, units=spec.units, length=g.length, width=g.width, tab_length=g.tab_length or 0.0, hole_diameter=g.hole_diameter,
                   angles=tuple(normalised_angle(a) for a in full_angles(spec)), ply_thickness=spec_ply_thickness(spec), family=family,
                   architecture=architecture, variant=method.variant if method is not None else None,
                   strain_device=strain.device if strain is not None else None, strain_length=strain.gauge_length if strain is not None else None,
                   tab_thickness=tabs.thickness if tabs is not None else None, tab_bevel=tabs.bevel if tabs is not None else None,
                   tab_material=tabs.material if tabs is not None else None)


def judge(requirement: Requirement, subject: Subject) -> Judged:
    if requirement.rule is None:
        return Judged(requirement, "lab", "", "")
    found = requirement.rule(subject)
    if found.ok is None:
        state = "na"
    elif found.ok:
        state = "na" if requirement.level == "note" else "met"
    else:
        state = STATE_OF_MISS[requirement.level]
    return Judged(requirement, state, found.value, found.limit)


def conformance(spec: CouponSpec) -> Conformance | None:
    """The spec judged against the standard its [test_method] names; None when it names none. The spec must be in SI."""
    if spec.test_method is None:
        return None
    profile = PROFILES[spec.test_method.id]
    subject = subject_of(spec)
    if profile.variants:
        preset = next((v for v in profile.variants if v.key == subject.variant), None)
    else:
        preset = profile.classify(subject) if profile.classify is not None else None
    return Conformance(profile, subject, preset, tuple(judge(r, subject) for r in profile.requirements))
