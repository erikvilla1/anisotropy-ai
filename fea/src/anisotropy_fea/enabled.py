"""The tests the studio offers until the first workflow is validated (ADR-0089).

One workflow first: the unnotched tension coupon, under ASTM D3039 or under no standard, is built in Anisotropy and in Abaqus and
every output is compared until they match; the other tests wait, hidden and kept, and each comes back through the same workflow.
This module is the one list. The form's definition carries it to the page (`tools/export_form_definition.py`, the `enabled` block),
which offers nothing else; the setup check refuses anything else by row (ADR-0089, part 2).

`ANISOTROPY_ALL_TESTS=on` shows every test again, for development: the switch is read on every call, `off` or unset keeps the list,
and any other value is refused (ADR-0003). The hosted tier never sets it. Nothing here deletes or changes a hidden test's code,
specs, checks or records: they all stay, and the committed checks of every kind keep running.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from .standards import NONE, PROFILES

ALL_TESTS_VARIABLE = "ANISOTROPY_ALL_TESTS"
SWITCH_WORDS = ("on", "off")

TESTS: tuple[str, ...] = ("unnotched tension",)  # the Test row's words the studio offers
STANDARDS: tuple[str, ...] = ("astm-d3039",)  # the profiles offered, by id; "none" (no standard) is always offered
MATERIAL_KINDS: tuple[str, ...] = ("plies",)  # a laminate of plies; one isotropic material (the plastic of ASTM D638) waits
DOGBONE = False  # the dog-bone's rows (ADR-0075) wait with D638: a tension coupon is a straight strip

# The words a customer reads when something is held back (ADR-0091 amendment 2): what is not offered, and what is. Every refusal of a
# hidden test, standard or material holds NOT_OFFERED, which the API matches (anisotropy_api.coupon_jobs.NOT_OFFERED).
NOT_OFFERED = "not offered yet"
OFFERED = "This workspace runs the unnotched tension coupon, under ASTM D3039 or no standard."
NOT_AVAILABLE = f"{NOT_OFFERED}. {OFFERED}"
# a tension coupon's layup reads the same from both faces (the founder, 2026-11-11: "do a for right now"; ADR-0089 amendment 4): an
# unsymmetric one bends as it is pulled, which the package, its every-output file and the comparison with Abaqus do not cover yet
SYMMETRIC_ONLY = True
UNSYMMETRIC = "This layup is not symmetric. Use a layup that reads the same from both faces, such as [0/45/-45/90]s."


class SwitchError(ValueError):
    """The switch holds a word other than on or off."""


def all_tests(environ: Mapping[str, str] | None = None) -> bool:
    """Whether every test is offered: `ANISOTROPY_ALL_TESTS` is `on`. Unset, blank or `off` keeps the list; any other value is refused."""
    raw = (os.environ if environ is None else environ).get(ALL_TESTS_VARIABLE)
    word = (raw or "").strip().lower()
    if not word:
        return False
    if word not in SWITCH_WORDS:
        raise SwitchError(f"{ALL_TESTS_VARIABLE} must be 'on' or 'off', not {raw!r}; unset it to offer the unnotched tension coupon only (ADR-0089)")
    return word == "on"


def standard_designations() -> tuple[str, ...]:
    """The designations of the offered standards, as the Standard row writes them ("ASTM D3039/D3039M-17")."""
    return tuple(PROFILES[profile_id].designation for profile_id in STANDARDS)


def is_test_enabled(test: str, every: bool) -> bool:
    """Whether the Test row's word is offered."""
    return every or test in TESTS


def is_standard_enabled(word: str | None, every: bool) -> bool:
    """Whether the Standard row's word is offered: no standard always, a designation when its profile is on the list."""
    if every or not word or word.strip().lower() == NONE:
        return True
    return word.strip().lower() in {d.lower() for d in standard_designations()}


def is_material_kind_enabled(word: str | None, every: bool) -> bool:
    """Whether the Material kind row's word is offered; blank means a laminate of plies."""
    return every or not word or word.strip().lower() in MATERIAL_KINDS


def is_layup_enabled(angles: list[float] | tuple[float, ...], every: bool) -> bool:
    """Whether a layup, every ply bottom first, is offered: one that reads the same from both faces, or any with the switch on."""
    return every or not SYMMETRIC_ONLY or list(angles) == list(reversed(angles))


def offered_words(key: str, words: tuple[str, ...] | list[str], every: bool) -> tuple[str, ...]:
    """A list row's words as offered: the Test, Standard and Material kind rows filtered by the list, every other row as it is."""
    if key == "test":
        return tuple(w for w in words if is_test_enabled(w, every))
    if key == "standard":
        return tuple(w for w in words if is_standard_enabled(w, every))
    if key == "material_kind":
        return tuple(w for w in words if is_material_kind_enabled(w, every))
    return tuple(words)


def refuse_hidden_kind(kind: str, name: str, every: bool | None = None) -> None:
    """Refuse a stored coupon of a hidden test (reopening it, running it by name): NotOffered names the coupon and the test."""
    from .spec import TEST_CODES  # the spec imports the standards; imported here so this module stays importable on its own

    every = all_tests() if every is None else every
    test = TEST_CODES[kind][1] if kind in TEST_CODES else kind
    if not is_test_enabled(test, every):
        raise NotOffered(f"{name}: its test, {test}, is {NOT_OFFERED}, and the coupon is kept. {OFFERED}")


class NotOffered(ValueError):
    """A coupon of a test the studio does not offer yet (ADR-0089). Its message holds the words of NOT_OFFERED."""


def definition() -> dict:
    """The `enabled` block of the form's definition: the list itself, never the switch, so the page's file is the same however the
    process was started; the page asks the API whether the switch is on (`GET /v1/coupon-tests`)."""
    return {"tests": list(TESTS), "standards": list(standard_designations()), "material_kinds": list(MATERIAL_KINDS), "dogbone": DOGBONE,
            "not_available": NOT_AVAILABLE, "not_offered": NOT_OFFERED, "offered": OFFERED, "symmetric_only": SYMMETRIC_ONLY, "unsymmetric": UNSYMMETRIC,
            "switch": ALL_TESTS_VARIABLE}
