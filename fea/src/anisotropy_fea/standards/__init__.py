"""The test standards a coupon may follow, as profiles our checks read (ADR-0072).

The form's Standard row offers "none" and the designation of every profile here whose kinds include the coupon's test; a spec that names
one carries `[test_method] id`. ASTM D4018 covers the fibre tow test, which is no spec kind: `tow_test` judges its record (ADR-0073). `conformance.conformance` judges a spec against its profile. This package imports nothing of the spec, so
the spec can import it.
"""

from __future__ import annotations

from . import astm_c1869, astm_d3039, astm_d4018
from .profile import INCH_POUND_SYSTEMS, LEVELS, STATES, Finding, Preset, Profile, Requirement, Subject

NONE = "none"  # the Standard row's word for a coupon that follows no standard
PROFILES: dict[str, Profile] = {profile.id: profile for profile in (astm_d3039.PROFILE, astm_c1869.PROFILE, astm_d4018.PROFILE)}
BY_DESIGNATION: dict[str, Profile] = {profile.designation: profile for profile in PROFILES.values()}
VARIANT_WORDS: tuple[str, ...] = tuple(dict.fromkeys(word for profile in PROFILES.values() for word in profile.variant_words))  # the Specimen row's words
STANDARD_WORDS: tuple[str, ...] = (NONE, *BY_DESIGNATION)  # the Standard row's words


def profile_of_word(word: str | None) -> Profile | None:
    """The profile a Standard row's word names; None for "none" or a blank row. An unknown word is the form's to refuse."""
    if not word or word.lower() == NONE:
        return None
    return next((p for p in PROFILES.values() if p.designation.lower() == word.lower()), None)


def profiles_for(kind: str) -> list[Profile]:
    """The profiles that cover a test, in the order the form lists them."""
    return [profile for profile in PROFILES.values() if kind in profile.kinds]


__all__ = ["BY_DESIGNATION", "INCH_POUND_SYSTEMS", "LEVELS", "NONE", "PROFILES", "STANDARD_WORDS", "STATES", "VARIANT_WORDS", "Finding", "Preset",
           "Profile", "Requirement", "Subject", "profile_of_word", "profiles_for"]
