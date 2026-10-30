"""The units boundary: a deck carries no units; the caller states them; SI inside (ADR-0002, ADR-0003)."""

from pathlib import Path

import pytest

from anisotropy_fea.abaqus_reader import parse_deck
from anisotropy_fea.model import to_si as deck_to_si
from anisotropy_fea.units import DECK_UNIT_SYSTEMS, from_si, to_si, unit_factors
from anisotropy_fea import paths  # where the files live (ADR-0036)

DECK = paths.CHECK_DECKS / "coupon-1x1-im7-8552.inp"


def test_the_two_systems_and_their_factors():
    assert set(DECK_UNIT_SYSTEMS) == {"mm-MPa", "m-Pa"}
    assert unit_factors("mm-MPa") == {"length": 1e-3, "stress": 1e6, "force": 1.0, "force_per_length": 1e3, "per_length": 1e3}
    assert unit_factors("m-Pa") == {"length": 1.0, "stress": 1.0, "force": 1.0, "force_per_length": 1.0, "per_length": 1.0}
    assert from_si(461.869e3, "force_per_length", "mm-MPa") == pytest.approx(461.869)  # N/m to N/mm
    assert from_si(2.0, "per_length", "mm-MPa") == pytest.approx(2e-3)  # a curvature of 2 per m is 0.002 per mm


def test_scalar_conversions_round_trip():
    assert to_si(80.0, "length", "mm-MPa") == pytest.approx(0.080)
    assert to_si(162095.74, "stress", "mm-MPa") == pytest.approx(162095.74e6)
    assert to_si(12.5, "force", "mm-MPa") == 12.5
    assert from_si(to_si(0.8, "length", "mm-MPa"), "length", "mm-MPa") == pytest.approx(0.8)
    assert to_si(3.0, "stress", "m-Pa") == 3.0


@pytest.mark.parametrize("bad", [None, "", "in-psi", "MM-MPA", "SI"])
def test_unknown_or_missing_units_are_refused(bad):
    with pytest.raises(ValueError, match="units must be stated"):
        unit_factors(bad)


def test_deck_conversion_scales_lengths_stresses_and_prescribed_displacements_only():
    deck = parse_deck(DECK.read_text(encoding="utf-8"))
    si = deck_to_si(deck, "mm-MPa")
    part, part_si = deck.parts["Coupon"], si.parts["Coupon"]
    assert part_si.nodes.xyz[2].tolist() == pytest.approx([0.025, 0.100, 0.0])
    assert part_si.sections[0].layers[0].thickness == pytest.approx(0.18288e-3)
    assert part_si.sections[0].layers[0].integration_points == 3  # counts are not scaled
    assert si.materials["IM7-8552"].elastic.E2 == pytest.approx(8963.18e6)
    assert si.materials["IM7-8552"].elastic.nu12 == 0.316  # ratios are not scaled
    assert si.materials["IM7-8552"].fail_stress.Xc == pytest.approx(-1731.48e6)
    (pull,) = [b for b in si.steps[0].boundaries if b.target == "Top"]
    assert pull.value == pytest.approx(0.8e-3)
    assert si.units == "mm-MPa" and deck.units is None
    assert part.nodes.xyz[2].tolist() == [25.0, 100.0, 0.0]  # the unitless deck is untouched


def test_m_pa_is_the_identity():
    deck = parse_deck(DECK.read_text(encoding="utf-8"))
    with pytest.warns(UserWarning, match="outside 1 GPa to 1000 GPa"):
        si = deck_to_si(deck, "m-Pa")  # these moduli are MPa numbers, so m-Pa is the wrong statement and the reader says so
    assert si.materials["IM7-8552"].elastic.E1 == 162095.74
    assert si.parts["Coupon"].nodes.xyz[2].tolist() == [25.0, 100.0, 0.0]


def test_plausible_moduli_do_not_warn(recwarn):
    deck = parse_deck(DECK.read_text(encoding="utf-8"))
    deck_to_si(deck, "mm-MPa")
    assert not [w for w in recwarn if "GPa" in str(w.message)]
