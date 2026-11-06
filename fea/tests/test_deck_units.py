"""The units boundary: a coupon is stated in one of four systems, a deck carries no units and is read in one of the two deck
systems; SI inside (ADR-0002, ADR-0003, ADR-0061)."""

from pathlib import Path

import pytest

from anisotropy_fea.abaqus_reader import parse_deck
from anisotropy_fea.model import to_si as deck_to_si
from anisotropy_engine.units import INCH, LBF, PSI
from anisotropy_fea.units import (DECK_UNIT_SYSTEMS, UNIT_LABEL, UNIT_SYSTEMS, deck_unit_factors, deck_units_of, from_si, to_si, unit_factors,
                                  units_words)
from anisotropy_fea import paths  # where the files live (ADR-0036)

DECK = paths.CHECK_DECKS / "coupon-1x1-im7-8552.inp"


def test_the_two_deck_systems_and_their_factors():
    assert set(DECK_UNIT_SYSTEMS) == {"mm-MPa", "m-Pa"}
    assert deck_unit_factors("mm-MPa") == unit_factors("mm-MPa") and deck_unit_factors("m-Pa") == unit_factors("m-Pa")
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


def test_the_four_stated_systems_use_the_engines_constants():
    assert list(UNIT_SYSTEMS) == ["mm-MPa", "m-Pa", "in-psi", "in-ksi"] and set(UNIT_LABEL) == set(UNIT_SYSTEMS)
    assert unit_factors("in-psi") == {"length": INCH, "stress": PSI, "force": LBF, "force_per_length": LBF / INCH, "per_length": 1 / INCH}
    assert unit_factors("in-ksi")["stress"] == 1e3 * PSI and unit_factors("in-ksi")["length"] == INCH
    assert to_si(10.0, "length", "in-psi") == pytest.approx(0.254)
    assert to_si(1.0, "stress", "in-psi") == pytest.approx(6894.757, rel=1e-6) and to_si(1.0, "stress", "in-ksi") == pytest.approx(6.894757e6, rel=1e-6)
    assert to_si(1.0, "force", "in-psi") == pytest.approx(4.448222, rel=1e-6)
    assert from_si(to_si(23.5e6, "stress", "in-psi"), "stress", "in-ksi") == pytest.approx(23.5e3)
    assert from_si(1000.0, "force_per_length", "in-psi") == pytest.approx(1000.0 * INCH / LBF)  # N/m to lbf/in
    assert UNIT_LABEL["in-psi"] == {"force": "lbf", "length": "in", "stress": "psi", "force_per_length": "lbf/in", "modulus": "Msi", "stiffness": "lbf/in",
                                    "per_length": "1/in", "moment": "lbf·in/in", "rotation": "rad"}
    assert UNIT_LABEL["in-ksi"]["stress"] == "ksi"
    assert units_words("mm-MPa") == "mm, MPa and N" and units_words("in-ksi") == "in, ksi and lbf"


def test_a_deck_is_written_in_a_deck_system():
    assert deck_units_of("mm-MPa") == "mm-MPa" and deck_units_of("m-Pa") == "m-Pa"
    assert deck_units_of("in-psi") == "mm-MPa" and deck_units_of("in-ksi") == "mm-MPa"
    with pytest.raises(ValueError, match="units must be stated"):
        deck_units_of("SI")


@pytest.mark.parametrize("bad", [None, "", "MM-MPA", "SI", "in"])
def test_unknown_or_missing_units_are_refused(bad):
    with pytest.raises(ValueError, match="units must be stated"):
        unit_factors(bad)
    with pytest.raises(ValueError, match="units must be stated"):
        deck_unit_factors(bad)


@pytest.mark.parametrize("stated", ["in-psi", "in-ksi"])
def test_a_deck_cannot_be_stated_in_inches(stated):
    deck = parse_deck(DECK.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="An Abaqus deck carries no units"):
        deck_unit_factors(stated)
    with pytest.raises(ValueError, match="An Abaqus deck carries no units"):
        deck_to_si(deck, stated)


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
